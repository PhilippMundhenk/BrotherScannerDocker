"""Page geometry (#120) and SCAN_MODE (#121) on the scanimage and gm commands."""
import io

import scanner


def test_scan_cmd_uses_scan_mode_from_env(monkeypatch, clean_env):
    calls = []
    monkeypatch.setattr(scanner, "execute_command", lambda log, cmd, **kw: calls.append(cmd))
    scanner.scan_cmd(io.StringIO(), None, "/tmp/x%04d.pnm", [])
    assert not any(a.startswith("--mode=") for a in calls[0]), "device default when SCAN_MODE is unset"

    clean_env.setenv("SCAN_MODE", "Black & White")
    scanner.scan_cmd(io.StringIO(), None, "/tmp/x%04d.pnm", [])
    assert "--mode=Black & White" in calls[1]
    assert calls[1].index("--mode=Black & White") < calls[1].index("--resolution=300")


def test_explicit_mode_argument_wins_over_env(monkeypatch, clean_env):
    calls = []
    monkeypatch.setattr(scanner, "execute_command", lambda log, cmd, **kw: calls.append(cmd))
    clean_env.setenv("SCAN_MODE", "Black & White")
    scanner.scan_cmd(io.StringIO(), None, "/tmp/x%04d.pnm", ["--mode=True Gray"])
    modes = [a for a in calls[0] if a.startswith("--mode=")]
    assert modes == ["--mode=True Gray"], "scan to OCR keeps its gray mode"


def test_resolution_from_env(monkeypatch, clean_env):
    calls = []
    monkeypatch.setattr(scanner, "execute_command", lambda log, cmd, **kw: calls.append(cmd))
    clean_env.setenv("RESOLUTION", "200")
    scanner.scan_cmd(io.StringIO(), None, "/tmp/x%04d.pnm", [])
    assert "--resolution=200" in calls[0]


def test_pdf_pages_get_the_scan_density(tmp_path, monkeypatch, clean_env):
    """#120: without a density the page size is the pixel size at 72 dpi (34 x 49 inches)."""
    job = "2026-10-10-12-00-00"
    job_dir = tmp_path / job
    job_dir.mkdir()
    (job_dir / f"{job}-front-page0001.pnm").write_bytes(b"P5 1 1 255 \x00")
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(scanner, "SCAN_DIR", str(scans))
    monkeypatch.setattr(scanner, "notify", lambda *a, **k: None)
    monkeypatch.setattr(scanner, "sendtoftps", lambda *a, **k: None)
    commands = []

    def fake_execute(log, command, **kwargs):
        commands.append(command)
        open(command[-1], "w").close()

    monkeypatch.setattr(scanner, "execute_command", fake_execute)
    clean_env.setenv("RESOLUTION", "200")
    scanner.convert_and_post_process(job, "front", None)
    gm = commands[0]
    assert gm[:2] == ["gm", "convert"]
    assert gm[gm.index("-density") + 1] == "200"
    assert "-units" in gm and gm[gm.index("-units") + 1] == "PixelsPerInch"


def test_jpeg_compression_still_applies(tmp_path, monkeypatch, clean_env):
    job = "2026-10-10-12-00-01"
    job_dir = tmp_path / job
    job_dir.mkdir()
    (job_dir / f"{job}-front-page0001.pnm").write_bytes(b"P5 1 1 255 \x00")
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setattr(scanner.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(scanner, "SCAN_DIR", str(scans))
    monkeypatch.setattr(scanner, "notify", lambda *a, **k: None)
    monkeypatch.setattr(scanner, "sendtoftps", lambda *a, **k: None)
    commands = []
    monkeypatch.setattr(scanner, "execute_command", lambda log, c, **k: commands.append(c) or open(c[-1], "w").close())
    clean_env.setenv("USE_JPEG_COMPRESSION", "true")
    scanner.convert_and_post_process(job, "front", None)
    gm = commands[0]
    assert "-compress" in gm and gm[gm.index("-compress") + 1] == "JPEG"
    assert gm[gm.index("-density") + 1] == "300"


def test_scan_area_defaults_and_env(monkeypatch, clean_env):
    calls = []
    monkeypatch.setattr(scanner, "execute_command", lambda log, cmd, **kw: calls.append(cmd))
    for name in ["SCAN_LEFT_MM", "SCAN_TOP_MM", "SCAN_WIDTH_MM", "SCAN_HEIGHT_MM"]:
        clean_env.delenv(name, raising=False)
    scanner.scan_cmd(io.StringIO(), None, "/tmp/x%04d.pnm", [])
    cmd = calls[0]
    assert cmd[cmd.index("-l") + 1] == "0" and cmd[cmd.index("-t") + 1] == "0"
    assert cmd[cmd.index("-x") + 1] == "215" and cmd[cmd.index("-y") + 1] == "297"

    clean_env.setenv("SCAN_TOP_MM", "1.5")
    clean_env.setenv("SCAN_HEIGHT_MM", "295")
    scanner.scan_cmd(io.StringIO(), None, "/tmp/x%04d.pnm", [])
    cmd = calls[1]
    assert cmd[cmd.index("-t") + 1] == "1.5" and cmd[cmd.index("-y") + 1] == "295"
    assert cmd[cmd.index("-x") + 1] == "215", "unset values keep their defaults"


def test_scan_area_rejects_nonsense(monkeypatch, clean_env, capsys):
    calls = []
    monkeypatch.setattr(scanner, "execute_command", lambda log, cmd, **kw: calls.append(cmd))
    clean_env.setenv("SCAN_HEIGHT_MM", "tall")
    clean_env.setenv("SCAN_WIDTH_MM", "0")
    clean_env.setenv("SCAN_LEFT_MM", "-3")
    scanner.scan_cmd(io.StringIO(), None, "/tmp/x%04d.pnm", [])
    cmd = calls[0]
    assert cmd[cmd.index("-y") + 1] == "297" and cmd[cmd.index("-x") + 1] == "215" and cmd[cmd.index("-l") + 1] == "0"
    out = capsys.readouterr().out
    assert "SCAN_HEIGHT_MM" in out and "SCAN_WIDTH_MM" in out and "SCAN_LEFT_MM" in out
