#!/usr/bin/env python3
# $1 = scanner device
# $2 = friendly name

import argparse
import glob
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, TextIO

from sendtoftps import sendtoftps
from trigger_inotify import trigger_inotify
from trigger_telegram import trigger_telegram
from ocr_queue import enqueue as enqueue_ocr
import jobstate
import thumbnails

ENVIRONMENT_FILE_PATH = "/opt/brother/scanner/env.txt"
LOCKED_KEYS_PATH = "/opt/brother/scanner/locked.txt"
DEFAULT_CONFIG_FILE = "/scans/.config/scanner.conf"
SCRIPT_DIR = "/opt/brother/scanner/brscan-skey/script"
SCAN_DIR = "/scans"
GM_COMPRESSED_JPEG_SETTINGS = ["-compress", "JPEG", "-quality", "80"]


#
# Utility methods
#

def set_status(status: str) -> None:
    """
    Sets the status by creating a temporary file.
    
    Parameters:
    status (str): The status to be set.
    """
    status_file = os.path.join(tempfile.gettempdir(), f"STATUS_{status.upper()}")
    with open(status_file, 'w') as temp_file:
        temp_file.write(status)


def read_status(status: str) -> bool:
    """
    Checks if the status file exists.
    
    Parameters:
    status (str): The status to be checked.
    
    Returns:
    bool: True if the status file exists, False otherwise.
    """
    status_file = os.path.join(tempfile.gettempdir(), f"STATUS_{status.upper()}")
    return os.path.exists(status_file)


def clear_status(status: str) -> None:
    """
    Clears the status by deleting the temporary file.
    
    Parameters:
    status (str): The status to be cleared.
    """
    status_file = os.path.join(tempfile.gettempdir(), f"STATUS_{status.upper()}")
    if os.path.exists(status_file):
        os.remove(status_file)


def read_environment() -> None:
    # Read the environment variables from the file,
    # as brscan is screwing it up
    with open(ENVIRONMENT_FILE_PATH, "r") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line or line.startswith("#") or "=" not in line:
                continue  # blank lines, comments, anything that is not KEY=VALUE
            key, value = line.split("=", 1)  # values may contain "=" themselves
            os.environ[key] = value
    apply_config_file()
    apply_timezone()


def parse_config_file(path: str) -> Dict[str, str]:
    """KEY=VALUE lines of the configuration file; comments, blanks and bad keys skipped."""
    values: Dict[str, str] = {}
    try:
        with open(path, "r") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return values
    for line in lines:
        line = line.rstrip("\r")
        if not line.strip() or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.replace(" ", "")
        if not re.match(r"^[A-Z][A-Z0-9_]*$", key):
            continue
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1]
        values[key] = value
    return values


def locked_keys() -> set:
    try:
        with open(LOCKED_KEYS_PATH, "r") as handle:
            return {line.strip() for line in handle if line.strip()}
    except OSError:
        return set()


def apply_config_file() -> None:
    """Overlay the configuration file (settings page) on the environment.

    Called after env.txt so that changes made while the container runs take
    effect for the next job. Keys that the container environment sets are
    locked (recorded by the entrypoint) and are never overridden.
    """
    path = os.environ.get("SCANNER_CONFIG_FILE") or DEFAULT_CONFIG_FILE
    locked = locked_keys()
    for key, value in parse_config_file(path).items():
        if key not in locked:
            os.environ[key] = value


JOB_NAME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}$")
DEVICE_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9 \[\]\(\),&-]{1,60}$")


def parse_entry_args(argv: List[str]) -> argparse.Namespace:
    """Arguments of the scanto*.py entry points.

    brscan-skey calls them as "<script> <device> <friendly name>"; the API adds
    --job-id and optional per-job parameters. Invalid values are rejected here
    so nothing unexpected reaches scanimage.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("device", nargs="?", default=None)
    parser.add_argument("friendly_name", nargs="?", default=None)
    parser.add_argument("--job-id", dest="job_id", default=None)
    parser.add_argument("--resolution", type=int, default=None)
    parser.add_argument("--mode", default=None)
    parser.add_argument("--source", default=None)
    args, _unknown = parser.parse_known_args(argv)
    if args.job_id is not None and not JOB_NAME_PATTERN.match(args.job_id):
        parser.error(f"invalid --job-id {args.job_id!r}")
    if args.resolution is not None and not (50 <= args.resolution <= 9600):
        parser.error(f"invalid --resolution {args.resolution}")
    for name in ("mode", "source"):
        value = getattr(args, name)
        if value is not None and not DEVICE_VALUE_PATTERN.match(value):
            parser.error(f"invalid --{name} {value!r}")
    return args


def entry_overrides(args: argparse.Namespace) -> Dict[str, str]:
    """Per-job scan parameters as environment overrides (RESOLUTION, SCAN_MODE, SCAN_SOURCE)."""
    overrides: Dict[str, str] = {}
    if args.resolution is not None:
        overrides["RESOLUTION"] = str(args.resolution)
    if args.mode is not None:
        overrides["SCAN_MODE"] = args.mode
    if args.source is not None:
        overrides["SCAN_SOURCE"] = args.source
    return overrides


def apply_overrides(overrides: Dict[str, str]) -> None:
    for key, value in overrides.items():
        os.environ[key] = value


def apply_timezone() -> None:
    """Make the C library pick up TZ from the environment.

    The scan scripts are started by brscan-skey from a login shell without TZ;
    read_environment() puts TZ into os.environ, but datetime.now() keeps using
    the time zone cached at process start until time.tzset() is called.
    Without this, job names and log times were in UTC.
    """
    if hasattr(time, "tzset"):
        time.tzset()


def execute_command(log: TextIO, command: List[str], capture: bool = False, **kwargs):
    log.flush()
    print(f"  DEBUG: Executing command: {command}, kwargs={kwargs}")
    log.flush()

    if capture:
        # Run the command with its output captured (and copied into the log), so
        # the caller can inspect it, e.g. to classify a scan failure. `check` is
        # honoured here instead of by subprocess.run so the captured output can
        # be attached to the raised error.
        check = kwargs.pop("check", False)
        proc = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
        if proc.stdout:
            log.write(proc.stdout)
            log.flush()
        if check and proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, command, output=proc.stdout)
        return proc.stdout

    subprocess.run(command, text=True, stdout=log, stderr=log, **kwargs)
    return None


def execute_command_pid(log: TextIO, command: List[str], **kwargs) -> int:
    log.flush()
    print(f"  DEBUG: Executing command: {command}, kwargs={kwargs}")
    log.flush()

    process = subprocess.Popen(
        command, start_new_session=True, text=True, stdout=log, stderr=log, **kwargs
    )
    return process.pid


DEFAULT_SCAN_AREA_MM = {"left": "0", "top": "0", "width": "215", "height": "297"}


def scan_area_mm() -> Dict[str, str]:
    """Scan window in mm from SCAN_LEFT_MM, SCAN_TOP_MM, SCAN_WIDTH_MM, SCAN_HEIGHT_MM.

    Lets the window be calibrated to the device: the ADF feeds the sheet a
    little before scanning starts, so a 297 mm window reaches past the trailing
    edge and shows a dark or white bar; SCAN_HEIGHT_MM=295 trims it. Values
    that are not numbers fall back to the defaults.
    """
    area = dict(DEFAULT_SCAN_AREA_MM)
    for key, variable in (("left", "SCAN_LEFT_MM"), ("top", "SCAN_TOP_MM"),
                          ("width", "SCAN_WIDTH_MM"), ("height", "SCAN_HEIGHT_MM")):
        value = os.environ.get(variable, "").strip()
        if not value:
            continue
        try:
            number = float(value)
        except ValueError:
            print(f"  WARNING: {variable}={value!r} is not a number, using {area[key]} mm")
            continue
        if number < 0 or (key in ("width", "height") and number == 0):
            print(f"  WARNING: {variable}={value!r} out of range, using {area[key]} mm")
            continue
        area[key] = f"{number:g}"
    return area


SCANNER_CAPABILITIES_PATH = "/tmp/SCANNER_CAPABILITIES"
FLATBED_SOURCE = "FlatBed"


def device_has_flatbed(path: str = SCANNER_CAPABILITIES_PATH) -> bool:
    """True when the device lists a flatbed source in its capabilities (captured
    by the entrypoint into SCANNER_CAPABILITIES)."""
    try:
        with open(path) as handle:
            return "flatbed" in handle.read().lower()
    except OSError:
        return False


def source_was_requested(scanimage_args: List[str]) -> bool:
    """True when a paper source was chosen explicitly, through SCAN_SOURCE or a
    per-job --source (web UI / API). Then we must not second-guess it."""
    if os.environ.get("SCAN_SOURCE", "").strip():
        return True
    return any(arg.startswith("--source=") for arg in scanimage_args)


def adf_empty_from_start(scanimage_output: str) -> bool:
    """True when scanimage failed because the document feeder was empty from the
    start (SANE_STATUS_NO_DOCS), as brscan5 reports it. A paper jam is a
    different condition and must not trigger a flatbed scan of the empty glass."""
    text = (scanimage_output or "").lower()
    if "jam" in text:
        return False
    return "out of documents" in text or "no docs" in text or "no_docs" in text or "no documents" in text


def first_batch_page_exists(output_batch: str) -> bool:
    """True when the batch produced at least its first page."""
    first = output_batch % 1 if "%" in output_batch else output_batch
    return os.path.exists(first)


def with_flatbed_source(scan_command: List[str]) -> List[str]:
    """Copy of the scan command with the paper source forced to the flatbed."""
    rebuilt = [arg for arg in scan_command if not arg.startswith("--source=")]
    # place the source next to the other mode options, before --resolution
    insert_at = next((i for i, arg in enumerate(rebuilt) if arg.startswith("--resolution=")), len(rebuilt))
    rebuilt.insert(insert_at, f"--source={FLATBED_SOURCE}")
    return rebuilt


def scan_cmd(
    log: TextIO, device: Optional[str], output_batch: str, scanimage_args: List[str]
) -> None:
    log.flush()  # Required, otherwise scanimage output will appear before the already printed output

    resolution = os.environ.get("RESOLUTION", 300)
    area = scan_area_mm()
    # SCAN_MODE selects the device mode (e.g. "True Gray", "Black & White") for all
    # scans; an explicit --mode in scanimage_args (scan to OCR) takes precedence.
    mode_args: List[str] = []
    scan_mode = os.environ.get("SCAN_MODE", "").strip()
    if scan_mode and not any(arg.startswith("--mode=") for arg in scanimage_args):
        mode_args = [f"--mode={scan_mode}"]
    # SCAN_SOURCE selects the paper source, e.g. "Automatic Document Feeder(left
    # aligned,Duplex)" on duplex-capable models or "FlatBed"; the values are the
    # ones the device lists at container start. Unset keeps the device default.
    scan_source = os.environ.get("SCAN_SOURCE", "").strip()
    if scan_source and not any(arg.startswith("--source=") for arg in scanimage_args):
        mode_args.append(f"--source={scan_source}")
    # `brother4:net1;dev0` device name gets passed to scanimage, which it refuses as an invalid device name
    #   for some reason.
    # Let's use the default scanner for now
    # fmt: off
    scan_command = [
        "scanimage",
        "-l", area["left"], "-t", area["top"], "-x", area["width"], "-y", area["height"],
        "--format=pnm",
        *mode_args,
        *scanimage_args,
        f"--resolution={resolution}",
        f"--batch={output_batch}",
    ]
    # fmt: on
    try:
        execute_command(log, scan_command, check=True, capture=True)
    except subprocess.CalledProcessError as error:
        # brscan5 aborts with "Document feeder out of documents" when the ADF is
        # empty, where brscan4 silently fell back to the flatbed (#180). When no
        # source was chosen, nothing was scanned yet, and the device has a
        # flatbed, retry once from the glass so a single button works for both.
        if (
            not source_was_requested(scanimage_args)
            and not first_batch_page_exists(output_batch)
            and adf_empty_from_start(error.output)
            and device_has_flatbed()
        ):
            print("  document feeder empty; retrying the scan from the flatbed")
            execute_command(log, with_flatbed_source(scan_command), check=True, capture=True)
        else:
            raise


def notify(log: TextIO, file_path: str, message: str) -> None:
    trigger_inotify(
        log,
        os.getenv("SSH_USER"),
        os.getenv("SSH_PASSWORD"),
        os.getenv("SSH_HOST"),
        os.getenv("SSH_PATH"),
        file_path,
    )
    trigger_telegram(
        log,
        f"Scanner: {message}",
        os.getenv("TELEGRAM_TOKEN"),
        os.getenv("TELEGRAM_CHATID"),
    )


def latest_batch_dir() -> Optional[str]:
    prefix = datetime.today().strftime("%Y-%m-%d")
    dir_entries = glob.glob(os.path.join(tempfile.gettempdir(), f"{prefix}*"))
    dirs = filter(os.path.isdir, dir_entries)
    sorted_dirs = sorted(dirs, key=os.path.getctime)
    if len(sorted_dirs) == 0:
        return None
    return os.path.basename(sorted_dirs[-1])


def move_across_mounts(source: str, destination: str) -> None:
    """Moves a file across mounts.

    Args:
        source (str): The source path.
        destination (str): The destination path.
    """

    try:
        print(f"  DEBUG: Moving {source} to {destination}")
        shutil.copy2(source, destination)
        os.remove(source)
    except Exception as e:
        print(f"  ERROR: moving file - {e}")


def clean_job_files(log: TextIO, side: str, job_name: str):
    # Cleanup temporary files
    print(f"  {side} side: cleaning up for {job_name}...")
    shutil.rmtree(os.path.join(tempfile.gettempdir(), job_name))


#
# PDF manipulation methods
#
def parse_page_count(pdfinfo_output: str) -> Optional[int]:
    """Extract the page count from pdfinfo output."""
    match = re.search(r"^Pages:\s*(\d+)", pdfinfo_output, re.MULTILINE)
    return int(match.group(1)) if match else None


def parse_ink_coverage(gs_output: str) -> Optional[float]:
    """Sum the CMYK coverage percentages reported by the gs ink_cov device."""
    for line in gs_output.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[4] == "CMYK":
            try:
                return sum(float(value) for value in parts[:4])
            except ValueError:
                continue
    return None


def pdf_page_count(log: TextIO, input_file: str) -> Optional[int]:
    process = subprocess.Popen(["pdfinfo", input_file], stdout=subprocess.PIPE, stderr=log)
    output, _ = process.communicate()
    if process.returncode != 0:
        return None
    return parse_page_count(output.decode())


def page_ink_coverage(log: TextIO, input_file: str, page: int) -> Optional[float]:
    process = subprocess.Popen(
        ["gs", "-o", "-", f"-dFirstPage={page}", f"-dLastPage={page}", "-sDEVICE=ink_cov", input_file],
        stdout=subprocess.PIPE,
        stderr=log,
    )
    output, _ = process.communicate()
    return parse_ink_coverage(output.decode())


def remove_blank_pages(
    log: TextIO, input_file: str, remove_blank_threshold: float
) -> None:
    """Removes blank pages from a PDF file based on a threshold.

    remove_blank - git.waldenlabs.net/calvinrw/brother-paperless-workflow
    Heavily based on from Anthony Street's (and other contributors')
    StackExchange answer: https://superuser.com/a/1307895

    Args:
    input_file (str): The path to the input PDF file.
    remove_blank_threshold (float): The threshold for ink coverage to consider a page non-blank.
    """

    filename = os.path.splitext(os.path.basename(input_file))[0]
    dirname = os.path.dirname(input_file)

    page_count = pdf_page_count(log, input_file)
    if page_count is None:
        print(f"  ERROR: getting number of pages from {input_file}")
        return

    print(
        f"  Analyzing {page_count} pages in {input_file} with threshold {remove_blank_threshold}%"
    )
    os.chdir(dirname)

    def non_blank_pages() -> List[str]:
        picked_pages: List[str] = []
        for page in range(1, page_count + 1):
            ink_coverage = page_ink_coverage(log, input_file, page)
            if ink_coverage is None:
                # Could not measure: never drop a page we know nothing about.
                print(f"    Page {page}: keep (ink coverage unknown)")
                picked_pages.append(str(page))
            elif ink_coverage < remove_blank_threshold:
                print(f"    Page {page}: delete (ink coverage: {ink_coverage:.2f}%)")
            else:
                picked_pages.append(str(page))
                print(f"    Page {page}: keep (ink coverage: {ink_coverage:.2f}%)")

        return picked_pages

    # Use pdftk to remove pages
    try:
        output_file = os.path.join(dirname, f"{filename}_noblank.pdf")
        selected_pages = non_blank_pages()
        command = [
            "/usr/bin/pdftk",
            input_file,
            "cat",
            *selected_pages,
            "output",
            output_file,
        ]
        execute_command(log, command, check=True)

        removed_pages = page_count - len(selected_pages)
        if removed_pages == 0:
            print(f"  No blank pages detected in {input_file}")
        else:
            os.replace(output_file, input_file)
            print(f"  Removed {removed_pages} blank pages and saved as {input_file}")
    except FileNotFoundError:
        print(
            f"  WARNING: '{command[0]}' executable not found. Skipping PDF manipulation."
        )
    except subprocess.CalledProcessError:
        print(f"  ERROR: manipulating {input_file}. Skipping PDF manipulation.")


#
# Async job methods
#
def convert_and_post_process(
    job_name: str, side: str, remove_blank_threshold: Optional[float]
) -> None:
    log = sys.stdout
    log.flush()

    print(f"  {side} side: converting to PDF for {job_name}...")
    jobstate.update(job_name, state="converting", side=side)

    # Find job pages, sorted in the correct order
    job_dir = os.path.join(tempfile.gettempdir(), job_name)
    tmp_output_pdf_file = os.path.join(job_dir, f"{job_name}.pdf")
    output_pdf_file = os.path.join(SCAN_DIR, f"{job_name}.pdf")
    if side == "front":
        filepath_base = os.path.join(job_dir, f"{job_name}-{side}-page")
        input_files = glob.glob(f"{filepath_base}*.pnm")
    else:
        input_files = glob.glob(os.path.join(job_dir, "*.pnm"))
    input_files.sort()

    # Convert pages to single PDF with optional JPEG compression
    # The pages are RESOLUTION dpi pixels; tell gm so the PDF page size is right
    # (A4 at 300 dpi gives 595 x 842 pt). Without this the page is the pixel
    # size at 72 dpi, i.e. 34 x 49 inches, and every consumer that renders the
    # page at a fixed dpi (the OCR service, gs) produces 4x the pixels.
    gm_opts = ["-density", str(os.environ.get("RESOLUTION", 300)), "-units", "PixelsPerInch"]
    if os.environ.get("USE_JPEG_COMPRESSION", "false") == "true":
        gm_opts += GM_COMPRESSED_JPEG_SETTINGS
    execute_command(
        log, ["gm", "convert", *gm_opts, *input_files, tmp_output_pdf_file], check=True
    )

    if remove_blank_threshold:
        remove_blank_pages(log, tmp_output_pdf_file, remove_blank_threshold)

    move_across_mounts(tmp_output_pdf_file, output_pdf_file)

    # thumbnail for the file list, so the web UI never has to render it on request
    if thumbnails.enabled():
        thumbnails.render(output_pdf_file, log=lambda message: print(f"  {message}"))

    notify(log, output_pdf_file, f"{job_name}.pdf ({side}) scanned")
    sendtoftps(
        log,
        os.getenv("FTP_USER"),
        os.getenv("FTP_PASSWORD"),
        os.getenv("FTP_HOST"),
        os.getenv("FTP_PATH"),
        output_pdf_file,
    )

    clean_job_files(log, side, job_name)

    # OCR is handed to the queue worker (ocr_queue.py), which uploads one scan
    # at a time and runs the post-OCR notifications itself.
    ocr_state = "none"
    if not all([os.getenv("OCR_SERVER"), os.getenv("OCR_PORT"), os.getenv("OCR_PATH")]):
        print(f"  {side} side: OCR environment variables not set, skipping OCR.")
    else:
        print(f"  {side} side: queueing OCR for {job_name}...")
        enqueue_ocr(output_pdf_file, job_name, side)
        ocr_state = "queued"
    jobstate.update(job_name, state="done", side=side, file=os.path.basename(output_pdf_file),
                    ocr=ocr_state, ocr_file=f"{job_name}-ocr.pdf" if ocr_state == "queued" else None)

    print(f"  {side} side: Conversion and post-processing finished.")
    print("-----------------------------------")


def rear_page_wait_seconds() -> int:
    return int(os.environ.get("REAR_PAGE_WAIT_SECONDS", "120"))


def wait_for_rear_pages_or_convert(job_name: str) -> None:
    # Wait for 2 minutes in case there is a rear side scan
    wait_seconds = rear_page_wait_seconds()
    print(f"  front side: Waiting {wait_seconds}s for rear pages before starting file conversion for {job_name}")
    try:
        set_status('waiting')
        time.sleep(wait_seconds)
    finally:
        clear_status('waiting')

    convert_and_post_process(job_name, "front", None)


#
# Reading/writing of temp state files
#


def scanimage_args_path(job_dir: str) -> str:
    # File where the arguments to scanimage are saved across steps in the job
    return os.path.join(job_dir, ".scanimage_args")


def save_scanimage_args(job_dir: str, scanimage_args: List[str]) -> None:
    # Save scanimage_args in a file for use with future rear side scans
    path = scanimage_args_path(job_dir)
    with open(path, "w") as scanimage_args_file:
        for arg in scanimage_args:
            scanimage_args_file.write(arg + "\n")


def read_scanimage_args(job_dir: str) -> List[str]:
    # Read scanimage_args used for front scanning
    path = scanimage_args_path(job_dir)
    scanimage_args = []
    try:
        with open(path, "r") as scanimage_args_file:
            scanimage_args = [line.rstrip() for line in scanimage_args_file]

        os.remove(path)
    except FileNotFoundError:
        print(f"  ERROR: scanimage_args file {path} not found.")

    return scanimage_args


def scan_pid_path(job_dir: str) -> str:
    return os.path.join(job_dir, ".scan_pid")


def save_front_processing_pid(job_dir: str, pid: int) -> None:
    with open(scan_pid_path(job_dir), "w") as pid_file:
        pid_file.write(str(pid))


def kill_front_processing_from_pid(job_dir: str) -> Optional[int]:
    path = scan_pid_path(job_dir)
    pid = None
    try:
        with open(path, "r") as scan_pid_file:
            pid = int(scan_pid_file.read().strip())
            print(
                f"  rear side: Read pid from {path}, killing front processing job {pid}"
            )
            os.kill(pid, signal.SIGKILL)
    except FileNotFoundError:
        print(f"  rear side: ERROR: scan_pid file {path} not found.")
    except ProcessLookupError:
        print(f"  rear side: ERROR: process with pid {pid} not found.")
    else:
        os.remove(path)
        return pid

    return None


def job_trigger(job_name_given: bool) -> Dict[str, Any]:
    """Who started this job, for its record (#187).

    The REST API and the web UI call the script with --job-id (the id they
    announced); the Scan-to-PC button daemon on the device calls it without
    one. So "trigger" is "api" or "button". A daemon that hands the button
    event on in the environment (openskey: SKEY_FUNC, SKEY_P1..4, SKEY_SEQ,
    SKEY_REGID, SKEY_CLIENT; Brother's brscan-skey passes nothing) gets those
    details recorded under "button", so a client such as Home Assistant can
    tell which button was pressed.
    """
    if job_name_given:
        return {"trigger": "api"}
    record: Dict[str, Any] = {"trigger": "button"}
    button: Dict[str, Any] = {}
    function = os.environ.get("SKEY_FUNC", "").strip().lower()
    if function:
        button["function"] = function
    for key, variable in (("seq", "SKEY_SEQ"), ("regid", "SKEY_REGID")):
        value = os.environ.get(variable, "").strip()
        if value.isdigit():
            button[key] = int(value)
    params: Dict[str, int] = {}
    for i in range(1, 5):
        value = os.environ.get(f"SKEY_P{i}", "").strip()
        if value.isdigit():
            params[f"p{i}"] = int(value)
    if params:
        button["params"] = params
    client = os.environ.get("SKEY_CLIENT", "").strip()
    if client:
        button["client"] = client
    if button:
        record["button"] = button
    return record


#
# Scan entry points
#
def scan_front(log: TextIO, device: Optional[str], scanimage_args=[], job_name: Optional[str] = None,
               action: str = "file", overrides: Optional[Dict[str, str]] = None) -> None:
    # Clear any existing waiting status before starting a new scan
    clear_status('waiting')

    # The job is named by its timestamp (the API passes the name it announced);
    # a job without a name was started on the device.
    trigger = job_trigger(job_name is not None)
    if job_name is None:
        job_name = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    jobstate.prune()
    jobstate.update(job_name, state="queued", action=action, side="front", params=overrides or {}, **trigger)
    job_dir = os.path.join(tempfile.gettempdir(), job_name)
    filepath_base = os.path.join(job_dir, f"{job_name}-front-page")
    tmp_output_batch = f"{filepath_base}%04d.pnm"

    # Create temporary directory
    os.makedirs(job_dir, exist_ok=True)
    os.chdir(job_dir)
    print(f"- Scanning front to batch {tmp_output_batch}")

    # Save scanimage_args in a file for use with future rear side scans
    save_scanimage_args(job_dir, scanimage_args)

    # Perform scan with retry; the status file lets the web UI show
    # 'scan in progress' without depending on process names.
    set_status('scan')
    jobstate.update(job_name, state="scanning")
    try:
        time.sleep(0.1)
        scan_cmd(log, device, tmp_output_batch, scanimage_args)
        if not os.path.exists(f"{filepath_base}0001.pnm"):
            time.sleep(1)  # Short delay before retry
            scan_cmd(log, device, tmp_output_batch, scanimage_args)
    except subprocess.CalledProcessError:
        print(" ERROR: Cancelling scanning!")
        jobstate.update(job_name, state="failed", error="scanning failed or was cancelled")
        clean_job_files(log, 'front', job_name)
        return
    finally:
        clear_status('scan')

    # Run conversion process in the background
    # Everything printed so far sits in the log buffer; flush it before forking,
    # otherwise parent and child both write it out and every line appears twice.
    log.flush()
    sys.stdout.flush()
    pid = os.fork()
    if pid == 0:  # Child process
        wait_for_rear_pages_or_convert(job_name)
        os._exit(0)  # Exit child process cleanly
    elif pid > 0:
        save_front_processing_pid(job_dir, pid)
        print(
            f"  front side: INFO: Waiting to start conversion process for {job_name} in process with PID {pid}"
        )
        pages = len(glob.glob(f"{filepath_base}*.pnm"))
        jobstate.update(job_name, state="waiting_for_rear", pages=pages,
                        waiting_until=time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() + rear_page_wait_seconds())))
    else:
        print(f"  front side: ERROR: Fork failed ({pid}).")


def scan_back(log: TextIO, device: Optional[str], scanimage_args=None, job_name: Optional[str] = None) -> None:
    # The job to attach to: the one named by the API, or the latest front scan
    if job_name is None:
        job_name = latest_batch_dir()
        print(f"- Scanning rear to latest batch {job_name}")
    else:
        print(f"- Scanning rear for job {job_name}")
        if not os.path.isdir(os.path.join(tempfile.gettempdir(), job_name)):
            print(f"  rear side: ERROR: job {job_name} is not waiting for rear pages")
            return
    if job_name is None:
        print("  rear side: ERROR: Could not find front scan directory")
        return
    record = jobstate.read(job_name) or {}
    apply_overrides(record.get("params") or {})

    print(f"  rear side: Found front-side batch: {job_name}")
    job_dir = os.path.join(tempfile.gettempdir(), job_name)
    filepath_base = os.path.join(job_dir, f"{job_name}-back-page")
    tmp_output_batch = f"{filepath_base}%04d.pnm"

    os.chdir(job_dir)

    # Interrupt front scanning process which is waiting from a rear side scan.
    # Either way nobody is waiting for rear pages any more: the front job is
    # taken over by this rear scan, or it is already gone. Clear the status
    # now, because the killed child cannot run its own cleanup (SIGKILL),
    # and a failing rear scan below must not leave a stale waiting state.
    front_pid = kill_front_processing_from_pid(job_dir)
    clear_status('waiting')
    if front_pid is None:
        return

    if scanimage_args is None:
        # Read scanimage_args used for front scanning
        scanimage_args = read_scanimage_args(job_dir)

    # Perform scan with retry; the status file lets the web UI show
    # 'scan in progress' without depending on process names.
    set_status('scan')
    jobstate.update(job_name, state="scanning_rear", side="rear")
    try:
        time.sleep(0.1)
        scan_cmd(log, device, tmp_output_batch, scanimage_args)
        if not os.path.exists(f"{filepath_base}0001.pnm"):
            time.sleep(1)  # Short delay before retry
            scan_cmd(log, device, tmp_output_batch, scanimage_args)
    except subprocess.CalledProcessError:
        print(" ERROR: Cancelling scanning!")
        jobstate.update(job_name, state="failed", error="rear scanning failed or was cancelled")
        clean_job_files(log, "back", job_name)
        return
    finally:
        clear_status('scan')

    # Rename pages
    number_of_pages = len(
        [f for f in os.listdir(".") if (os.path.isfile(f) and "front-page" in f)]
    )
    print(f"  rear side: INFO: number of pages scanned: {number_of_pages}")

    cnt = 0
    for filename in sorted(glob.glob("*front*.pnm")):
        cnt += 1
        cnt_formatted = f"{cnt:03d}"
        new_filename = f"index{cnt_formatted}-1-{filename}"
        os.rename(filename, new_filename)
        print(f"  rear side: DEBUG: renamed {filename} to {new_filename}")

    cnt = 0
    for filename in sorted(glob.glob("*back*.pnm")):
        cnt += 1
        rear_index = number_of_pages - cnt + 1
        rear_index_formatted = f"{rear_index:03d}"
        new_filename = f"index{rear_index_formatted}-2-{filename}"
        os.rename(filename, new_filename)
        print(f"  rear side: DEBUG: renamed {filename} to {new_filename}")

    # Convert to PDF
    remove_blank_threshold_str = os.getenv("REMOVE_BLANK_THRESHOLD")
    remove_blank_threshold = None
    if remove_blank_threshold_str is not None and remove_blank_threshold_str != "":
        remove_blank_threshold = float(remove_blank_threshold_str)

    # Everything printed so far sits in the log buffer; flush it before forking,
    # otherwise parent and child both write it out and every line appears twice.
    log.flush()
    sys.stdout.flush()
    pid = os.fork()
    if pid == 0:  # Child process
        convert_and_post_process(job_name, "rear", remove_blank_threshold)
        os._exit(0)  # Exit child process cleanly

    elif pid < 0:
        print(f"  rear side: ERROR: Fork failed ({pid}).")
