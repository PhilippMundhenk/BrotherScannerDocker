import os
import subprocess

import pytest

import ocr_queue

# The validation step asks for page counts; the fake OCR output and the fake
# originals are not real PDFs, so every file counts as one page here.


class FakeRun:
    """Stand-in for subprocess.run that fakes curl: records calls, optionally creates the -o file."""

    def __init__(self, returncode=0, create_output=True):
        self.returncode = returncode
        self.create_output = create_output
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        if self.create_output and self.returncode == 0 and "-o" in command:
            out = command[command.index("-o") + 1]
            with open(out, "w") as handle:
                handle.write("%PDF-1.4 fake ocr output")
        return subprocess.CompletedProcess(command, self.returncode)


@pytest.fixture
def queue(tmp_path, clean_env):
    root = tmp_path / "queue"
    clean_env.setenv("OCR_QUEUE_DIR", str(root))
    scans = tmp_path / "scans"
    scans.mkdir()
    clean_env.setenv("OCR_OUTPUT_DIR", str(scans))
    return root, scans


def ocr_env(monkeypatch):
    monkeypatch.setenv("OCR_SERVER", "ocr.local")
    monkeypatch.setenv("OCR_PORT", "80")
    monkeypatch.setenv("OCR_PATH", "ocr.php")


def pending(root):
    return sorted(p.name for p in (root / "pending").glob("*.job"))


def test_enqueue_writes_job_atomically(queue):
    root, scans = queue
    path = ocr_queue.enqueue("/scans/a.pdf", "2026-05-17-18-00-00", "front")
    assert os.path.isfile(path)
    assert os.path.dirname(path) == str(root / "pending")
    assert ocr_queue.read_job(path) == {
        "PDF": "/scans/a.pdf", "DATE": "2026-05-17-18-00-00", "SUFFIX": "front", "ATTEMPTS": "0"}
    assert not list((root / "pending").glob(".*.tmp")), "temp file must not be left behind"


def test_jobs_sort_in_enqueue_order(queue):
    root, _ = queue
    first = ocr_queue.enqueue("/scans/a.pdf", "a", "front")
    second = ocr_queue.enqueue("/scans/b.pdf", "b", "rear")
    names = pending(root)
    assert names == sorted(names)
    assert names[0] == os.path.basename(first) and names[1] == os.path.basename(second)


def test_recover_moves_in_progress_back_to_pending(queue):
    root, _ = queue
    dirs = ocr_queue.ensure_dirs()
    stranded = os.path.join(dirs["in_progress"], "0000-orphan-front.job")
    ocr_queue.write_job(stranded, {"PDF": "/x.pdf", "DATE": "x", "SUFFIX": "front", "ATTEMPTS": "1"})
    assert ocr_queue.recover() == 1
    assert pending(root) == ["0000-orphan-front.job"]
    assert not os.path.exists(stranded)


def test_successful_upload_removes_job_and_writes_output(queue, clean_env):
    root, scans = queue
    ocr_env(clean_env)
    source = scans / "2026-05-17-test.pdf"
    source.write_text("%PDF-1.4 source")
    ocr_queue.enqueue(str(source), "2026-05-17-test", "front")

    run = FakeRun()
    ocr_queue.run_worker(count_pages=lambda path: 1, once=True, sleep=lambda s: None, run=run)

    assert pending(root) == []
    assert not list((root / "in_progress").glob("*")) and not list((root / "failed").glob("*"))
    assert (scans / "2026-05-17-test-ocr.pdf").is_file()
    assert source.is_file(), "original must be kept unless REMOVE_ORIGINAL_AFTER_OCR"
    curl = run.calls[0]
    assert curl[0] == "curl" and "ocr.local:80/ocr.php" in curl
    assert f"userfile=@{source}" in curl


def test_remove_original_after_ocr(queue, clean_env):
    root, scans = queue
    ocr_env(clean_env)
    clean_env.setenv("REMOVE_ORIGINAL_AFTER_OCR", "true")
    source = scans / "s.pdf"
    source.write_text("%PDF-1.4")
    ocr_queue.enqueue(str(source), "s", "front")
    ocr_queue.run_worker(count_pages=lambda path: 1, once=True, sleep=lambda s: None, run=FakeRun())
    assert not source.exists()
    assert (scans / "s-ocr.pdf").is_file()


def test_repeated_failures_land_in_failed_with_backoff(queue, clean_env):
    root, scans = queue
    ocr_env(clean_env)
    source = scans / "f.pdf"
    source.write_text("%PDF-1.4")
    ocr_queue.enqueue(str(source), "f", "rear")
    slept = []
    ocr_queue.run_worker(count_pages=lambda path: 1, once=True, max_attempts=3, backoff_seconds=10,
                         sleep=slept.append, run=FakeRun(returncode=7))
    failed = list((root / "failed").glob("*.job"))
    assert len(failed) == 1 and pending(root) == []
    assert ocr_queue.read_job(str(failed[0]))["ATTEMPTS"] == "3"
    assert slept == [10, 20], "linear backoff between attempts, none after the final one"
    assert not (scans / "f-ocr.pdf").exists(), "partial output must be removed on failure"


def test_missing_ocr_config_does_not_loop_forever(queue, clean_env):
    root, scans = queue
    source = scans / "n.pdf"
    source.write_text("%PDF-1.4")
    ocr_queue.enqueue(str(source), "n", "front")
    run = FakeRun()
    ocr_queue.run_worker(count_pages=lambda path: 1, once=True, max_attempts=2, backoff_seconds=0, sleep=lambda s: None, run=run)
    assert run.calls == [], "no upload attempted without OCR configuration"
    assert len(list((root / "failed").glob("*.job"))) == 1


def test_missing_input_pdf_lands_in_failed(queue, clean_env):
    root, scans = queue
    ocr_env(clean_env)
    ocr_queue.enqueue(str(scans / "missing.pdf"), "m", "front")
    ocr_queue.run_worker(count_pages=lambda path: 1, once=True, max_attempts=1, backoff_seconds=0, sleep=lambda s: None, run=FakeRun())
    assert len(list((root / "failed").glob("*.job"))) == 1


def test_worker_processes_oldest_first(queue, clean_env):
    root, scans = queue
    ocr_env(clean_env)
    for name in ["a", "b", "c"]:
        (scans / f"{name}.pdf").write_text("%PDF-1.4")
        ocr_queue.enqueue(str(scans / f"{name}.pdf"), name, "front")
    run = FakeRun()
    ocr_queue.run_worker(count_pages=lambda path: 1, once=True, sleep=lambda s: None, run=run)
    uploaded = [c[c.index("-F") + 1] for c in run.calls]
    assert uploaded == [f"userfile=@{scans / n}.pdf" for n in ["a", "b", "c"]]


def test_cli_enqueue(queue, capsys):
    root, _ = queue
    assert ocr_queue.main(["ocr_queue.py", "enqueue", "/scans/x.pdf", "x", "front"]) == 0
    assert len(pending(root)) == 1
    assert ocr_queue.main(["ocr_queue.py"]) == 2
