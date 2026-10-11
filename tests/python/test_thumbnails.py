"""script/thumbnails.py: ahead-of-time thumbnails for the file list (#143)."""
import os
import subprocess
import time
from types import SimpleNamespace

import pytest

import ocr_queue
import scanner
import thumbnails


def fake_run_ok(command, **kwargs):
    """Stands in for pdftoppm: writes the <base>.jpg it was asked for."""
    with open(command[-1] + ".jpg", "wb") as out:
        out.write(b"\xff\xd8\xff thumbnail")
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def fake_run_fail(command, **kwargs):
    return SimpleNamespace(returncode=1, stdout="", stderr="Syntax Error: Couldn't read xref table\nCommand Line Error: broken")


def make_pdf(directory, name, mtime=None):
    path = directory / name
    path.write_bytes(b"%PDF-1.4 x")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return str(path)


def test_enabled_reads_gui_thumbnails_like_the_web_ui():
    assert thumbnails.enabled({})
    assert thumbnails.enabled({"GUI_THUMBNAILS": "true"})
    assert thumbnails.enabled({"GUI_THUMBNAILS": "yes"})
    for value in ("false", "FALSE", "0", "no", "off", " off "):
        assert not thumbnails.enabled({"GUI_THUMBNAILS": value}), value


def test_in_scan_dir_is_true_only_for_files_directly_in_the_scan_dir(tmp_path):
    assert thumbnails.in_scan_dir(str(tmp_path / "a.pdf"), str(tmp_path))
    assert not thumbnails.in_scan_dir(str(tmp_path / "sub" / "a.pdf"), str(tmp_path))
    assert not thumbnails.in_scan_dir("/elsewhere/a.pdf", str(tmp_path))


def test_thumbnail_path_carries_name_and_mtime(tmp_path):
    pdf = make_pdf(tmp_path, "2026-01-02-03-04-05.pdf", mtime=1700000000)
    assert thumbnails.thumbnail_path(pdf, str(tmp_path / "t")) == str(tmp_path / "t" / "2026-01-02-03-04-05.pdf.1700000000.jpg")


def test_render_writes_the_cache_file_and_drops_older_versions(tmp_path):
    thumb_dir = tmp_path / ".thumbnails"
    thumb_dir.mkdir()
    stale = thumb_dir / "scan.pdf.1.jpg"
    stale.write_bytes(b"old")
    other = thumb_dir / "other.pdf.1.jpg"
    other.write_bytes(b"keep")
    pdf = make_pdf(tmp_path, "scan.pdf", mtime=1700000000)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return fake_run_ok(command, **kwargs)

    target = thumbnails.render(pdf, str(thumb_dir), run=run)
    assert target == str(thumb_dir / "scan.pdf.1700000000.jpg")
    assert os.path.getsize(target) > 0
    assert not stale.exists(), "the thumbnail of the earlier version goes"
    assert other.exists(), "other files are untouched"
    assert calls[0][:2] == ["pdftoppm", "-f"] and calls[0][-2] == pdf
    assert "-scale-to-x" in calls[0] and calls[0][calls[0].index("-H") + 1] == "302"
    assert not [n for n in os.listdir(thumb_dir) if n.startswith(".")], "no temp file left behind"

    # cached: pdftoppm is not called again
    calls.clear()
    assert thumbnails.render(pdf, str(thumb_dir), run=run) == target
    assert calls == []


def test_render_creates_the_cache_dir(tmp_path):
    pdf = make_pdf(tmp_path, "scan.pdf")
    target = thumbnails.render(pdf, str(tmp_path / "new" / "dir"), run=fake_run_ok)
    assert target and os.path.isfile(target)


def test_render_failure_logs_the_reason_and_leaves_no_file(tmp_path):
    pdf = make_pdf(tmp_path, "broken.pdf")
    thumb_dir = tmp_path / "t"
    messages = []

    def run_fail_with_tmp(command, **kwargs):
        open(command[-1] + ".jpg", "wb").close()  # pdftoppm wrote an empty file before failing
        return fake_run_fail(command)

    assert thumbnails.render(pdf, str(thumb_dir), run=run_fail_with_tmp, log=messages.append) is None
    assert messages == [f"thumbnail failed for {pdf}: Command Line Error: broken"]
    assert os.listdir(thumb_dir) == []

    assert thumbnails.render(pdf, str(thumb_dir), run=lambda c, **k: SimpleNamespace(returncode=3, stdout="", stderr=""), log=messages.append) is None
    assert messages[-1].endswith("exit status 3")


def test_render_handles_missing_pdftoppm_and_timeouts(tmp_path):
    pdf = make_pdf(tmp_path, "scan.pdf")
    messages = []

    def run_missing(command, **kwargs):
        raise FileNotFoundError("pdftoppm")

    def run_timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout", 0))

    assert thumbnails.render(pdf, str(tmp_path), run=run_missing, log=messages.append) is None
    assert thumbnails.render(pdf, str(tmp_path), run=run_timeout, log=messages.append) is None
    assert thumbnails.render(str(tmp_path / "gone.pdf"), str(tmp_path), run=fake_run_ok, log=messages.append) is None
    assert len(messages) == 3 and all(m.startswith("thumbnail failed for") for m in messages)


def test_forget_removes_all_versions_of_one_file(tmp_path):
    for name in ("a.pdf.1.jpg", "a.pdf.2.jpg", "a.pdfx.3.jpg", "ab.pdf.1.jpg"):
        (tmp_path / name).write_bytes(b"x")
    assert thumbnails.forget("/scans/a.pdf", str(tmp_path)) == 2
    assert sorted(os.listdir(tmp_path)) == ["a.pdfx.3.jpg", "ab.pdf.1.jpg"]
    assert thumbnails.forget("/scans/none.pdf", str(tmp_path)) == 0


def test_forget_and_sweep_survive_files_that_cannot_be_removed(tmp_path, monkeypatch):
    scans = tmp_path / "scans"
    scans.mkdir()
    thumb_dir = scans / ".thumbnails"
    thumb_dir.mkdir()
    (thumb_dir / "a.pdf.1.jpg").write_bytes(b"x")
    (thumb_dir / "orphan.pdf.1.jpg").write_bytes(b"x")
    make_pdf(scans, "a.pdf")

    def refuse(path):
        raise PermissionError(path)

    monkeypatch.setattr(thumbnails.os, "remove", refuse)
    assert thumbnails.forget("/scans/a.pdf", str(thumb_dir)) == 0
    # the stale version cannot go, the orphan neither; the new render still happens
    assert thumbnails.sweep(str(scans), str(thumb_dir), run=fake_run_ok, busy=lambda: False) == (1, 0, 0)


def test_sweep_skips_a_scan_that_vanishes_while_listing(tmp_path, monkeypatch):
    scans = tmp_path / "scans"
    scans.mkdir()
    make_pdf(scans, "a.pdf")
    monkeypatch.setattr(thumbnails, "thumbnail_path", lambda pdf, thumb_dir: (_ for _ in ()).throw(FileNotFoundError(pdf)))
    assert thumbnails.sweep(str(scans), str(scans / ".thumbnails"), run=fake_run_ok, busy=lambda: False) == (0, 0, 0)


def test_sweep_renders_missing_newest_first_and_removes_orphans(tmp_path):
    scans = tmp_path / "scans"
    scans.mkdir()
    thumb_dir = scans / ".thumbnails"
    thumb_dir.mkdir()
    old = make_pdf(scans, "old.pdf", mtime=1600000000)
    new = make_pdf(scans, "new.pdf", mtime=1700000000)
    done = make_pdf(scans, "done.pdf", mtime=1650000000)
    (thumb_dir / "done.pdf.1650000000.jpg").write_bytes(b"cached")
    (thumb_dir / "gone.pdf.1600000000.jpg").write_bytes(b"orphan")
    (thumb_dir / "old.pdf.1500000000.jpg").write_bytes(b"outdated version")
    (thumb_dir / ".new.pdf.123.jpg").write_bytes(b"temp file of a running render")
    (scans / ".hidden.pdf").write_bytes(b"%PDF")
    (scans / "notes.txt").write_bytes(b"not a pdf")
    rendered = []
    slept = []

    def run(command, **kwargs):
        rendered.append(command[-2])
        return fake_run_ok(command, **kwargs)

    result = thumbnails.sweep(str(scans), str(thumb_dir), run=run, pause=0.1, sleep=slept.append, busy=lambda: False)
    assert result == (2, 0, 1)
    assert rendered == [new, old], "newest first, cached and hidden files skipped"
    assert slept == [0.1, 0.1]
    names = sorted(os.listdir(thumb_dir))
    assert names == [".new.pdf.123.jpg", "done.pdf.1650000000.jpg", "new.pdf.1700000000.jpg", "old.pdf.1600000000.jpg"]
    assert thumbnails.in_scan_dir(done, str(scans))


def test_sweep_waits_while_the_scanner_is_busy_and_counts_failures(tmp_path):
    scans = tmp_path / "scans"
    scans.mkdir()
    make_pdf(scans, "a.pdf")
    states = iter([True, True, False])
    slept = []
    result = thumbnails.sweep(str(scans), str(scans / ".thumbnails"), run=fake_run_fail, sleep=slept.append,
                              busy=lambda: next(states), log=lambda m: None)
    assert result == (0, 1, 0)
    assert slept == [5, 5]


def test_sweep_without_a_cache_dir_or_scans(tmp_path):
    assert thumbnails.sweep(str(tmp_path / "none"), str(tmp_path / "nothumbs"), run=fake_run_ok, busy=lambda: False) == (0, 0, 0)


def test_scanner_busy_reads_the_status_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(thumbnails.tempfile, "gettempdir", lambda: str(tmp_path))
    assert not thumbnails.scanner_busy()
    marker = tmp_path / "STATUS_SCAN"
    marker.write_text("scan")
    assert thumbnails.scanner_busy()
    os.utime(marker, (time.time() - 7200, time.time() - 7200))
    assert not thumbnails.scanner_busy(), "a stale marker from a crashed scan is ignored"


def test_main_sweep_and_render(tmp_path, monkeypatch):
    scans = tmp_path / "scans"
    scans.mkdir()
    pdf = make_pdf(scans, "a.pdf")
    thumb_dir = str(scans / ".thumbnails")
    monkeypatch.setattr(thumbnails.subprocess, "run", fake_run_ok)
    monkeypatch.setattr(thumbnails, "scanner_busy", lambda: False)
    messages = []
    assert thumbnails.main(["sweep", "--scan-dir", str(scans), "--thumb-dir", thumb_dir], log=messages.append) == 0
    assert messages[-1].startswith("thumbnail sweep finished: 1 rendered, 0 failed, 0 orphans removed")

    messages.clear()
    assert thumbnails.main(["render", pdf, "--thumb-dir", thumb_dir], log=messages.append) == 0
    assert messages == [thumbnails.thumbnail_path(pdf, thumb_dir)]
    assert thumbnails.main(["render", str(scans / "missing.pdf"), "--thumb-dir", thumb_dir], log=messages.append) == 1

    with pytest.raises(SystemExit):
        thumbnails.main([])


# --- hooks in the pipeline -------------------------------------------------

def test_scanner_renders_the_thumbnail_after_the_pdf_landed(tmp_path, monkeypatch, clean_env):
    scan_dir = tmp_path / "scans"
    scan_dir.mkdir()
    job = "2026-05-06-07-08-09"
    job_dir = tmp_path / "tmp" / job
    job_dir.mkdir(parents=True)
    (job_dir / f"{job}-front-page-1.pnm").write_bytes(b"P6")
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path / "tmp"))
    monkeypatch.setattr(scanner, "SCAN_DIR", str(scan_dir))
    monkeypatch.setattr(scanner, "execute_command", lambda log, command, **kw: open(command[-1], "w").close())
    monkeypatch.setattr(scanner, "notify", lambda *a, **k: None)
    monkeypatch.setattr(scanner, "sendtoftps", lambda *a, **k: None)
    monkeypatch.setattr(scanner.jobstate, "update", lambda *a, **k: None)
    rendered = []
    monkeypatch.setattr(thumbnails, "render", lambda path, **kw: rendered.append(path) or path)

    clean_env.setenv("GUI_THUMBNAILS", "false")
    scanner.convert_and_post_process(job, "front", None)
    assert rendered == [], "off: nothing rendered"

    job_dir.mkdir(parents=True, exist_ok=True)  # clean_job_files removed it
    (job_dir / f"{job}-front-page-1.pnm").write_bytes(b"P6")
    clean_env.setenv("GUI_THUMBNAILS", "true")
    scanner.convert_and_post_process(job, "front", None)
    assert rendered == [str(scan_dir / f"{job}.pdf")]


def test_ocr_queue_renders_the_result_and_forgets_the_removed_original(tmp_path, monkeypatch, clean_env):
    scans = tmp_path / "scans"
    scans.mkdir()
    pdf = make_pdf(scans, "2026-05-06-07-08-09.pdf")
    monkeypatch.setattr(thumbnails, "SCAN_DIR", str(scans))
    monkeypatch.setattr(ocr_queue, "trigger_inotify", lambda *a, **k: None)
    monkeypatch.setattr(ocr_queue, "trigger_telegram", lambda *a, **k: None)
    monkeypatch.setattr(ocr_queue, "sendtoftps", lambda *a, **k: None)
    monkeypatch.setattr(ocr_queue, "wait_for_idle_scanner", lambda **k: None)
    rendered, forgotten = [], []
    monkeypatch.setattr(thumbnails, "render", lambda path, **kw: rendered.append(path) or path)
    monkeypatch.setattr(thumbnails, "forget", lambda path, **kw: forgotten.append(path) or 1)
    clean_env.setenv("OCR_SERVER", "ocr")
    clean_env.setenv("OCR_PORT", "8080")
    clean_env.setenv("OCR_PATH", "ocr.php")
    clean_env.setenv("REMOVE_ORIGINAL_AFTER_OCR", "true")
    clean_env.setenv("GUI_THUMBNAILS", "true")

    def upload(pdf_path, output_path, url, run=None):
        with open(output_path, "wb") as out:
            out.write(b"%PDF-1.4 ocr")
        return True

    monkeypatch.setattr(ocr_queue, "upload", upload)
    monkeypatch.setattr(ocr_queue, "validate_pdf", lambda *a, **k: (True, "ok"))
    job = {"PDF": pdf, "DATE": "2026-05-06-07-08-09", "SUFFIX": "front"}
    assert ocr_queue.process_job(job, output_dir=str(scans), count_pages=lambda p: 1)
    assert rendered == [str(scans / "2026-05-06-07-08-09-ocr.pdf")]
    assert forgotten == [pdf], "the removed original loses its thumbnail"

    # result outside the listed directory: nothing to render
    rendered.clear()
    forgotten.clear()
    pdf2 = make_pdf(scans, "2026-05-06-07-08-10.pdf")
    clean_env.setenv("REMOVE_ORIGINAL_AFTER_OCR", "false")
    out_dir = tmp_path / "elsewhere"
    out_dir.mkdir()
    job = {"PDF": pdf2, "DATE": "2026-05-06-07-08-10", "SUFFIX": "front"}
    assert ocr_queue.process_job(job, output_dir=str(out_dir), count_pages=lambda p: 1)
    assert rendered == [] and forgotten == []
