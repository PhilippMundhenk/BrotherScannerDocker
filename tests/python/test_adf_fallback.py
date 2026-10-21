"""ADF-empty fallback to the flatbed (#180).

brscan5 aborts a scan with "Document feeder out of documents" when the ADF is
empty, where brscan4 silently used the flatbed. scanner.scan_cmd retries once
from the flatbed when no source was chosen, nothing was scanned, and the device
has a flatbed.
"""
import io
import subprocess

import pytest

import scanner


# --- helpers ---------------------------------------------------------------

def test_device_has_flatbed_reads_the_capabilities(tmp_path):
    caps = tmp_path / "caps"
    caps.write_text("    --source FlatBed|Automatic Document Feeder(left aligned)\n")
    assert scanner.device_has_flatbed(str(caps)) is True
    caps.write_text("    --source Automatic Document Feeder(left aligned)\n")
    assert scanner.device_has_flatbed(str(caps)) is False
    assert scanner.device_has_flatbed(str(tmp_path / "missing")) is False


def test_source_was_requested(clean_env):
    assert scanner.source_was_requested([]) is False
    assert scanner.source_was_requested(["--source=FlatBed"]) is True
    clean_env.setenv("SCAN_SOURCE", "FlatBed")
    assert scanner.source_was_requested([]) is True


def test_adf_empty_from_start_distinguishes_jam_from_no_docs():
    assert scanner.adf_empty_from_start("sane_start: Document feeder out of documents") is True
    assert scanner.adf_empty_from_start("my_sane_read SANE_STATUS_NO_DOCS; page = 0") is True
    assert scanner.adf_empty_from_start("sane_start: Document feeder jammed") is False
    assert scanner.adf_empty_from_start("") is False


def test_with_flatbed_source_replaces_any_source_before_resolution():
    cmd = ["scanimage", "--source=Automatic Document Feeder(left aligned)", "--resolution=300", "--batch=x%04d.pnm"]
    out = scanner.with_flatbed_source(cmd)
    assert "--source=Automatic Document Feeder(left aligned)" not in out
    assert "--source=FlatBed" in out
    assert out.index("--source=FlatBed") < out.index("--resolution=300")


# --- execute_command capture -----------------------------------------------

def test_execute_command_capture_returns_and_logs_output():
    log = io.StringIO()
    out = scanner.execute_command(log, ["sh", "-c", "printf hello"], capture=True)
    assert "hello" in out
    assert "hello" in log.getvalue()


def test_execute_command_capture_raises_with_output_on_failure():
    log = io.StringIO()
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        scanner.execute_command(log, ["sh", "-c", "echo boom; exit 3"], check=True, capture=True)
    assert "boom" in (excinfo.value.output or "")


# --- scan_cmd retry --------------------------------------------------------

def _raise(output):
    def fake(log, cmd, **kwargs):
        fake.calls.append(cmd)
        if len(fake.calls) == 1:
            raise subprocess.CalledProcessError(1, cmd, output=output)
        return ""
    fake.calls = []
    return fake


def test_scan_cmd_retries_from_flatbed_when_the_feeder_is_empty(monkeypatch, clean_env, tmp_path):
    fake = _raise("scanimage: sane_start: Document feeder out of documents")
    monkeypatch.setattr(scanner, "execute_command", fake)
    monkeypatch.setattr(scanner, "device_has_flatbed", lambda *a: True)
    scanner.scan_cmd(io.StringIO(), None, str(tmp_path / "x%04d.pnm"), [])
    assert len(fake.calls) == 2
    assert not any(a.startswith("--source=") for a in fake.calls[0])
    assert "--source=FlatBed" in fake.calls[1]


def test_scan_cmd_does_not_retry_on_a_paper_jam(monkeypatch, clean_env, tmp_path):
    fake = _raise("scanimage: sane_start: Document feeder jammed")
    monkeypatch.setattr(scanner, "execute_command", fake)
    monkeypatch.setattr(scanner, "device_has_flatbed", lambda *a: True)
    with pytest.raises(subprocess.CalledProcessError):
        scanner.scan_cmd(io.StringIO(), None, str(tmp_path / "x%04d.pnm"), [])
    assert len(fake.calls) == 1


def test_scan_cmd_does_not_retry_when_a_source_was_chosen(monkeypatch, clean_env, tmp_path):
    fake = _raise("Document feeder out of documents")
    monkeypatch.setattr(scanner, "execute_command", fake)
    monkeypatch.setattr(scanner, "device_has_flatbed", lambda *a: True)
    clean_env.setenv("SCAN_SOURCE", "FlatBed")
    with pytest.raises(subprocess.CalledProcessError):
        scanner.scan_cmd(io.StringIO(), None, str(tmp_path / "x%04d.pnm"), [])
    assert len(fake.calls) == 1


def test_scan_cmd_does_not_retry_without_a_flatbed(monkeypatch, clean_env, tmp_path):
    fake = _raise("Document feeder out of documents")
    monkeypatch.setattr(scanner, "execute_command", fake)
    monkeypatch.setattr(scanner, "device_has_flatbed", lambda *a: False)
    with pytest.raises(subprocess.CalledProcessError):
        scanner.scan_cmd(io.StringIO(), None, str(tmp_path / "x%04d.pnm"), [])
    assert len(fake.calls) == 1


def test_scan_cmd_does_not_retry_when_pages_were_already_scanned(monkeypatch, clean_env, tmp_path):
    batch = str(tmp_path / "x%04d.pnm")
    (tmp_path / "x0001.pnm").write_bytes(b"P5 1 1 255 \x00")  # a page already came through
    fake = _raise("Document feeder out of documents")
    monkeypatch.setattr(scanner, "execute_command", fake)
    monkeypatch.setattr(scanner, "device_has_flatbed", lambda *a: True)
    with pytest.raises(subprocess.CalledProcessError):
        scanner.scan_cmd(io.StringIO(), None, batch, [])
    assert len(fake.calls) == 1
