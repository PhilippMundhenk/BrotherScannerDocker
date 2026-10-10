import io
import os
import subprocess
import sys
from datetime import datetime

import pytest

import scanner


@pytest.fixture
def front_job(tmp_path, monkeypatch, clean_env):
    """A front scan that is 'waiting for rear pages': job dir, pid file of a live child, waiting status."""
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))
    job_name = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    job_dir = tmp_path / job_name
    job_dir.mkdir()
    (job_dir / f"{job_name}-front-page0001.pnm").write_bytes(b"P5 1 1 255 \x00")
    scanner.save_scanimage_args(str(job_dir), [])
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    scanner.save_front_processing_pid(str(job_dir), child.pid)
    scanner.set_status("waiting")
    yield job_name, job_dir, child
    if child.poll() is None:
        child.kill()
    child.wait()


def test_failed_rear_scan_clears_waiting_state(front_job, monkeypatch, tmp_path):
    """#37: a rear scan that fails must not leave the UI in 'waiting for rear pages'."""
    job_name, job_dir, child = front_job

    def failing_scan(log, device, batch, args):
        raise subprocess.CalledProcessError(1, ["scanimage"])

    monkeypatch.setattr(scanner, "scan_cmd", failing_scan)
    scanner.scan_back(io.StringIO(), None)

    assert not scanner.read_status("waiting")
    assert not scanner.read_status("scan")
    assert not job_dir.exists(), "job files cleaned up after the failed rear scan"
    child.wait(timeout=5)
    assert child.returncode is not None, "front conversion child was stopped"


def test_rear_scan_without_front_process_clears_waiting_state(front_job, monkeypatch):
    job_name, job_dir, child = front_job
    child.kill()
    child.wait()
    calls = []
    monkeypatch.setattr(scanner, "scan_cmd", lambda *a: calls.append(a))
    scanner.scan_back(io.StringIO(), None)
    assert calls == [], "no rear scan when the front job is already gone"
    assert not scanner.read_status("waiting")


def test_successful_rear_scan_clears_waiting_and_converts(front_job, monkeypatch):
    job_name, job_dir, child = front_job

    def fake_scan(log, device, batch, args):
        with open(batch % 1, "wb") as handle:
            handle.write(b"P5 1 1 255 \x00")

    monkeypatch.setattr(scanner, "scan_cmd", fake_scan)
    forked = []
    monkeypatch.setattr(scanner.os, "fork", lambda: forked.append(1) or 4242)
    scanner.scan_back(io.StringIO(), None)
    assert not scanner.read_status("waiting")
    assert forked == [1], "conversion is handed to a child process"
    names = sorted(p.name for p in job_dir.iterdir() if p.suffix == ".pnm")
    assert names == [f"index001-1-{job_name}-front-page0001.pnm", f"index001-2-{job_name}-back-page0001.pnm"]
