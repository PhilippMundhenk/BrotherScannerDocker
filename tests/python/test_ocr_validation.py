"""The OCR result must be validated before it replaces anything, and the original
scan may only be removed after a validated result is in place."""
import os
import subprocess

import pytest

import ocr_queue


class FakeOcr:
    """Fake curl: writes `body` to the -o path (or nothing when body is None)."""

    def __init__(self, body=b"%PDF-1.4 fake ocr output", returncode=0):
        self.body = body
        self.returncode = returncode
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        if self.returncode == 0 and "-o" in command and self.body is not None:
            with open(command[command.index("-o") + 1], "wb") as handle:
                handle.write(self.body)
        return subprocess.CompletedProcess(command, self.returncode)


def pages_by_header(path):
    """Fake pdfinfo: page count encoded in the fake PDF body, None for non-PDFs."""
    with open(path, "rb") as handle:
        head = handle.read(64)
    if not head.startswith(b"%PDF-"):
        return None
    for token in head.split():
        if token.startswith(b"pages="):
            return int(token[6:])
    return 1


@pytest.fixture
def setup(tmp_path, clean_env):
    root = tmp_path / "queue"
    scans = tmp_path / "scans"
    scans.mkdir()
    clean_env.setenv("OCR_QUEUE_DIR", str(root))
    clean_env.setenv("OCR_OUTPUT_DIR", str(scans))
    clean_env.setenv("OCR_SERVER", "ocr.local")
    clean_env.setenv("OCR_PORT", "80")
    clean_env.setenv("OCR_PATH", "ocr.php")
    clean_env.setenv("REMOVE_ORIGINAL_AFTER_OCR", "true")
    source = scans / "2026-10-10-17-25-20.pdf"
    source.write_bytes(b"%PDF-1.4 pages=2 original")
    ocr_queue.enqueue(str(source), "2026-10-10-17-25-20", "front")
    return root, scans, source


def drain(fake, max_attempts=2):
    ocr_queue.run_worker(once=True, max_attempts=max_attempts, backoff_seconds=0,
                         sleep=lambda s: None, run=fake, count_pages=pages_by_header)


def failed_files(root):
    return sorted(p.name for p in (root / "failed").iterdir())


def test_valid_result_replaces_original(setup):
    root, scans, source = setup
    drain(FakeOcr(b"%PDF-1.4 pages=2 ocr"))
    assert (scans / "2026-10-10-17-25-20-ocr.pdf").read_bytes() == b"%PDF-1.4 pages=2 ocr"
    assert not source.exists(), "original removed only after a valid result"
    assert not list(scans.glob("*.part"))
    assert failed_files(root) == []


def test_text_error_with_http_200_keeps_original(setup):
    """The microservice answers 200 with 'Error: File not found.' when tesseract fails."""
    root, scans, source = setup
    drain(FakeOcr(b"Error: File not found."))
    assert source.exists(), "original must never be deleted for an invalid result"
    assert not (scans / "2026-10-10-17-25-20-ocr.pdf").exists()
    assert not list(scans.glob("*.part"))
    names = failed_files(root)
    assert any(n.endswith(".job") for n in names), "job parked in failed/ after max attempts"
    responses = [n for n in names if ".response-" in n]
    assert len(responses) == 2, "every invalid response is kept for inspection"
    assert (root / "failed" / responses[0]).read_bytes() == b"Error: File not found."


def test_empty_body_keeps_original(setup):
    root, scans, source = setup
    drain(FakeOcr(b""))
    assert source.exists()
    assert not (scans / "2026-10-10-17-25-20-ocr.pdf").exists()


def test_page_count_mismatch_keeps_original(setup):
    root, scans, source = setup
    drain(FakeOcr(b"%PDF-1.4 pages=1 truncated"))
    assert source.exists()
    assert not (scans / "2026-10-10-17-25-20-ocr.pdf").exists()
    assert any(".response-" in n for n in failed_files(root))


def test_unparseable_pdf_keeps_original(setup):
    root, scans, source = setup

    def never_parses(path):
        return 2 if path.endswith("2026-10-10-17-25-20.pdf") else None

    ocr_queue.run_worker(once=True, max_attempts=1, backoff_seconds=0, sleep=lambda s: None,
                         run=FakeOcr(b"%PDF-1.4 broken"), count_pages=never_parses)
    assert source.exists()
    assert not (scans / "2026-10-10-17-25-20-ocr.pdf").exists()


def test_no_removal_when_flag_not_true(setup, clean_env):
    root, scans, source = setup
    clean_env.setenv("REMOVE_ORIGINAL_AFTER_OCR", "false")
    drain(FakeOcr(b"%PDF-1.4 pages=2 ocr"))
    assert source.exists()
    assert (scans / "2026-10-10-17-25-20-ocr.pdf").exists()


def test_unknown_original_page_count_still_requires_a_pdf(setup):
    root, scans, source = setup

    def unknown_for_original(path):
        return None if path == str(source) else 3

    ocr_queue.run_worker(once=True, max_attempts=1, backoff_seconds=0, sleep=lambda s: None,
                         run=FakeOcr(b"Error: File not found."), count_pages=unknown_for_original)
    assert source.exists()
    ocr_queue.enqueue(str(source), "2026-10-10-17-25-20", "front")
    ocr_queue.run_worker(once=True, max_attempts=1, backoff_seconds=0, sleep=lambda s: None,
                         run=FakeOcr(b"%PDF-1.4 pages=3 ocr"), count_pages=unknown_for_original)
    assert (scans / "2026-10-10-17-25-20-ocr.pdf").exists(), "page count comparison is skipped when unknown"


def test_validate_pdf_reasons(tmp_path):
    missing = tmp_path / "missing.pdf"
    assert ocr_queue.validate_pdf(str(missing), 1, count_pages=lambda p: 1)[0] is False
    empty = tmp_path / "empty.pdf"
    empty.write_bytes(b"")
    assert ocr_queue.validate_pdf(str(empty), 1, count_pages=lambda p: 1) == (False, "empty file")
    text = tmp_path / "text.pdf"
    text.write_bytes(b"Error: File not found.")
    ok, reason = ocr_queue.validate_pdf(str(text), 1, count_pages=lambda p: 1)
    assert ok is False and "not a PDF" in reason
    pdf = tmp_path / "ok.pdf"
    pdf.write_bytes(b"%PDF-1.4 x")
    assert ocr_queue.validate_pdf(str(pdf), 2, count_pages=lambda p: 2)[0] is True
    assert ocr_queue.validate_pdf(str(pdf), 2, count_pages=lambda p: 1) == (False, "1 pages, original has 2")
    assert ocr_queue.validate_pdf(str(pdf), 2, count_pages=lambda p: None) == (False, "pdfinfo cannot read it")


def test_pdf_page_count_with_real_pdfinfo(tmp_path):
    """Uses pdfinfo when available (the image has poppler-utils); skipped elsewhere."""
    import shutil
    if shutil.which("pdfinfo") is None:
        pytest.skip("pdfinfo not installed")
    sample = os.path.join(os.path.dirname(__file__), "..", "e2e", "fixtures", "sample.pdf")
    assert ocr_queue.pdf_page_count(sample) == 1
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"Error: File not found.")
    assert ocr_queue.pdf_page_count(str(bad)) is None
