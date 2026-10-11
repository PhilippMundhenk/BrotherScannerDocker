#!/usr/bin/env python3
"""Thumbnails of the first page for the file list of the web UI (#130, #143).

A thumbnail is a landscape crop of the top third of the first page, 640 x 302
pixels, cached on the volume as

    /scans/.thumbnails/<file name>.<mtime>.jpg

The web server renders a missing thumbnail on request (file-thumbnail.php uses
the same layout and the same pdftoppm call). This module renders them ahead of
time, as the scan user: right after a scan or an OCR result lands in /scans,
and in a sweep over the existing scans when the container starts. That way the
drawer rarely waits for a render, and a volume that only the scan user may
write to (NFS with uid mapping, CIFS with uid=) works as well.

Usage:
    thumbnails.py sweep [--pause SECONDS]   render missing thumbnails, drop orphans
    thumbnails.py render <pdf>              render one thumbnail
"""

import argparse
import glob
import os
import subprocess
import sys
import tempfile
import time
from typing import Callable, List, Optional, Tuple

SCAN_DIR = "/scans"
THUMB_DIR = "/scans/.thumbnails"
WIDTH = 640
HEIGHT = 302  # top third of an A4 page at 640 px width (640 * 1.414 / 3)
PDFTOPPM = [
    "pdftoppm", "-f", "1", "-l", "1",
    "-scale-to-x", str(WIDTH), "-scale-to-y", "-1",
    "-x", "0", "-y", "0", "-W", str(WIDTH), "-H", str(HEIGHT),
    "-jpeg", "-jpegopt", "quality=70", "-singlefile",
]
RENDER_TIMEOUT = 60
SCAN_STATUS_MAX_AGE = 600


def enabled(env=None) -> bool:
    """GUI_THUMBNAILS, as the web UI reads it: anything but false/0/no/off is on."""
    env = os.environ if env is None else env
    return env.get("GUI_THUMBNAILS", "true").strip().lower() not in ("false", "0", "no", "off")


def in_scan_dir(path: str, scan_dir: Optional[str] = None) -> bool:
    """True when the file is listed by the web UI, i.e. lies directly in the scan directory."""
    scan_dir = SCAN_DIR if scan_dir is None else scan_dir
    return os.path.dirname(os.path.abspath(path)) == os.path.abspath(scan_dir)


def thumbnail_path(pdf_path: str, thumb_dir: str = THUMB_DIR) -> str:
    """Cache file of a scan: <name>.<mtime>.jpg, so a changed file gets a new thumbnail."""
    mtime = int(os.stat(pdf_path).st_mtime)
    return os.path.join(thumb_dir, f"{os.path.basename(pdf_path)}.{mtime}.jpg")


def forget(pdf_path: str, thumb_dir: str = THUMB_DIR) -> int:
    """Remove the cached thumbnails of a file (every version). Returns how many went."""
    removed = 0
    pattern = os.path.join(thumb_dir, glob.escape(os.path.basename(pdf_path)) + ".*.jpg")
    for old in glob.glob(pattern):
        try:
            os.remove(old)
            removed += 1
        except OSError:
            pass
    return removed


def render(
    pdf_path: str,
    thumb_dir: str = THUMB_DIR,
    run: Optional[Callable] = None,
    log: Callable[[str], None] = print,
) -> Optional[str]:
    """Render the thumbnail of a PDF unless it is cached already. Returns the cache file, None on failure."""
    run = subprocess.run if run is None else run
    try:
        target = thumbnail_path(pdf_path, thumb_dir)
        if os.path.isfile(target) and os.path.getsize(target) > 0:
            return target
        os.makedirs(thumb_dir, exist_ok=True)
        forget(pdf_path, thumb_dir)  # a miss: only outdated versions can exist
        tmp_base = os.path.join(thumb_dir, f".{os.path.basename(pdf_path)}.{os.getpid()}")
        tmp = tmp_base + ".jpg"
        result = run([*PDFTOPPM, pdf_path, tmp_base], capture_output=True, text=True, timeout=RENDER_TIMEOUT)
        if result.returncode != 0 or not os.path.isfile(tmp) or os.path.getsize(tmp) == 0:
            detail = (result.stderr or result.stdout or "").strip().splitlines()
            log(f"thumbnail failed for {pdf_path}: " + (detail[-1] if detail else f"exit status {result.returncode}"))
            if os.path.exists(tmp):
                os.remove(tmp)
            return None
        os.replace(tmp, target)
        os.chmod(target, 0o664)
        return target
    except (OSError, subprocess.SubprocessError) as error:
        log(f"thumbnail failed for {pdf_path}: {error}")
        return None


def scanner_busy(max_age: float = SCAN_STATUS_MAX_AGE) -> bool:
    """True while scanner.py marks a scan in progress (STATUS_SCAN in the temp dir, see ocr_queue.py)."""
    marker = os.path.join(tempfile.gettempdir(), "STATUS_SCAN")
    try:
        return (time.time() - os.path.getmtime(marker)) < max_age
    except OSError:
        return False


def listed_pdfs(scan_dir: str = SCAN_DIR) -> List[str]:
    """The PDFs the file list shows, newest first."""
    pdfs = [p for p in glob.glob(os.path.join(scan_dir, "*.pdf")) if os.path.isfile(p) and not os.path.basename(p).startswith(".")]
    pdfs.sort(key=lambda p: os.stat(p).st_mtime, reverse=True)
    return pdfs


def sweep(
    scan_dir: str = SCAN_DIR,
    thumb_dir: str = THUMB_DIR,
    run: Optional[Callable] = None,
    log: Callable[[str], None] = print,
    pause: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
    busy: Callable[[], bool] = scanner_busy,
) -> Tuple[int, int, int]:
    """Render every missing thumbnail (newest scans first) and remove thumbnails of files that are gone.

    Waits while a scan is running so the sweep never competes with it. Returns
    (rendered, failed, removed).
    """
    rendered = failed = removed = 0
    wanted = set()
    for pdf in listed_pdfs(scan_dir):
        try:
            target = thumbnail_path(pdf, thumb_dir)
        except OSError:
            continue  # vanished meanwhile
        wanted.add(os.path.basename(target))
        if os.path.isfile(target) and os.path.getsize(target) > 0:
            continue
        while busy():
            sleep(5)
        if render(pdf, thumb_dir, run=run, log=log):
            rendered += 1
        else:
            failed += 1
        if pause:
            sleep(pause)
    if os.path.isdir(thumb_dir):
        for name in os.listdir(thumb_dir):
            if name.startswith(".") or not name.endswith(".jpg") or name in wanted:
                continue
            try:
                os.remove(os.path.join(thumb_dir, name))
                removed += 1
            except OSError:
                pass
    return rendered, failed, removed


def main(argv: List[str], log: Callable[[str], None] = print) -> int:
    parser = argparse.ArgumentParser(description="thumbnails of the first page for the file list")
    sub = parser.add_subparsers(dest="command", required=True)
    p_sweep = sub.add_parser("sweep", help="render missing thumbnails of all scans, drop orphans")
    p_sweep.add_argument("--scan-dir", default=SCAN_DIR)
    p_sweep.add_argument("--thumb-dir", default=THUMB_DIR)
    p_sweep.add_argument("--pause", type=float, default=0.0, help="seconds to wait between two renders")
    p_render = sub.add_parser("render", help="render the thumbnail of one PDF")
    p_render.add_argument("pdf")
    p_render.add_argument("--thumb-dir", default=THUMB_DIR)
    args = parser.parse_args(argv)

    if args.command == "render":
        target = render(args.pdf, args.thumb_dir, log=log)
        if target:
            log(target)
        return 0 if target else 1

    started = time.time()
    rendered, failed, removed = sweep(args.scan_dir, args.thumb_dir, log=log, pause=args.pause)
    log(f"thumbnail sweep finished: {rendered} rendered, {failed} failed, {removed} orphans removed "
        f"in {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
