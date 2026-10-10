import io
import os
import subprocess
import sys
from datetime import datetime

import scanner


class SpyLog(io.StringIO):
    """Log that knows whether it holds unflushed output."""

    def __init__(self):
        super().__init__()
        self.dirty = False
        self.flushes = 0

    def write(self, s):
        self.dirty = True
        return super().write(s)

    def flush(self):
        self.dirty = False
        self.flushes += 1
        super().flush()


def fake_scan(log, device, batch, args):
    with open(batch % 1, "wb") as handle:
        handle.write(b"P5 1 1 255 \x00")


def install_spy(monkeypatch):
    # Must happen inside the test body: pytest re-installs its own capture on
    # sys.stdout when the call phase starts, which would undo a fixture's patch.
    spy = SpyLog()
    monkeypatch.setattr(sys, "stdout", spy)
    return spy


def test_scan_front_flushes_before_fork(tmp_path, monkeypatch, clean_env):
    """#112: output printed before os.fork() must not be duplicated by the child."""
    spy = install_spy(monkeypatch)
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(scanner, "scan_cmd", fake_scan)
    seen = {}

    def fork_spy():
        seen["dirty_at_fork"] = spy.dirty
        seen["written_before_fork"] = spy.getvalue()
        return 4242  # pretend to be the parent

    monkeypatch.setattr(os, "fork", fork_spy)
    scanner.scan_front(spy, None)
    assert "Scanning front to batch" in seen["written_before_fork"], "spy must actually receive the output"
    assert seen["dirty_at_fork"] is False, "log buffer must be flushed right before fork"


def test_scan_back_flushes_before_fork(tmp_path, monkeypatch, clean_env):
    spy = install_spy(monkeypatch)
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))
    job_name = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    job_dir = tmp_path / job_name
    job_dir.mkdir()
    (job_dir / f"{job_name}-front-page0001.pnm").write_bytes(b"P5 1 1 255 \x00")
    scanner.save_scanimage_args(str(job_dir), [])
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        scanner.save_front_processing_pid(str(job_dir), child.pid)
        monkeypatch.setattr(scanner, "scan_cmd", fake_scan)
        seen = {}

        def fork_spy():
            seen["dirty_at_fork"] = spy.dirty
            return 4242

        monkeypatch.setattr(os, "fork", fork_spy)
        scanner.scan_back(spy, None)
        assert spy.getvalue().count("renamed") == 2, "the two rename lines are printed exactly once"
        assert seen["dirty_at_fork"] is False
    finally:
        if child.poll() is None:
            child.kill()
        child.wait()
