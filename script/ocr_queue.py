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
    failed/       jobs that exceeded OCR_MAX_ATTEMPTS

A job file is plain KEY=VALUE text:

    PDF=/scans/2026-05-17-17-22-59.pdf
    DATE=2026-05-17-17-22-59
    SUFFIX=front
    ATTEMPTS=0

All state transitions are a single rename within the same directory tree, so
the queue is safe on filesystems without inotify or flock (SMB mounts).

Usage:
    ocr_queue.py worker                       run the worker loop (forever)
    ocr_queue.py enqueue <pdf> <date> <side>  add a job (used by tests/tools)
"""

import glob
import os
import subprocess
import sys
import time
from typing import Callable, Dict, Optional, TextIO

from sendtoftps import sendtoftps
from trigger_inotify import trigger_inotify
from trigger_telegram import trigger_telegram

DEFAULT_QUEUE_DIR = "/scans/.ocr_queue"
DEFAULT_OUTPUT_DIR = "/scans"


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
# Processing
#
def upload(pdf_path: str, output_path: str, url: str, run: Callable = subprocess.run) -> bool:
    """Upload pdf_path to the OCR service and store the response at output_path."""
    command = [
        "curl", "--fail", "--silent", "--show-error",
        "-F", f"userfile=@{pdf_path}",
        "-H", "Expect:",
        "-o", output_path,
        url,
    ]
    result = run(command, stdout=sys.stdout, stderr=sys.stdout)
    return result.returncode == 0


def process_job(job: Dict[str, str], output_dir: Optional[str] = None, run: Callable = subprocess.run) -> bool:
    """Upload one job and run the post-OCR side effects. True on success."""
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

    ocr_name = f"{date}-ocr.pdf"
    output_path = os.path.join(output_dir, ocr_name)
    url = f"{server}:{port}/{path}"
    log(f"uploading {pdf} to {url}")
    if not upload(pdf, output_path, url, run=run):
        log(f"OCR upload failed for {pdf}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return False
    log(f"OCR finished -> {output_path}")

    # Best effort side effects; none of them fails the job.
    out: TextIO = sys.stdout
    trigger_inotify(out, env.get("SSH_USER"), env.get("SSH_PASSWORD"), env.get("SSH_HOST"), env.get("SSH_PATH"), ocr_name)
    trigger_telegram(out, f"Scanner: {ocr_name} ({side}) OCR finished", env.get("TELEGRAM_TOKEN"), env.get("TELEGRAM_CHATID"))
    sendtoftps(out, env.get("FTP_USER"), env.get("FTP_PASSWORD"), env.get("FTP_HOST"), env.get("FTP_PATH"), output_path)

    if env.get("REMOVE_ORIGINAL_AFTER_OCR") == "true" and os.path.isfile(output_path):
        try:
            os.remove(pdf)
        except OSError as error:
            log(f"could not remove original {pdf}: {error}")
    return True


def run_worker(
    root: Optional[str] = None,
    poll_seconds: Optional[float] = None,
    max_attempts: Optional[int] = None,
    backoff_seconds: Optional[float] = None,
    once: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    run: Callable = subprocess.run,
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

        job = read_job(claim)
        attempts = int(job.get("ATTEMPTS", "0") or 0) + 1
        job["ATTEMPTS"] = str(attempts)
        # Persist the attempt before uploading so a crash mid-upload still counts.
        write_job(claim, job)

        if process_job(job, run=run):
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
        except (ImportError, FileNotFoundError):
            pass
        run_worker()
        return 0
    if len(argv) == 5 and argv[1] == "enqueue":
        enqueue(argv[2], argv[3], argv[4])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
