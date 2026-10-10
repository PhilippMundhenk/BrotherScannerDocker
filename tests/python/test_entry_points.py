"""The scanto*.py entry points: argument handling and dispatch, with the log redirected to a temp file."""
import importlib
import sys

import pytest


@pytest.fixture
def entry(monkeypatch, tmp_path):
    """Import an entry module fresh and stub what it calls."""
    def load(name):
        module = importlib.import_module(name)
        importlib.reload(module)
        calls = {}
        if hasattr(module, "read_environment"):
            monkeypatch.setattr(module, "read_environment", lambda: calls.__setitem__("env", calls.get("env", 0) + 1))
        if hasattr(module, "scan_front"):
            monkeypatch.setattr(module, "scan_front", lambda log, device, *a, **kw: calls.__setitem__("front", (device, a, kw)))
        if hasattr(module, "scan_back"):
            monkeypatch.setattr(module, "scan_back", lambda log, device, *a, **kw: calls.__setitem__("back", (device, a, kw)))
        return module, calls
    yield load
    sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__


def test_scantofile_device_call(entry, tmp_path):
    module, calls = entry("scantofile")
    module.main(["brother4:net1;dev0", "Scanner"], log_path=str(tmp_path / "log"))
    device, args, kwargs = calls["front"]
    assert device == "brother4:net1;dev0" and kwargs["job_name"] is None and kwargs["action"] == "file"
    assert kwargs["overrides"] == {}
    assert calls["env"] == 1


def test_scantofile_api_call_with_overrides(entry, tmp_path, clean_env):
    module, calls = entry("scantofile")
    module.main(["--job-id", "2026-10-10-10-10-10", "--resolution", "200", "--mode", "True Gray"], log_path=str(tmp_path / "log"))
    device, args, kwargs = calls["front"]
    assert device is None and kwargs["job_name"] == "2026-10-10-10-10-10"
    assert kwargs["overrides"] == {"RESOLUTION": "200", "SCAN_MODE": "True Gray"}
    import os
    assert os.environ["RESOLUTION"] == "200"


def test_scantoocr_gray_by_default_but_not_when_mode_given(entry, tmp_path, clean_env):
    module, calls = entry("scantoocr")
    module.main([], log_path=str(tmp_path / "log"))
    device, args, kwargs = calls["front"]
    assert args[0] == ["--mode=True Gray"] and kwargs["action"] == "ocr"
    module.main(["--mode", "24bit Color[Fast]"], log_path=str(tmp_path / "log"))
    assert calls["front"][1][0] == []


def test_scantoocr_respects_scan_mode_env(entry, tmp_path, clean_env):
    clean_env.setenv("SCAN_MODE", "Black & White")
    module, calls = entry("scantoocr")
    module.main([], log_path=str(tmp_path / "log"))
    assert calls["front"][1][0] == []


def test_scantoemail_passes_job_id(entry, tmp_path):
    module, calls = entry("scantoemail")
    module.main(["--job-id", "2026-10-10-10-10-10"], log_path=str(tmp_path / "log"))
    device, args, kwargs = calls["back"]
    assert device is None and kwargs["job_name"] == "2026-10-10-10-10-10"
    module.main(["brother4:net1;dev0", "Scanner"], log_path=str(tmp_path / "log"))
    assert calls["back"][0] == "brother4:net1;dev0" and calls["back"][2]["job_name"] is None


def test_scantoimage_logs_not_implemented(entry, tmp_path):
    module, calls = entry("scantoimage")
    log = tmp_path / "log"
    module.main([], log_path=str(log))
    text = log.read_text()
    assert "ERROR!" in text and "not implemented" in text


def test_entry_point_log_goes_to_the_log_file(entry, tmp_path):
    module, calls = entry("scantofile")
    log = tmp_path / "log"
    module.main([], log_path=str(log))
    assert log.exists()
