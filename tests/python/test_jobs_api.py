"""Job records and entry point arguments (#101)."""
import io
import json
import os
import time

import pytest

import jobstate
import scanner


@pytest.fixture
def jobs_dir(tmp_path, monkeypatch):
    d = tmp_path / "jobs"
    monkeypatch.setenv("SCANNER_JOBS_DIR", str(d))
    return d


def test_update_creates_readable_record(jobs_dir):
    record = jobstate.update("2026-10-10-19-25-20", state="scanning", action="file")
    path = jobs_dir / "2026-10-10-19-25-20.json"
    assert path.is_file()
    assert oct(path.stat().st_mode & 0o777) == "0o644"
    assert oct(jobs_dir.stat().st_mode & 0o777) == "0o755"
    assert record["state"] == "scanning" and record["created"] and record["updated"]
    assert json.loads(path.read_text())["action"] == "file"
    assert not list(jobs_dir.glob("*.tmp")), "written atomically"


def test_update_merges_and_keeps_created(jobs_dir):
    first = jobstate.update("2026-10-10-19-25-20", state="queued", action="file", params={"RESOLUTION": "200"})
    second = jobstate.update("2026-10-10-19-25-20", state="done", file="2026-10-10-19-25-20.pdf")
    assert second["created"] == first["created"]
    assert second["action"] == "file" and second["params"] == {"RESOLUTION": "200"}
    assert jobstate.read("2026-10-10-19-25-20")["state"] == "done"
    assert jobstate.read("2026-01-01-00-00-00") is None


def test_list_is_newest_first_and_limited(jobs_dir):
    for name in ["2026-10-10-10-00-00", "2026-10-10-12-00-00", "2026-10-10-11-00-00"]:
        jobstate.update(name, state="done")
    names = [j["job"] for j in jobstate.list_jobs()]
    assert names == ["2026-10-10-12-00-00", "2026-10-10-11-00-00", "2026-10-10-10-00-00"]
    assert len(jobstate.list_jobs(limit=2)) == 2


def test_prune_removes_old_records(jobs_dir):
    jobstate.update("2026-01-01-00-00-00", state="done")
    jobstate.update("2026-10-10-00-00-00", state="done")
    old = jobs_dir / "2026-01-01-00-00-00.json"
    stamp = time.time() - 10 * 86400
    os.utime(old, (stamp, stamp))
    assert jobstate.prune(max_age_days=7) == 1
    assert [j["job"] for j in jobstate.list_jobs()] == ["2026-10-10-00-00-00"]


def test_parse_entry_args_device_style_call():
    args = scanner.parse_entry_args(["brother4:net1;dev0", "Scanner"])
    assert args.device == "brother4:net1;dev0" and args.job_id is None
    assert scanner.entry_overrides(args) == {}


def test_parse_entry_args_api_style_call():
    args = scanner.parse_entry_args(["--job-id", "2026-10-10-19-25-20", "--resolution", "200",
                                     "--mode", "True Gray", "--source", "Automatic Document Feeder(left aligned,Duplex)"])
    assert args.device is None and args.job_id == "2026-10-10-19-25-20"
    assert scanner.entry_overrides(args) == {
        "RESOLUTION": "200", "SCAN_MODE": "True Gray", "SCAN_SOURCE": "Automatic Document Feeder(left aligned,Duplex)"}


@pytest.mark.parametrize("argv", [
    ["--job-id", "not-a-job"],
    ["--job-id", "2026-10-10-19-25-20/../x"],
    ["--resolution", "10"],
    ["--resolution", "abc"],
    ["--mode", "True Gray; rm -rf /"],
    ["--source", "x" * 61],
])
def test_parse_entry_args_rejects_bad_values(argv):
    with pytest.raises(SystemExit):
        scanner.parse_entry_args(argv)


def test_apply_overrides_sets_environment(clean_env):
    scanner.apply_overrides({"RESOLUTION": "150", "SCAN_MODE": "Black & White"})
    assert os.environ["RESOLUTION"] == "150" and os.environ["SCAN_MODE"] == "Black & White"


def test_scan_front_records_states(tmp_path, monkeypatch, clean_env, jobs_dir):
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))

    def fake_scan(log, device, batch, args):
        for n in (1, 2):
            with open(batch % n, "wb") as handle:
                handle.write(b"P5 1 1 255 \x00")

    monkeypatch.setattr(scanner, "scan_cmd", fake_scan)
    monkeypatch.setattr(os, "fork", lambda: 4242)
    clean_env.setenv("REAR_PAGE_WAIT_SECONDS", "7")
    scanner.scan_front(io.StringIO(), None, job_name="2026-10-10-19-25-20", action="file",
                       overrides={"RESOLUTION": "200"})
    record = jobstate.read("2026-10-10-19-25-20")
    assert record["state"] == "waiting_for_rear" and record["pages"] == 2
    assert record["action"] == "file" and record["params"] == {"RESOLUTION": "200"}
    assert record["waiting_until"]


def test_scan_front_failure_records_error(tmp_path, monkeypatch, clean_env, jobs_dir):
    import subprocess
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))

    def failing(log, device, batch, args):
        raise subprocess.CalledProcessError(1, ["scanimage"])

    monkeypatch.setattr(scanner, "scan_cmd", failing)
    scanner.scan_front(io.StringIO(), None, job_name="2026-10-10-19-25-21")
    record = jobstate.read("2026-10-10-19-25-21")
    assert record["state"] == "failed" and "cancelled" in record["error"]


def test_scan_back_for_unknown_job_does_nothing(tmp_path, monkeypatch, clean_env, jobs_dir, capsys):
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))
    calls = []
    monkeypatch.setattr(scanner, "scan_cmd", lambda *a: calls.append(a))
    scanner.scan_back(io.StringIO(), None, job_name="2026-10-10-19-25-22")
    assert calls == []
    assert "is not waiting for rear pages" in capsys.readouterr().out


def test_convert_records_done_with_ocr_state(tmp_path, monkeypatch, clean_env, jobs_dir):
    job = "2026-10-10-19-25-23"
    job_dir = tmp_path / job
    job_dir.mkdir()
    (job_dir / f"{job}-front-page0001.pnm").write_bytes(b"P5 1 1 255 \x00")
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(scanner, "SCAN_DIR", str(scans))
    monkeypatch.setattr(scanner, "execute_command", lambda log, c, **k: open(c[-1], "w").close())
    monkeypatch.setattr(scanner, "notify", lambda *a, **k: None)
    monkeypatch.setattr(scanner, "sendtoftps", lambda *a, **k: None)
    monkeypatch.setattr(scanner, "enqueue_ocr", lambda *a: None)
    clean_env.setenv("OCR_SERVER", "ocr.local")
    clean_env.setenv("OCR_PORT", "80")
    clean_env.setenv("OCR_PATH", "ocr.php")
    scanner.convert_and_post_process(job, "front", None)
    record = jobstate.read(job)
    assert record["state"] == "done" and record["file"] == f"{job}.pdf"
    assert record["ocr"] == "queued" and record["ocr_file"] == f"{job}-ocr.pdf"
