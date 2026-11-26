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


def pgm(pixels, width, height, header_extra=b"", maxval=255):
    return b"P5\n" + header_extra + f"{width} {height}\n{maxval}\n".encode() + bytes(pixels)


def test_parse_dark_coverage_counts_pixels_below_the_cutoff():
    assert scanner.parse_dark_coverage(pgm([255] * 100, 10, 10)) == 0.0
    assert scanner.parse_dark_coverage(pgm([0] * 100, 10, 10)) == 100.0
    half = [0] * 50 + [255] * 50
    assert scanner.parse_dark_coverage(pgm(half, 10, 10)) == pytest.approx(50.0)
    # the cutoff itself counts as paper
    assert scanner.parse_dark_coverage(pgm([160] * 10 + [159] * 10, 10, 2), 160) == pytest.approx(50.0)


def test_parse_dark_coverage_ignores_paper_tint():
    """Regression: a tinted, noisy blank page used to score ~9% ink."""
    tinted = [235, 238, 230, 242] * 25
    assert scanner.parse_dark_coverage(pgm(tinted, 10, 10)) == 0.0


def test_parse_dark_coverage_accepts_header_comments():
    data = pgm([0, 255], 2, 1, header_extra=b"# Ghostscript\n")
    assert scanner.parse_dark_coverage(data) == pytest.approx(50.0)


@pytest.mark.parametrize(
    "data",
    [
        b"nothing useful",
        b"",
        b"P6\n1 1\n255\n\x00\x00\x00",  # colour PGM variant, not supported
        pgm([0], 1, 1, maxval=65535),
        b"P5\n0 0\n255\n",
        b"P5\n10 10\n255\n\x00\x00",  # truncated pixel data
    ],
)
def test_parse_dark_coverage_rejects_unusable_input(data):
    assert scanner.parse_dark_coverage(data) is None


def test_parse_page_count():
    assert scanner.parse_page_count("Title: x\nPages: 12\nFile size: 1 bytes\n") == 12
    assert scanner.parse_page_count("no pages here") is None


def test_remove_blank_pages_keeps_pages_above_threshold_including_two_digit_pages(tmp_path, monkeypatch):
    """Regression: pages >= 10 used to be split into single digits ('1', '0')."""
    pdf = tmp_path / "in.pdf"
    pdf.write_text("%PDF-1.4")
    coverage = {page: (0.0 if page in (2, 11) else 0.9) for page in range(1, 13)}
    monkeypatch.setattr(scanner, "pdf_page_count", lambda log, path: 12)
    monkeypatch.setattr(scanner, "page_dark_coverage", lambda log, path, page: coverage[page])
    commands = []

    def fake_execute(log, command, **kwargs):
        commands.append(command)
        # qpdf would write the output file; emulate that so the replace step runs
        with open(command[-1], "w") as handle:
            handle.write("%PDF-1.4 noblank")

    monkeypatch.setattr(scanner, "execute_command", fake_execute)
    scanner.remove_blank_pages(io.StringIO(), str(pdf), 0.3)
    qpdf = commands[0]
    assert qpdf[:4] == ["/usr/bin/qpdf", str(pdf), "--pages", "."]
    assert qpdf[-2] == "--"
    pages = qpdf[4].split(",")
    assert pages == ["1", "3", "4", "5", "6", "7", "8", "9", "10", "12"]
    assert pdf.read_text() == "%PDF-1.4 noblank", "cleaned file replaces the input"


def test_remove_blank_pages_leaves_file_when_nothing_is_blank(tmp_path, monkeypatch):
    pdf = tmp_path / "in.pdf"
    pdf.write_text("%PDF-1.4 original")
    monkeypatch.setattr(scanner, "pdf_page_count", lambda log, path: 2)
    monkeypatch.setattr(scanner, "page_dark_coverage", lambda log, path, page: 1.0)
    monkeypatch.setattr(scanner, "execute_command", lambda *a, **kw: pytest.fail("no rewrite needed"))
    scanner.remove_blank_pages(io.StringIO(), str(pdf), 0.3)
    assert pdf.read_text() == "%PDF-1.4 original"


def test_remove_blank_pages_keeps_original_when_all_pages_are_blank(tmp_path, monkeypatch):
    pdf = tmp_path / "in.pdf"
    pdf.write_text("%PDF-1.4 original")
    monkeypatch.setattr(scanner, "pdf_page_count", lambda log, path: 2)
    monkeypatch.setattr(scanner, "page_dark_coverage", lambda log, path, page: 0.0)
    monkeypatch.setattr(scanner, "execute_command", lambda *a, **kw: pytest.fail("must not write an empty PDF"))
    scanner.remove_blank_pages(io.StringIO(), str(pdf), 0.3)
    assert pdf.read_text() == "%PDF-1.4 original"


def test_remove_blank_pages_keeps_unknown_coverage_and_spaces_in_paths(tmp_path, monkeypatch):
    pdf = tmp_path / "scan with spaces.pdf"
    pdf.write_text("%PDF-1.4 original")
    monkeypatch.setattr(scanner, "pdf_page_count", lambda log, path: 3)
    monkeypatch.setattr(scanner, "page_dark_coverage", lambda log, path, page: {1: None, 2: 0.0, 3: 0.9}[page])
    commands = []

    def fake_execute(log, command, **kwargs):
        commands.append(command)
        with open(command[-1], "w") as handle:
            handle.write("%PDF-1.4 selected")

    monkeypatch.setattr(scanner, "execute_command", fake_execute)
    scanner.remove_blank_pages(io.StringIO(), str(pdf), 0.3)
    assert commands[0][1] == str(pdf)
    assert commands[0][4] == "1,3"
    assert pdf.read_text() == "%PDF-1.4 selected"


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
