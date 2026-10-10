"""The worker marks when it holds an upload back for a busy scanner (#125)."""
import os

import ocr_queue


def test_hold_marker_exists_only_while_holding(tmp_path, monkeypatch, clean_env):
    monkeypatch.setattr(ocr_queue.tempfile, "gettempdir", lambda: str(tmp_path))
    marker = tmp_path / "STATUS_OCR_HOLD"
    seen = []
    states = iter([True, True, False])

    def sleep(seconds):
        seen.append(marker.exists())

    ocr_queue.wait_for_idle_scanner(sleep=sleep, poll=1.0, busy=lambda: next(states))
    assert seen == [True, True], "marker present during the wait"
    assert not marker.exists(), "marker removed once the scanner is idle"


def test_no_marker_when_scanner_is_idle(tmp_path, monkeypatch, clean_env):
    monkeypatch.setattr(ocr_queue.tempfile, "gettempdir", lambda: str(tmp_path))
    ocr_queue.wait_for_idle_scanner(sleep=lambda s: None, busy=lambda: False)
    assert not (tmp_path / "STATUS_OCR_HOLD").exists()


def test_marker_removed_even_when_max_wait_hits(tmp_path, monkeypatch, clean_env):
    monkeypatch.setattr(ocr_queue.tempfile, "gettempdir", lambda: str(tmp_path))
    ocr_queue.wait_for_idle_scanner(sleep=lambda s: None, poll=5.0, max_wait=10.0, busy=lambda: True)
    assert not (tmp_path / "STATUS_OCR_HOLD").exists()
