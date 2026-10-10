import io
import os

import pytest

import scanner


def test_read_environment_handles_values_with_equals_and_blank_lines(tmp_path, monkeypatch):
    env_file = tmp_path / "env.txt"
    env_file.write_text(
        "# comment\n"
        "OCR_PATH=ocr.php?mode=fast&x=1\n"
        "\n"
        "RENAME_GUI_SCANTOFILE=Scan front pages\n"
        "EMPTY=\n"
    )
    monkeypatch.setattr(scanner, "ENVIRONMENT_FILE_PATH", str(env_file))
    for name in ["OCR_PATH", "RENAME_GUI_SCANTOFILE", "EMPTY"]:
        monkeypatch.delenv(name, raising=False)
    scanner.read_environment()
    assert os.environ["OCR_PATH"] == "ocr.php?mode=fast&x=1"
    assert os.environ["RENAME_GUI_SCANTOFILE"] == "Scan front pages"
    assert os.environ["EMPTY"] == ""


def test_parse_ink_coverage():
    gs_output = "GPL Ghostscript\n 0.00000  0.00000  0.00000  0.51230 CMYK OK\n"
    assert scanner.parse_ink_coverage(gs_output) == pytest.approx(0.5123)
    assert scanner.parse_ink_coverage("nothing useful") is None


def test_parse_page_count():
    assert scanner.parse_page_count("Title: x\nPages: 12\nFile size: 1 bytes\n") == 12
    assert scanner.parse_page_count("no pages here") is None


def test_remove_blank_pages_keeps_pages_above_threshold_including_two_digit_pages(tmp_path, monkeypatch):
    """Regression: pages >= 10 used to be split into single digits ('1', '0')."""
    pdf = tmp_path / "in.pdf"
    pdf.write_text("%PDF-1.4")
    coverage = {page: (0.0 if page in (2, 11) else 0.9) for page in range(1, 13)}
    monkeypatch.setattr(scanner, "pdf_page_count", lambda log, path: 12)
    monkeypatch.setattr(scanner, "page_ink_coverage", lambda log, path, page: coverage[page])
    commands = []

    def fake_execute(log, command, **kwargs):
        commands.append(command)
        # pdftk would write the output file; emulate that so the replace step runs
        with open(command[-1], "w") as handle:
            handle.write("%PDF-1.4 noblank")

    monkeypatch.setattr(scanner, "execute_command", fake_execute)
    scanner.remove_blank_pages(io.StringIO(), str(pdf), 0.3)
    pdftk = commands[0]
    assert pdftk[0].endswith("pdftk")
    pages = pdftk[pdftk.index("cat") + 1:pdftk.index("output")]
    assert pages == ["1", "3", "4", "5", "6", "7", "8", "9", "10", "12"]
    assert pdf.read_text() == "%PDF-1.4 noblank", "cleaned file replaces the input"


def test_remove_blank_pages_leaves_file_when_nothing_is_blank(tmp_path, monkeypatch):
    pdf = tmp_path / "in.pdf"
    pdf.write_text("%PDF-1.4 original")
    monkeypatch.setattr(scanner, "pdf_page_count", lambda log, path: 2)
    monkeypatch.setattr(scanner, "page_ink_coverage", lambda log, path, page: 1.0)
    monkeypatch.setattr(scanner, "execute_command", lambda log, command, **kw: open(command[-1], "w").close())
    scanner.remove_blank_pages(io.StringIO(), str(pdf), 0.3)
    assert pdf.read_text() == "%PDF-1.4 original"


def test_rear_page_wait_is_configurable(monkeypatch, clean_env):
    slept = []
    monkeypatch.setattr(scanner.time, "sleep", slept.append)
    monkeypatch.setattr(scanner, "convert_and_post_process", lambda *a, **k: None)
    scanner.wait_for_rear_pages_or_convert("job")
    assert slept == [120]
    clean_env.setenv("REAR_PAGE_WAIT_SECONDS", "3")
    slept.clear()
    scanner.wait_for_rear_pages_or_convert("job")
    assert slept == [3]


def test_waiting_status_is_cleared_after_wait(monkeypatch, tmp_path, clean_env):
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(scanner.time, "sleep", lambda s: None)
    monkeypatch.setattr(scanner, "convert_and_post_process", lambda *a, **k: None)
    scanner.wait_for_rear_pages_or_convert("job")
    assert not (tmp_path / "STATUS_WAITING").exists()


def test_convert_enqueues_ocr_instead_of_uploading(tmp_path, monkeypatch, clean_env):
    """The pipeline hands OCR to the queue; it must not call curl itself."""
    job = "2026-05-17-10-00-00"
    job_dir = tmp_path / job
    job_dir.mkdir()
    (job_dir / f"{job}-front-page0001.pnm").write_bytes(b"P5 1 1 255 \x00")
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(scanner, "SCAN_DIR", str(scans))
    clean_env.setenv("OCR_SERVER", "ocr.local")
    clean_env.setenv("OCR_PORT", "80")
    clean_env.setenv("OCR_PATH", "ocr.php")
    clean_env.setenv("FTP_USER", "u")
    clean_env.setenv("FTP_PASSWORD", "p")
    clean_env.setenv("FTP_HOST", "h")
    clean_env.setenv("FTP_PATH", "/up/")

    commands = []

    def fake_execute(log, command, **kwargs):
        commands.append(command)
        if command[:2] == ["gm", "convert"]:
            open(command[-1], "w").close()

    monkeypatch.setattr(scanner, "execute_command", fake_execute)
    queued = []
    monkeypatch.setattr(scanner, "enqueue_ocr", lambda pdf, name, side: queued.append((pdf, name, side)))
    ftp = []
    monkeypatch.setattr(scanner, "sendtoftps", lambda log, *args: ftp.append(args))
    monkeypatch.setattr(scanner, "notify", lambda *a, **k: None)

    scanner.convert_and_post_process(job, "front", None)

    assert [c[:2] for c in commands] == [["gm", "convert"]], "no curl from the pipeline"
    assert queued == [(str(scans / f"{job}.pdf"), job, "front")]
    assert ftp == [("u", "p", "h", "/up/", str(scans / f"{job}.pdf"))], "plain scan is uploaded to FTP"
    assert (scans / f"{job}.pdf").is_file()
    assert not job_dir.exists(), "job directory is cleaned up"


def test_convert_skips_ocr_without_configuration(tmp_path, monkeypatch, clean_env):
    job = "2026-05-17-11-00-00"
    job_dir = tmp_path / job
    job_dir.mkdir()
    (job_dir / f"{job}-front-page0001.pnm").write_bytes(b"P5 1 1 255 \x00")
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(scanner, "SCAN_DIR", str(scans))
    monkeypatch.setattr(scanner, "execute_command", lambda log, command, **kw: open(command[-1], "w").close())
    queued = []
    monkeypatch.setattr(scanner, "enqueue_ocr", lambda *a: queued.append(a))
    monkeypatch.setattr(scanner, "notify", lambda *a, **k: None)
    scanner.convert_and_post_process(job, "front", None)
    assert queued == []
