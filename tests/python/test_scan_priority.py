"""Scanning has priority over OCR: uploads wait for an idle scanner and can be rate limited (#107)."""
import os
import subprocess
import time

import ocr_queue


def test_scanner_busy_reads_fresh_marker_only(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_queue.tempfile, "gettempdir", lambda: str(tmp_path))
    assert ocr_queue.scanner_busy() is False
    marker = tmp_path / "STATUS_SCAN"
    marker.write_text("scan")
    assert ocr_queue.scanner_busy() is True
    old = time.time() - 2 * ocr_queue.SCAN_STATUS_MAX_AGE
    os.utime(marker, (old, old))
    assert ocr_queue.scanner_busy() is False, "a stale marker from a crashed scan must not block uploads forever"


def test_wait_for_idle_scanner_blocks_until_idle(clean_env, capsys):
    states = iter([True, True, True, False])
    slept = []
    waited = ocr_queue.wait_for_idle_scanner(sleep=slept.append, poll=2.0, busy=lambda: next(states))
    assert slept == [2.0, 2.0, 2.0]
    assert waited == 6.0
    assert capsys.readouterr().out.count("holding OCR upload") == 1, "announced once, not on every poll"


def test_wait_for_idle_scanner_gives_up_after_max_wait(clean_env):
    slept = []
    waited = ocr_queue.wait_for_idle_scanner(sleep=slept.append, poll=5.0, max_wait=12.0, busy=lambda: True)
    assert waited == 15.0 and len(slept) == 3


def test_wait_for_idle_scanner_can_be_disabled(clean_env):
    clean_env.setenv("OCR_WAIT_FOR_IDLE_SCANNER", "false")
    slept = []
    assert ocr_queue.wait_for_idle_scanner(sleep=slept.append, busy=lambda: True) == 0.0
    assert slept == []


def test_process_job_waits_before_uploading(tmp_path, clean_env, monkeypatch):
    monkeypatch.setattr(ocr_queue.tempfile, "gettempdir", lambda: str(tmp_path))
    clean_env.setenv("OCR_SERVER", "ocr.local")
    clean_env.setenv("OCR_PORT", "80")
    clean_env.setenv("OCR_PATH", "ocr.php")
    clean_env.setenv("OCR_OUTPUT_DIR", str(tmp_path))
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF-1.4 x")
    marker = tmp_path / "STATUS_SCAN"
    marker.write_text("scan")
    order = []

    def sleep(seconds):
        order.append(("sleep", seconds))
        marker.unlink(missing_ok=True)  # the scan finishes while we wait

    def run(command, **kwargs):
        order.append(("curl", command))
        with open(command[command.index("-o") + 1], "wb") as handle:
            handle.write(b"%PDF-1.4 ocr")
        return subprocess.CompletedProcess(command, 0)

    ok = ocr_queue.process_job({"PDF": str(source), "DATE": "job", "SUFFIX": "front", "ATTEMPTS": "1"},
                               run=run, count_pages=lambda p: 1, sleep=sleep)
    assert ok is True
    assert order[0][0] == "sleep" and order[1][0] == "curl", "upload only after the scanner went idle"


def test_upload_rate_limit_from_env(clean_env, tmp_path):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    ocr_queue.upload("/scans/a.pdf", str(tmp_path / "out"), "ocr.local:80/ocr.php", run=run)
    assert "--limit-rate" not in calls[0]
    clean_env.setenv("OCR_UPLOAD_LIMIT_RATE", "2M")
    ocr_queue.upload("/scans/a.pdf", str(tmp_path / "out"), "ocr.local:80/ocr.php", run=run)
    assert calls[1][calls[1].index("--limit-rate") + 1] == "2M"
    assert calls[1].index("--limit-rate") < calls[1].index("-F"), "option precedes the upload arguments"
