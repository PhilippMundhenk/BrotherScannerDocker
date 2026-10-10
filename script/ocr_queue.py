#!/usr/bin/env python3
"""OCR upload queue.

Scans are not uploaded to the OCR service directly by the scan pipeline.
Instead the pipeline enqueues a small job file and a single worker process
(started by runScanner.sh as the scanner user) drains the queue one upload at
a time. This keeps several scans in quick succession from competing for the
same upload bandwidth and from overwhelming the single-threaded OCR backend.

Queue layout (under OCR_QUEUE_DIR, default /scans/.ocr_queue, which lives on
the persistent volume so the queue survives container restarts):

    pending/      newly enqueued jobs, oldest first by filename prefix
    in_progress/  the single job currently being processed
    failed/       jobs that exceeded OCR_MAX_ATTEMPTS, plus any invalid
                  response the OCR service returned (<job>.response-<n>)

A job file is plain KEY=VALUE text:

    PDF=/scans/2026-05-17-17-22-59.pdf
    DATE=2026-05-17-17-22-59
    SUFFIX=front
    ATTEMPTS=0

All state transitions are a single rename within the same directory tree, so
the queue is safe on filesystems without inotify or flock (SMB mounts).

The OCR result is downloaded to a temporary name and only moved to
<date>-ocr.pdf after it has been validated (PDF header, parseable, same page
count as the original). The original scan is removed (REMOVE_ORIGINAL_AFTER_OCR)
only after that validation passed, never otherwise.

Usage:
    ocr_queue.py worker                       run the worker loop (forever)
    ocr_queue.py enqueue <pdf> <date> <side>  add a job (used by tests/tools)
"""

import glob
import os
import re
import subprocess
import sys
import tempfile
import time
from typing import Callable, Dict, Optional, TextIO, Tuple

from sendtoftps import sendtoftps
from trigger_inotify import trigger_inotify
from trigger_telegram import trigger_telegram

DEFAULT_QUEUE_DIR = "/scans/.ocr_queue"
DEFAULT_OUTPUT_DIR = "/scans"
PART_SUFFIX = ".part"
SCAN_STATUS_MAX_AGE = 600  # a STATUS_SCAN file older than this is considered stale
IDLE_WAIT_MAX = 1800  # never hold an upload back for more than half an hour


def queue_root() -> str:
    return os.environ.get("OCR_QUEUE_DIR", DEFAULT_QUEUE_DIR)


def queue_dirs(root: Optional[str] = None) -> Dict[str, str]:
    root = root or queue_root()
    return {
        "pending": os.path.join(root, "pending"),
        "in_progress": os.path.join(root, "in_progress"),
        "failed": os.path.join(root, "failed"),
    }


def ensure_dirs(root: Optional[str] = None) -> Dict[str, str]:
    dirs = queue_dirs(root)
    for path in dirs.values():
        os.makedirs(path, exist_ok=True)
    return dirs


def log(message: str) -> None:
    print(f"[ocr_queue {time.strftime('%Y-%m-%dT%H:%M:%S')}] {message}")
    sys.stdout.flush()


#
# Job files
#
def write_job(path: str, fields: Dict[str, str]) -> None:
    """Write a job file atomically (hidden temp file, then rename)."""
    directory, name = os.path.split(path)
    tmp = os.path.join(directory, f".{name}.tmp")
    with open(tmp, "w") as handle:
        for key, value in fields.items():
            handle.write(f"{key}={value}\n")
    os.replace(tmp, path)


def read_job(path: str) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    with open(path, "r") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if "=" in line:
                key, value = line.split("=", 1)
                fields[key] = value
    return fields


def enqueue(pdf_path: str, job_name: str, side: str, root: Optional[str] = None) -> str:
    """Add an upload job for pdf_path to the pending queue. Returns the job file path."""
    dirs = ensure_dirs(root)
    # Nanosecond timestamp prefix keeps the queue roughly FIFO by filename.
    name = f"{time.time_ns()}-{job_name}-{side}.job"
    path = os.path.join(dirs["pending"], name)
    write_job(path, {"PDF": pdf_path, "DATE": job_name, "SUFFIX": side, "ATTEMPTS": "0"})
    log(f"queued {name}")
    return path


def recover(root: Optional[str] = None) -> int:
    """Return jobs stranded in in_progress/ (crash, restart) to pending/."""
    dirs = ensure_dirs(root)
    moved = 0
    for path in sorted(glob.glob(os.path.join(dirs["in_progress"], "*.job"))):
        name = os.path.basename(path)
        try:
            os.rename(path, os.path.join(dirs["pending"], name))
            log(f"recovered {name} from in_progress")
            moved += 1
        except OSError:
            pass
    return moved


#
# PDF validation
#
def pdf_page_count(path: str) -> Optional[int]:
    """Page count via pdfinfo, or None when the file is not a readable PDF."""
    try:
        result = subprocess.run(["pdfinfo", path], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    match = re.search(r"^Pages:\s*(\d+)", result.stdout, re.MULTILINE)
    return int(match.group(1)) if match else None


def validate_pdf(
    path: str, expected_pages: Optional[int], count_pages: Callable[[str], Optional[int]] = pdf_page_count
) -> Tuple[bool, str]:
    """Check that path is a usable PDF with the expected number of pages."""
    try:
        size = os.path.getsize(path)
    except OSError as error:
        return False, f"missing: {error}"
    if size == 0:
        return False, "empty file"
    with open(path, "rb") as handle:
        head = handle.read(5)
    if head != b"%PDF-":
        return False, f"not a PDF (starts with {head!r}, {size} bytes)"
    pages = count_pages(path)
    if pages is None:
        return False, "pdfinfo cannot read it"
    if expected_pages is not None and pages != expected_pages:
        return False, f"{pages} pages, original has {expected_pages}"
    return True, f"{pages} pages, {size} bytes"


#
# Scanner activity
#
def scanner_busy(max_age: float = SCAN_STATUS_MAX_AGE) -> bool:
    """True while scanner.py marks a scan in progress (STATUS_SCAN in the temp dir).

    The worker and the scan scripts run as the same user, so they share the
    temp directory. A stale marker (crashed scan) is ignored after max_age.
    """
    marker = os.path.join(tempfile.gettempdir(), "STATUS_SCAN")
    try:
        return (time.time() - os.path.getmtime(marker)) < max_age
    except OSError:
        return False


def wait_for_idle_scanner(sleep: Callable[[float], None] = time.sleep, poll: float = 2.0,
                          max_wait: float = IDLE_WAIT_MAX, busy: Callable[[], bool] = scanner_busy) -> float:
    """Block while a scan is running so the upload never competes with the scanner.

    Scanning must stay as fast as possible; OCR is background work. Returns the
    time waited. Disable with OCR_WAIT_FOR_IDLE_SCANNER=false.
    """
    if os.environ.get("OCR_WAIT_FOR_IDLE_SCANNER", "true").strip().lower() == "false":
        return 0.0
    waited = 0.0
    announced = False
    marker = os.path.join(tempfile.gettempdir(), "STATUS_OCR_HOLD")
    try:
        while busy() and waited < max_wait:
            if not announced:
                log("scan in progress; holding OCR upload until the scanner is idle")
                announced = True
                # Tell the status endpoint the queue is held back by a scan.
                with open(marker, "w") as handle:
                    handle.write("holding")
            sleep(poll)
            waited += poll
    finally:
        if announced:
            try:
                os.remove(marker)
            except OSError:
                pass
    return waited


#
# Processing
#
def upload(pdf_path: str, output_path: str, url: str, run: Callable = subprocess.run) -> bool:
    """Upload pdf_path to the OCR service and store the response at output_path."""
    command = ["curl", "--fail", "--silent", "--show-error"]
    limit = os.environ.get("OCR_UPLOAD_LIMIT_RATE", "").strip()
    if limit:
        # Leave bandwidth for the scanner, e.g. "2M" for 2 MB/s (curl --limit-rate syntax).
        command += ["--limit-rate", limit]
    command += [
        "-F", f"userfile=@{pdf_path}",
        "-H", "Expect:",
        "-o", output_path,
        url,
    ]
    result = run(command, stdout=sys.stdout, stderr=sys.stdout)
    return result.returncode == 0


def keep_invalid_response(part_path: str, job: Dict[str, str], root: Optional[str]) -> Optional[str]:
    """Move an invalid OCR response into failed/ next to the job for inspection."""
    dirs = ensure_dirs(root)
    attempt = job.get("ATTEMPTS", "0")
    target = os.path.join(dirs["failed"], f"{job.get('DATE', 'unknown')}.response-{attempt}")
    try:
        os.replace(part_path, target)
        return target
    except OSError as error:
        log(f"could not keep invalid response {part_path}: {error}")
        try:
            os.remove(part_path)
        except OSError:
            pass
        return None


def process_job(
    job: Dict[str, str],
    output_dir: Optional[str] = None,
    run: Callable = subprocess.run,
    count_pages: Callable[[str], Optional[int]] = pdf_page_count,
    root: Optional[str] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Upload one job, validate the result and run the post-OCR side effects. True on success."""
    env = os.environ
    pdf = job.get("PDF", "")
    date = job.get("DATE", "")
    side = job.get("SUFFIX", "?")
    output_dir = output_dir or env.get("OCR_OUTPUT_DIR", DEFAULT_OUTPUT_DIR)

    server, port, path = env.get("OCR_SERVER"), env.get("OCR_PORT"), env.get("OCR_PATH")
    if not all([server, port, path]):
        log("OCR_SERVER/OCR_PORT/OCR_PATH not set; cannot process")
        return False
    if not pdf or not date:
        log("malformed job: PDF or DATE missing")
        return False
    if not os.path.isfile(pdf):
        log(f"input PDF missing: {pdf}")
        return False

    expected_pages = count_pages(pdf)
    if expected_pages is None:
        log(f"warning: cannot determine page count of {pdf}; the result's page count will not be compared")

    ocr_name = f"{date}-ocr.pdf"
    output_path = os.path.join(output_dir, ocr_name)
    part_path = output_path + PART_SUFFIX
    url = f"{server}:{port}/{path}"
    wait_for_idle_scanner(sleep=sleep)
    log(f"uploading {pdf} ({expected_pages} pages) to {url}")
    if not upload(pdf, part_path, url, run=run):
        log(f"OCR upload failed for {pdf}")
        if os.path.exists(part_path):
            os.remove(part_path)
        return False

    valid, detail = validate_pdf(part_path, expected_pages, count_pages=count_pages)
    if not valid:
        kept = keep_invalid_response(part_path, job, root)
        log(f"OCR result for {pdf} rejected: {detail}; original kept" + (f", response saved as {kept}" if kept else ""))
        return False

    os.replace(part_path, output_path)
    log(f"OCR finished -> {output_path} ({detail})")

    # Best effort side effects; none of them fails the job.
    out: TextIO = sys.stdout
    trigger_inotify(out, env.get("SSH_USER"), env.get("SSH_PASSWORD"), env.get("SSH_HOST"), env.get("SSH_PATH"), ocr_name)
    trigger_telegram(out, f"Scanner: {ocr_name} ({side}) OCR finished", env.get("TELEGRAM_TOKEN"), env.get("TELEGRAM_CHATID"))
    sendtoftps(out, env.get("FTP_USER"), env.get("FTP_PASSWORD"), env.get("FTP_HOST"), env.get("FTP_PATH"), output_path)

    # Only now, with a validated result in place, may the original go.
    if env.get("REMOVE_ORIGINAL_AFTER_OCR") == "true":
        ok, why = validate_pdf(output_path, expected_pages, count_pages=count_pages)
        if ok:
            try:
                os.remove(pdf)
                log(f"removed original {pdf} (REMOVE_ORIGINAL_AFTER_OCR)")
            except OSError as error:
                log(f"could not remove original {pdf}: {error}")
        else:
            log(f"original {pdf} kept: result failed re-validation ({why})")
    return True


def run_worker(
    root: Optional[str] = None,
    poll_seconds: Optional[float] = None,
    max_attempts: Optional[int] = None,
    backoff_seconds: Optional[float] = None,
    once: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    run: Callable = subprocess.run,
    count_pages: Callable[[str], Optional[int]] = pdf_page_count,
    refresh: Optional[Callable[[], None]] = None,
) -> None:
    """Drain the queue. With once=True, return as soon as pending/ is empty."""
    env = os.environ
    dirs = ensure_dirs(root)
    poll_seconds = float(env.get("OCR_QUEUE_POLL_SECONDS", "5")) if poll_seconds is None else poll_seconds
    max_attempts = int(env.get("OCR_MAX_ATTEMPTS", "5")) if max_attempts is None else max_attempts
    backoff_seconds = float(env.get("OCR_RETRY_BACKOFF_SECONDS", "30")) if backoff_seconds is None else backoff_seconds

    recover(root)
    log(f"queue worker started (poll={poll_seconds}s, max_attempts={max_attempts})")

    while True:
        candidates = sorted(glob.glob(os.path.join(dirs["pending"], "*.job")))
        if not candidates:
            if once:
                return
            sleep(poll_seconds)
            continue

        name = os.path.basename(candidates[0])
        claim = os.path.join(dirs["in_progress"], name)
        try:
            os.rename(candidates[0], claim)  # atomic claim
        except OSError:
            continue

        if refresh is not None:
            refresh()  # pick up settings changed since the last job
        job = read_job(claim)
        attempts = int(job.get("ATTEMPTS", "0") or 0) + 1
        job["ATTEMPTS"] = str(attempts)
        # Persist the attempt before uploading so a crash mid-upload still counts.
        write_job(claim, job)

        if process_job(job, run=run, count_pages=count_pages, root=root, sleep=sleep):
            os.remove(claim)
            continue

        if attempts >= max_attempts:
            os.rename(claim, os.path.join(dirs["failed"], name))
            log(f"{name} exceeded {max_attempts} attempts; moved to failed/")
            continue

        delay = attempts * backoff_seconds
        log(f"{name} attempt {attempts} failed; retrying in {delay:g}s")
        sleep(delay)
        os.rename(claim, os.path.join(dirs["pending"], name))


def main(argv) -> int:
    if len(argv) >= 2 and argv[1] == "worker":
        try:
            # Load the container environment the same way the scan scripts do;
            # su - starts with a clean environment.
            from scanner import read_environment
            read_environment()
            refresh = read_environment
        except (ImportError, FileNotFoundError):
            refresh = None
        run_worker(refresh=refresh)
        return 0
    if len(argv) == 5 and argv[1] == "enqueue":
        enqueue(argv[2], argv[3], argv[4])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
