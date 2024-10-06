#!/usr/bin/env python3
# $1 = scanner device
# $2 = friendly name

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
from typing import List, Optional, TextIO

from sendtoftps import sendtoftps
from trigger_inotify import trigger_inotify
from trigger_telegram import trigger_telegram

ENVIRONMENT_FILE_PATH = "/opt/brother/scanner/env.txt"
SCRIPT_DIR = "/opt/brother/scanner/brscan-skey/script"
SCAN_DIR = "/scans"
GM_COMPRESSED_JPEG_SETTINGS = ["-compress", "JPEG", "-quality", "80"]


#
# Utility methods
#


def read_environment() -> None:
    # Read the environment variables from the file,
    # as brscan is screwing it up
    with open(ENVIRONMENT_FILE_PATH, "r") as f:
        for line in f:
            if not line.startswith("#"):  # Skip comments
                key, value = line.strip().split("=")
                os.environ[key] = value


def execute_command(log: TextIO, command: List[str], **kwargs) -> None:
    log.flush()
    print(f"  DEBUG: Executing command: {command}, kwargs={kwargs}")
    log.flush()

    subprocess.run(command, text=True, stdout=log, stderr=log, **kwargs)


def execute_command_pid(log: TextIO, command: List[str], **kwargs) -> int:
    log.flush()
    print(f"  DEBUG: Executing command: {command}, kwargs={kwargs}")
    log.flush()

    process = subprocess.Popen(
        command, start_new_session=True, text=True, stdout=log, stderr=log, **kwargs
    )
    return process.pid


def scan_cmd(
    log: TextIO, device: Optional[str], output_batch: str, scanimage_args: List[str]
) -> None:
    log.flush()  # Required, otherwise scanimage output will appear before the already printed output

    resolution = os.environ.get("RESOLUTION", 300)
    # `brother4:net1;dev0` device name gets passed to scanimage, which it refuses as an invalid device name
    #   for some reason.
    # Let's use the default scanner for now
    # fmt: off
    scan_command = [
        "scanimage",
        "-l", "0", "-t", "0", "-x", "215", "-y", "297",
        "--format=pnm",
        *scanimage_args,
        f"--resolution={resolution}",
        f"--batch={output_batch}",
    ]
    # fmt: on
    execute_command(log, scan_command, check=True)


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


#
# PDF manipulation methods
#
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

    # Get the number of pages in the PDF
    process = subprocess.Popen(
        ["pdfinfo", input_file], stdout=subprocess.PIPE, stderr=log
    )
    output, _ = process.communicate()
    if process.returncode != 0:
        print(f"  ERROR: getting number of pages from {input_file}")
        return
    info = output.decode()
    pages_line = re.search(r"^Pages:\s*(\d+)", info, re.MULTILINE)
    if pages_line is None:
        print(f"  ERROR: finding number of pages in {info}")
        return
    page_count = int(pages_line.group(1))

    print(f"  Analyzing {page_count} pages in {input_file} with threshold {remove_blank_threshold}%")
    os.chdir(dirname)

    def non_blank_pages() -> List[str]:
        picked_pages: List[str] = []
        for page in range(1, page_count + 1):
            # Use subprocess to run gs and get ink coverage
            process = subprocess.Popen(
                [
                    "gs",
                    "-o",
                    "-",
                    f"-dFirstPage={page}",
                    f"-dLastPage={page}",
                    "-sDEVICE=ink_cov",
                    input_file,
                ],
                stdout=subprocess.PIPE,
                stderr=log,
            )
            output, _ = process.communicate()
            ink_coverage_line = re.search(
                r"^\s*([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+CMYK",
                output.decode(),
                re.MULTILINE,
            )
            if ink_coverage_line is not None:
                ink_coverage = sum(map(float, ink_coverage_line.groups()))

                if ink_coverage < remove_blank_threshold:
                    print(f"    Page {page}: delete (ink coverage: {ink_coverage:.2f}%)")
                else:
                    picked_pages += str(page)
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
        print(f"  WARNING: '{command[0]}' executable not found. Skipping PDF manipulation.")
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
    gm_opts = []
    if os.environ.get("USE_JPEG_COMPRESSION", "false") == "true":
        gm_opts += GM_COMPRESSED_JPEG_SETTINGS
    execute_command(
        log, ["gm", "convert", *gm_opts, *input_files, tmp_output_pdf_file], check=True
    )

    if remove_blank_threshold:
        remove_blank_pages(log, tmp_output_pdf_file, remove_blank_threshold)

    move_across_mounts(tmp_output_pdf_file, output_pdf_file)

    notify(log, output_pdf_file, f"{job_name}.pdf ({side}) scanned")

    # Cleanup temporary files
    print(f"  {side} side: cleaning up for {job_name}...")
    subprocess.run(
        f"rm -rf '{job_dir}' {tempfile.gettempdir()}/brscan_jpeg_*",
        shell=True,
        check=True,
        stdout=log,
        stderr=log,
    )

    # Check for OCR environment variables
    ocr_server = os.getenv("OCR_SERVER")
    ocr_port = os.getenv("OCR_PORT")
    ocr_path = os.getenv("OCR_PATH")

    if not any([ocr_server, ocr_port, ocr_path]):
        print(f"  {side} side: OCR environment variables not set, skipping OCR.")
    else:
        ocr_pdf_name = f"{job_name}-ocr.pdf"
        ocr_pdf_path = os.path.join(SCAN_DIR, ocr_pdf_name)

        # Perform OCR in the background
        print(f"  {side} side: starting OCR for {job_name}...")
        execute_command(
            log,
            [
                "curl",
                "-F",
                "userfile=@${output_pdf_file}",
                "-H",
                "Expect:",
                "-o",
                ocr_pdf_path,
                f"{ocr_server}:{ocr_port}/{ocr_path}",
            ],
            check=True,
        )

        notify(log, ocr_pdf_name, f"{ocr_pdf_name} ({side}) OCR finished")

        ftp_user = os.getenv("FTP_USER")
        ftp_password = os.getenv("FTP_PASSWORD")
        ftp_host = os.getenv("FTP_HOST")
        ftp_path = os.getenv("FTP_PATH")
        sendtoftps(log, ftp_user, ftp_password, ftp_host, ftp_path, ocr_pdf_path)

    if os.getenv("REMOVE_ORIGINAL_AFTER_OCR") == "true" and os.path.isfile(
        ocr_pdf_path
    ):
        os.remove(output_pdf_file)

    print(f"  {side} side: Conversion and post-processing for finished.")
    print("-----------------------------------")


def wait_for_rear_pages_or_convert(job_name: str) -> None:
    # Wait for 2 minutes in case there is a rear side scan
    print(f"  front side: Waiting for 2 minutes before starting file conversion for {job_name}")
    time.sleep(120)

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
            print(f"  rear side: Read pid from {path}, killing front processing job {pid}")
            os.kill(pid, signal.SIGKILL)
    except FileNotFoundError:
        print("  rear side: ERROR: scan_pid file {path} not found.")
    except ProcessLookupError:
        print("  rear side: ERROR: process with pid {pid} not found.")
    else:
        os.remove(path)
        return pid

    return None


#
# Scan entry points
#
def scan_front(log: TextIO, device: Optional[str], scanimage_args=[]) -> None:
    # Generate unique timestamp
    job_name = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    job_dir = os.path.join(tempfile.gettempdir(), job_name)
    filepath_base = os.path.join(job_dir, f"{job_name}-front-page")
    tmp_output_batch = f"{filepath_base}%04d.pnm"

    # Create temporary directory
    os.makedirs(job_dir, exist_ok=True)
    os.chdir(job_dir)
    print(f"- Scanning front to batch {tmp_output_batch}")

    # Save scanimage_args in a file for use with future rear side scans
    save_scanimage_args(job_dir, scanimage_args)

    # Perform scan with retry
    time.sleep(0.1)
    scan_cmd(log, device, tmp_output_batch, scanimage_args)
    if not os.path.exists(f"{filepath_base}0001.pnm"):
        time.sleep(1)  # Short delay before retry
        scan_cmd(log, device, tmp_output_batch, scanimage_args)

    # Run conversion process in the background
    pid = os.fork()
    if pid == 0:  # Child process
        wait_for_rear_pages_or_convert(job_name)
        os._exit(0)  # Exit child process cleanly
    elif pid > 0:
        save_front_processing_pid(job_dir, pid)
        print(f"  front side: INFO: Waiting to start conversion process for {job_name} in process with PID {pid}")
    else:
        print(f"  front side: ERROR: Fork failed ({pid}).")


def scan_rear(log: TextIO, device: Optional[str], scanimage_args=None) -> None:
    # Find latest directory in temp directory
    job_name = latest_batch_dir()
    print(f"- Scanning rear to latest batch {job_name}")
    if job_name is None:
        print("  rear side: ERROR: Could not find front scan directory")
        return

    print(f"  rear side: Found front-side batch: {job_name}")
    job_dir = os.path.join(tempfile.gettempdir(), job_name)
    filepath_base = os.path.join(job_dir, f"{job_name}-back-page")
    tmp_output_batch = f"{filepath_base}%04d.pnm"

    os.chdir(job_dir)

    # Interrupt front scanning process which is waiting from a rear side scan
    if kill_front_processing_from_pid(job_dir) is None:
        return

    if scanimage_args is None:
        # Read scanimage_args used for front scanning
        scanimage_args = read_scanimage_args(job_dir)

    # Perform scan with retry
    time.sleep(0.1)
    scan_cmd(log, device, tmp_output_batch, scanimage_args)
    if not os.path.exists(f"{filepath_base}0001.pnm"):
        time.sleep(1)  # Short delay before retry
        scan_cmd(log, device, tmp_output_batch, scanimage_args)

    # Rename pages
    number_of_pages = len(
        [f for f in os.listdir(".") if (os.path.isfile(f) and "front-page" in f)]
    )
    print(f"  rear side: INFO: number of pages scanned: {number_of_pages}")

    cnt = 0
    for filename in glob.glob("*front*.pnm"):
        cnt += 1
        cnt_formatted = f"{cnt:03d}"
        os.rename(filename, f"index{cnt_formatted}-1-{filename}")
        print(f"  rear side: DEBUG: renamed {filename} to index{cnt_formatted}-1-{filename}")

    cnt = 0
    for filename in glob.glob("*back*.pnm"):
        cnt += 1
        rear_index = number_of_pages - cnt + 1
        rear_index_formatted = f"{rear_index:03d}"
        os.rename(filename, f"index{rear_index_formatted}-2-{filename}")
        print(f"  rear side: DEBUG: renamed {filename} to index{rear_index_formatted}-2-{filename}")

    # Convert to PDF
    remove_blank_threshold_str = os.getenv("REMOVE_BLANK_THRESHOLD")
    remove_blank_threshold = None
    if remove_blank_threshold_str is not None and remove_blank_threshold_str != "":
        remove_blank_threshold = float(remove_blank_threshold_str)

    pid = os.fork()
    if pid == 0:  # Child process
        convert_and_post_process(job_name, "rear", remove_blank_threshold)
        os._exit(0)  # Exit child process cleanly

    elif pid < 0:
        print(f"  rear side: ERROR: Fork failed ({pid}).")
