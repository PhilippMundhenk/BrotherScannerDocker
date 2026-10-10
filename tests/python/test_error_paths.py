"""Error and edge paths that the main tests do not reach (#126)."""
import io
import os
import subprocess
import sys
import time
from datetime import datetime

import pytest

import jobstate
import ocr_queue
import scanner
import trigger_inotify as inotify_module


class FakeProcess:
    def __init__(self, output=b"", returncode=0):
        self._output = output
        self.returncode = returncode

    def communicate(self):
        return self._output, b""


# --- scanner.py: subprocess helpers

def test_execute_command_and_pid(monkeypatch, tmp_path):
    runs = []
    monkeypatch.setattr(scanner.subprocess, "run", lambda cmd, **kw: runs.append(cmd))
    log = io.StringIO()
    scanner.execute_command(log, ["true"], check=True)
    assert runs == [["true"]]

    class P:
        pid = 4321
    monkeypatch.setattr(scanner.subprocess, "Popen", lambda *a, **kw: P())
    assert scanner.execute_command_pid(log, ["sleep", "1"]) == 4321


def test_pdf_page_count_and_ink_coverage_via_subprocess(monkeypatch):
    monkeypatch.setattr(scanner.subprocess, "Popen", lambda *a, **kw: FakeProcess(b"Pages: 3\n"))
    assert scanner.pdf_page_count(io.StringIO(), "x.pdf") == 3
    monkeypatch.setattr(scanner.subprocess, "Popen", lambda *a, **kw: FakeProcess(b"", returncode=1))
    assert scanner.pdf_page_count(io.StringIO(), "x.pdf") is None
    monkeypatch.setattr(scanner.subprocess, "Popen", lambda *a, **kw: FakeProcess(b" 0.1 0.2 0.3 0.4 CMYK OK\n"))
    assert scanner.page_ink_coverage(io.StringIO(), "x.pdf", 1) == pytest.approx(1.0)
    assert scanner.parse_ink_coverage("a b c d CMYK") is None


def test_remove_blank_pages_error_branches(tmp_path, monkeypatch):
    pdf = tmp_path / "in.pdf"
    pdf.write_text("%PDF-1.4")
    log = io.StringIO()
    # page count unknown
    monkeypatch.setattr(scanner, "pdf_page_count", lambda l, p: None)
    scanner.remove_blank_pages(log, str(pdf), 0.3)
    # pdftk missing
    monkeypatch.setattr(scanner, "pdf_page_count", lambda l, p: 1)
    monkeypatch.setattr(scanner, "page_ink_coverage", lambda l, p, n: 0.0)

    def missing(log, command, **kw):
        raise FileNotFoundError(command[0])
    monkeypatch.setattr(scanner, "execute_command", missing)
    scanner.remove_blank_pages(log, str(pdf), 0.3)
    # pdftk fails
    def failing(log, command, **kw):
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(scanner, "execute_command", failing)
    scanner.remove_blank_pages(log, str(pdf), 0.3)
    assert pdf.read_text() == "%PDF-1.4", "input untouched on every error path"


def test_notify_calls_both_triggers(monkeypatch, clean_env):
    seen = []
    monkeypatch.setattr(scanner, "trigger_inotify", lambda log, *a: seen.append(("inotify", a)))
    monkeypatch.setattr(scanner, "trigger_telegram", lambda log, msg, *a: seen.append(("telegram", msg)))
    clean_env.setenv("SSH_USER", "u")
    scanner.notify(io.StringIO(), "/scans/x.pdf", "x.pdf scanned")
    assert seen[0] == ("inotify", ("u", None, None, None, "/scans/x.pdf"))
    assert seen[1] == ("telegram", "Scanner: x.pdf scanned")


def test_latest_batch_dir_picks_newest_of_today(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))
    assert scanner.latest_batch_dir() is None
    prefix = datetime.today().strftime("%Y-%m-%d")
    old = tmp_path / f"{prefix}-01-00-00"
    new = tmp_path / f"{prefix}-02-00-00"
    old.mkdir()
    time.sleep(0.05)
    new.mkdir()
    (tmp_path / f"{prefix}-03-00-00.txt").write_text("not a dir")
    assert scanner.latest_batch_dir() == new.name


def test_move_across_mounts_reports_errors(tmp_path, capsys):
    scanner.move_across_mounts(str(tmp_path / "missing.pdf"), str(tmp_path / "out.pdf"))
    assert "ERROR: moving file" in capsys.readouterr().out
    src = tmp_path / "a.pdf"
    src.write_text("x")
    scanner.move_across_mounts(str(src), str(tmp_path / "b.pdf"))
    assert not src.exists() and (tmp_path / "b.pdf").read_text() == "x"


def test_scanimage_args_roundtrip_and_missing(tmp_path, capsys):
    scanner.save_scanimage_args(str(tmp_path), ["--mode=True Gray", "--x"])
    assert scanner.read_scanimage_args(str(tmp_path)) == ["--mode=True Gray", "--x"]
    assert scanner.read_scanimage_args(str(tmp_path)) == []
    assert "not found" in capsys.readouterr().out


def test_kill_front_processing_error_paths(tmp_path, capsys):
    assert scanner.kill_front_processing_from_pid(str(tmp_path)) is None
    assert "not found" in capsys.readouterr().out
    scanner.save_front_processing_pid(str(tmp_path), 2 ** 22 + 12345)  # no such process
    assert scanner.kill_front_processing_from_pid(str(tmp_path)) is None
    assert "process with pid" in capsys.readouterr().out


def test_scan_front_retry_fork_failure_and_child(tmp_path, monkeypatch, clean_env):
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(scanner.time, "sleep", lambda s: None)
    attempts = []

    def scan_second_time(log, device, batch, args):
        attempts.append(1)
        if len(attempts) == 2:
            with open(batch % 1, "wb") as handle:
                handle.write(b"P5 1 1 255 \x00")

    monkeypatch.setattr(scanner, "scan_cmd", scan_second_time)
    monkeypatch.setattr(os, "fork", lambda: -1)
    scanner.scan_front(io.StringIO(), None, job_name="2026-10-10-11-11-11")
    assert len(attempts) == 2, "retried once when the first attempt produced no page"

    # child branch: runs the wait and exits via os._exit
    attempts.clear()
    waited = []
    monkeypatch.setattr(scanner, "wait_for_rear_pages_or_convert", lambda job: waited.append(job))

    class Exit(Exception):
        pass

    def fake_exit(code):
        raise Exit()
    monkeypatch.setattr(os, "fork", lambda: 0)
    monkeypatch.setattr(os, "_exit", fake_exit)
    with pytest.raises(Exit):
        scanner.scan_front(io.StringIO(), None, job_name="2026-10-10-11-11-12")
    assert waited == ["2026-10-10-11-11-12"]


def test_scan_back_without_any_job_and_child_branch(tmp_path, monkeypatch, clean_env, capsys):
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))
    scanner.scan_back(io.StringIO(), None)
    assert "Could not find front scan directory" in capsys.readouterr().out

    job = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    job_dir = tmp_path / job
    job_dir.mkdir()
    (job_dir / f"{job}-front-page0001.pnm").write_bytes(b"P5 1 1 255 \x00")
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        scanner.save_front_processing_pid(str(job_dir), child.pid)
        monkeypatch.setattr(scanner.time, "sleep", lambda s: None)
        monkeypatch.setattr(scanner, "scan_cmd", lambda log, d, batch, a: open(batch % 1, "wb").write(b"P5 1 1 255 \x00"))
        clean_env.setenv("REMOVE_BLANK_THRESHOLD", "0.3")
        converted = []
        monkeypatch.setattr(scanner, "convert_and_post_process", lambda *a: converted.append(a))

        class Exit(Exception):
            pass
        monkeypatch.setattr(os, "fork", lambda: 0)
        monkeypatch.setattr(os, "_exit", lambda code: (_ for _ in ()).throw(Exit()))
        with pytest.raises(Exit):
            scanner.scan_back(io.StringIO(), None, job_name=job)
        assert converted == [(job, "rear", 0.3)]
    finally:
        if child.poll() is None:
            child.kill()
        child.wait()


def test_scan_back_fork_failure(tmp_path, monkeypatch, clean_env, capsys):
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))
    job = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    job_dir = tmp_path / job
    job_dir.mkdir()
    (job_dir / f"{job}-front-page0001.pnm").write_bytes(b"P5 1 1 255 \x00")
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        scanner.save_front_processing_pid(str(job_dir), child.pid)
        monkeypatch.setattr(scanner.time, "sleep", lambda s: None)
        attempts = []

        def scan(log, d, batch, a):
            attempts.append(1)
            if len(attempts) == 2:
                open(batch % 1, "wb").write(b"P5 1 1 255 \x00")
        monkeypatch.setattr(scanner, "scan_cmd", scan)
        monkeypatch.setattr(os, "fork", lambda: -1)
        scanner.scan_back(io.StringIO(), None, job_name=job)
        assert "Fork failed" in capsys.readouterr().out and len(attempts) == 2
    finally:
        if child.poll() is None:
            child.kill()
        child.wait()


def test_convert_rear_side_and_blank_removal_hook(tmp_path, monkeypatch, clean_env):
    job = "2026-10-10-12-12-12"
    job_dir = tmp_path / job
    job_dir.mkdir()
    (job_dir / "index001-1-x.pnm").write_bytes(b"P5 1 1 255 \x00")
    (job_dir / "index001-2-y.pnm").write_bytes(b"P5 1 1 255 \x00")
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(scanner, "SCAN_DIR", str(scans))
    monkeypatch.setattr(scanner, "execute_command", lambda log, c, **k: open(c[-1], "w").close())
    monkeypatch.setattr(scanner, "notify", lambda *a, **k: None)
    monkeypatch.setattr(scanner, "sendtoftps", lambda *a, **k: None)
    removed = []
    monkeypatch.setattr(scanner, "remove_blank_pages", lambda log, path, t: removed.append((path, t)))
    scanner.convert_and_post_process(job, "rear", 0.3)
    assert removed and removed[0][1] == 0.3
    assert (scans / f"{job}.pdf").is_file()


def test_read_environment_without_tzset(monkeypatch, tmp_path):
    env_file = tmp_path / "env.txt"
    env_file.write_text("X_TEST=1\n")
    monkeypatch.setattr(scanner, "ENVIRONMENT_FILE_PATH", str(env_file))
    monkeypatch.setattr(scanner, "LOCKED_KEYS_PATH", str(tmp_path / "none"))
    monkeypatch.delattr(scanner.time, "tzset", raising=False)
    scanner.read_environment()
    assert os.environ["X_TEST"] == "1"


# --- ocr_queue.py

def test_recover_ignores_rename_errors(tmp_path, monkeypatch, clean_env):
    clean_env.setenv("OCR_QUEUE_DIR", str(tmp_path / "q"))
    dirs = ocr_queue.ensure_dirs()
    ocr_queue.write_job(os.path.join(dirs["in_progress"], "0-x-front.job"), {"PDF": "x"})
    monkeypatch.setattr(os, "rename", lambda a, b: (_ for _ in ()).throw(OSError("busy")))
    assert ocr_queue.recover() == 0


def test_pdf_page_count_subprocess_paths(monkeypatch):
    monkeypatch.setattr(ocr_queue.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="Pages: 4\n"))
    assert ocr_queue.pdf_page_count("x.pdf") == 4
    monkeypatch.setattr(ocr_queue.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, stdout=""))
    assert ocr_queue.pdf_page_count("x.pdf") is None
    monkeypatch.setattr(ocr_queue.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="no pages"))
    assert ocr_queue.pdf_page_count("x.pdf") is None

    def boom(*a, **k):
        raise OSError("no pdfinfo")
    monkeypatch.setattr(ocr_queue.subprocess, "run", boom)
    assert ocr_queue.pdf_page_count("x.pdf") is None


def test_keep_invalid_response_falls_back_to_removal(tmp_path, monkeypatch, clean_env):
    clean_env.setenv("OCR_QUEUE_DIR", str(tmp_path / "q"))
    part = tmp_path / "x.part"
    part.write_text("garbage")
    monkeypatch.setattr(os, "replace", lambda a, b: (_ for _ in ()).throw(OSError("read-only")))
    assert ocr_queue.keep_invalid_response(str(part), {"DATE": "d", "ATTEMPTS": "1"}, None) is None
    assert not part.exists()


def test_process_job_rejects_malformed_and_cleans_failed_upload(tmp_path, clean_env):
    clean_env.setenv("OCR_SERVER", "s")
    clean_env.setenv("OCR_PORT", "1")
    clean_env.setenv("OCR_PATH", "p")
    clean_env.setenv("OCR_OUTPUT_DIR", str(tmp_path))
    assert ocr_queue.process_job({"PDF": "", "DATE": ""}) is False
    source = tmp_path / "s.pdf"
    source.write_text("%PDF-1.4")

    def run_leaving_partial(command, **kw):
        open(command[command.index("-o") + 1], "w").write("partial")
        return subprocess.CompletedProcess(command, 22)
    assert ocr_queue.process_job({"PDF": str(source), "DATE": "s", "SUFFIX": "front"}, run=run_leaving_partial, count_pages=lambda p: 1) is False
    assert not (tmp_path / "s-ocr.pdf.part").exists()


def test_remove_original_failure_is_logged(tmp_path, monkeypatch, clean_env, capsys):
    clean_env.setenv("OCR_SERVER", "s")
    clean_env.setenv("OCR_PORT", "1")
    clean_env.setenv("OCR_PATH", "p")
    clean_env.setenv("OCR_OUTPUT_DIR", str(tmp_path))
    clean_env.setenv("REMOVE_ORIGINAL_AFTER_OCR", "true")
    source = tmp_path / "s.pdf"
    source.write_text("%PDF-1.4")

    def run_ok(command, **kw):
        open(command[command.index("-o") + 1], "w").write("%PDF-1.4 ocr")
        return subprocess.CompletedProcess(command, 0)
    real_remove = os.remove
    monkeypatch.setattr(os, "remove", lambda p: (_ for _ in ()).throw(OSError("locked")) if p == str(source) else real_remove(p))
    assert ocr_queue.process_job({"PDF": str(source), "DATE": "s", "SUFFIX": "front"}, run=run_ok, count_pages=lambda p: 1) is True
    assert "could not remove original" in capsys.readouterr().out


def test_worker_claim_race_and_refresh(tmp_path, clean_env, monkeypatch):
    clean_env.setenv("OCR_QUEUE_DIR", str(tmp_path / "q"))
    clean_env.setenv("OCR_SERVER", "s")
    clean_env.setenv("OCR_PORT", "1")
    clean_env.setenv("OCR_PATH", "p")
    clean_env.setenv("OCR_OUTPUT_DIR", str(tmp_path))
    source = tmp_path / "s.pdf"
    source.write_text("%PDF-1.4")
    ocr_queue.enqueue(str(source), "s", "front")
    real_rename = os.rename
    state = {"failed_once": False}

    def flaky_rename(a, b):
        if not state["failed_once"] and "in_progress" in b:
            state["failed_once"] = True
            raise OSError("claimed elsewhere")
        return real_rename(a, b)
    monkeypatch.setattr(os, "rename", flaky_rename)
    refreshed = []

    def run_ok(command, **kw):
        open(command[command.index("-o") + 1], "w").write("%PDF-1.4 ocr")
        return subprocess.CompletedProcess(command, 0)
    ocr_queue.run_worker(once=True, sleep=lambda s: None, run=run_ok, count_pages=lambda p: 1,
                         refresh=lambda: refreshed.append(1))
    assert state["failed_once"] and refreshed == [1]
    assert (tmp_path / "s-ocr.pdf").exists()


def test_worker_polls_when_idle_then_returns(tmp_path, clean_env):
    clean_env.setenv("OCR_QUEUE_DIR", str(tmp_path / "q"))
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        raise KeyboardInterrupt  # end the endless loop
    with pytest.raises(KeyboardInterrupt):
        ocr_queue.run_worker(poll_seconds=3, sleep=sleep)
    assert slept == [3]


def test_main_worker_and_usage(monkeypatch, capsys):
    monkeypatch.setattr(scanner, "read_environment", lambda: None)
    started = []
    monkeypatch.setattr(ocr_queue, "run_worker", lambda refresh=None: started.append(refresh))
    assert ocr_queue.main(["ocr_queue.py", "worker"]) == 0
    assert started and callable(started[0])
    assert ocr_queue.main(["ocr_queue.py", "bogus"]) == 2
    assert "OCR upload queue" in capsys.readouterr().out


def test_upload_uses_run_result(monkeypatch, tmp_path):
    assert ocr_queue.upload("/a.pdf", str(tmp_path / "o"), "u", run=lambda c, **k: subprocess.CompletedProcess(c, 0)) is True
    assert ocr_queue.upload("/a.pdf", str(tmp_path / "o"), "u", run=lambda c, **k: subprocess.CompletedProcess(c, 7)) is False


# --- jobstate.py

def test_list_and_prune_skip_unreadable(tmp_path, monkeypatch):
    monkeypatch.setenv("SCANNER_JOBS_DIR", str(tmp_path))
    (tmp_path / "2026-01-01-00-00-00.json").write_text("not json")
    jobstate.update("2026-01-02-00-00-00", state="done")
    assert [j["job"] for j in jobstate.list_jobs()] == ["2026-01-02-00-00-00"]
    monkeypatch.setattr(os, "remove", lambda p: (_ for _ in ()).throw(OSError("busy")))
    old = time.time() - 30 * 86400
    for p in tmp_path.glob("*.json"):
        os.utime(p, (old, old))
    assert jobstate.prune(max_age_days=7) == 0


# --- trigger_inotify.py

def test_inotify_os_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("no sshpass")
    monkeypatch.setattr(inotify_module.subprocess, "run", boom)
    assert inotify_module.trigger_inotify(io.StringIO(), "u", "p", "h", "/r", "f.pdf") is False


def test_main_worker_without_environment_file(monkeypatch, tmp_path):
    monkeypatch.setattr(scanner, "ENVIRONMENT_FILE_PATH", str(tmp_path / "missing"))
    started = []
    monkeypatch.setattr(ocr_queue, "run_worker", lambda refresh=None: started.append(refresh))
    assert ocr_queue.main(["ocr_queue.py", "worker"]) == 0
    assert started == [None]


def test_inotify_success(monkeypatch):
    monkeypatch.setattr(inotify_module.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0))
    assert inotify_module.trigger_inotify(io.StringIO(), "u", "p", "h", "/r", "f.pdf") is True
