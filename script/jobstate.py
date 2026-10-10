#!/usr/bin/env python3
"""Job state records for scans, so the API can report progress.

Every scan is a job named by its timestamp (the same name the PDF gets). The
scan scripts write one small JSON file per job into the jobs directory
(SCANNER_JOBS_DIR, default <tempdir>/scanner-jobs); the web backend reads
them for GET /api/jobs and GET /api/jobs/<id>.

States, in order of a normal life:
    queued            script started, nothing scanned yet
    scanning          scanimage is running (front pages)
    waiting_for_rear  front pages scanned, waiting REAR_PAGE_WAIT_SECONDS for
                      a rear scan
    scanning_rear     a rear scan took the job over
    converting        pages are being converted and post-processed
    done              PDF is in /scans (field "file"); "ocr" tells whether an
                      OCR copy was queued
    failed            scanning was cancelled (field "error")

Files are written atomically and are world-readable; the directory is
created with mode 755 so the web server user can list it.
"""

import glob
import json
import os
import tempfile
import time
from typing import Any, Dict, List, Optional

MAX_AGE_DAYS = 7


def jobs_dir() -> str:
    return os.environ.get("SCANNER_JOBS_DIR") or os.path.join(tempfile.gettempdir(), "scanner-jobs")


def job_path(job_name: str) -> str:
    return os.path.join(jobs_dir(), f"{job_name}.json")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def read(job_name: str) -> Optional[Dict[str, Any]]:
    try:
        with open(job_path(job_name), "r") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def update(job_name: str, **fields: Any) -> Dict[str, Any]:
    """Merge fields into the job's record (creating it) and write it atomically."""
    directory = jobs_dir()
    os.makedirs(directory, mode=0o755, exist_ok=True)
    record = read(job_name) or {"job": job_name, "created": now_iso()}
    record.update(fields)
    record["updated"] = now_iso()
    path = job_path(job_name)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as handle:
        json.dump(record, handle, sort_keys=True)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)
    return record


def list_jobs(limit: int = 50) -> List[Dict[str, Any]]:
    """Newest jobs first (job names are timestamps, so the name sorts them)."""
    paths = sorted(glob.glob(os.path.join(jobs_dir(), "*.json")), reverse=True)
    jobs: List[Dict[str, Any]] = []
    for path in paths[: max(0, limit)]:
        try:
            with open(path, "r") as handle:
                jobs.append(json.load(handle))
        except (OSError, ValueError):
            continue
    return jobs


def prune(max_age_days: float = MAX_AGE_DAYS) -> int:
    """Remove records older than max_age_days. Returns the number removed."""
    cutoff = time.time() - max_age_days * 86400
    removed = 0
    for path in glob.glob(os.path.join(jobs_dir(), "*.json")):
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed += 1
        except OSError:
            continue
    return removed
