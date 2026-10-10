import os
import sys

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT_DIR = os.path.join(REPO_ROOT, "script")
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


@pytest.fixture
def clean_env(monkeypatch):
    """Unset every variable the pipeline reads so tests start from nothing."""
    for name in [
        "OCR_SERVER", "OCR_PORT", "OCR_PATH", "OCR_QUEUE_DIR", "OCR_OUTPUT_DIR",
        "OCR_QUEUE_POLL_SECONDS", "OCR_MAX_ATTEMPTS", "OCR_RETRY_BACKOFF_SECONDS",
        "SSH_USER", "SSH_PASSWORD", "SSH_HOST", "SSH_PATH",
        "FTP_USER", "FTP_PASSWORD", "FTP_HOST", "FTP_PATH",
        "TELEGRAM_TOKEN", "TELEGRAM_CHATID", "REMOVE_ORIGINAL_AFTER_OCR",
        "REMOVE_BLANK_THRESHOLD", "RESOLUTION", "USE_JPEG_COMPRESSION",
        "REAR_PAGE_WAIT_SECONDS", "SCAN_MODE", "SCAN_SOURCE",
        "SCAN_LEFT_MM", "SCAN_TOP_MM", "SCAN_WIDTH_MM", "SCAN_HEIGHT_MM", "SCANNER_JOBS_DIR",
    ]:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch
