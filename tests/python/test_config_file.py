"""Configuration file overlay in the scripts (#124): file beats default, environment beats file."""
import os

import scanner


def test_parse_config_file_rules(tmp_path):
    conf = tmp_path / "scanner.conf"
    conf.write_text('# comment\n\nRESOLUTION=200\r\nSCAN_MODE="True Gray"\nFTP_PATH=/a/b=c/\nno equals\nlower=1\n KEY_WITH_SPACES = x\n')
    assert scanner.parse_config_file(str(conf)) == {
        "RESOLUTION": "200", "SCAN_MODE": "True Gray", "FTP_PATH": "/a/b=c/", "KEY_WITH_SPACES": " x"}
    assert scanner.parse_config_file(str(tmp_path / "missing.conf")) == {}


def test_read_environment_overlays_file_except_locked_keys(tmp_path, monkeypatch):
    env_file = tmp_path / "env.txt"
    env_file.write_text("RESOLUTION=600\nOCR_SERVER=ocr.local\n")
    locked = tmp_path / "locked.txt"
    locked.write_text("RESOLUTION\nOCR_SERVER\n")
    conf = tmp_path / "scanner.conf"
    conf.write_text("RESOLUTION=200\nSCAN_MODE=True Gray\nOCR_SERVER=other\nREMOVE_BLANK_THRESHOLD=0.5\n")
    monkeypatch.setattr(scanner, "ENVIRONMENT_FILE_PATH", str(env_file))
    monkeypatch.setattr(scanner, "LOCKED_KEYS_PATH", str(locked))
    for name in ["RESOLUTION", "OCR_SERVER", "SCAN_MODE", "REMOVE_BLANK_THRESHOLD"]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SCANNER_CONFIG_FILE", str(conf))

    scanner.read_environment()

    assert os.environ["RESOLUTION"] == "600", "environment wins over the file"
    assert os.environ["OCR_SERVER"] == "ocr.local"
    assert os.environ["SCAN_MODE"] == "True Gray", "file sets what the environment does not"
    assert os.environ["REMOVE_BLANK_THRESHOLD"] == "0.5"


def test_file_changes_apply_on_next_read(tmp_path, monkeypatch):
    env_file = tmp_path / "env.txt"
    env_file.write_text("NAME=Scanner\n")
    conf = tmp_path / "scanner.conf"
    conf.write_text("SCAN_MODE=True Gray\n")
    monkeypatch.setattr(scanner, "ENVIRONMENT_FILE_PATH", str(env_file))
    monkeypatch.setattr(scanner, "LOCKED_KEYS_PATH", str(tmp_path / "none"))
    monkeypatch.delenv("SCAN_MODE", raising=False)
    monkeypatch.setenv("SCANNER_CONFIG_FILE", str(conf))
    scanner.read_environment()
    assert os.environ["SCAN_MODE"] == "True Gray"
    conf.write_text("SCAN_MODE=Black & White\n")
    scanner.read_environment()
    assert os.environ["SCAN_MODE"] == "Black & White"


def test_scan_command_uses_file_value(tmp_path, monkeypatch, clean_env):
    env_file = tmp_path / "env.txt"
    env_file.write_text("NAME=Scanner\n")
    conf = tmp_path / "scanner.conf"
    conf.write_text("RESOLUTION=150\nSCAN_HEIGHT_MM=295\n")
    monkeypatch.setattr(scanner, "ENVIRONMENT_FILE_PATH", str(env_file))
    monkeypatch.setattr(scanner, "LOCKED_KEYS_PATH", str(tmp_path / "none"))
    clean_env.setenv("SCANNER_CONFIG_FILE", str(conf))
    scanner.read_environment()
    calls = []
    monkeypatch.setattr(scanner, "execute_command", lambda log, cmd, **kw: calls.append(cmd))
    import io
    scanner.scan_cmd(io.StringIO(), None, "/tmp/x%04d.pnm", [])
    assert "--resolution=150" in calls[0]
    assert calls[0][calls[0].index("-y") + 1] == "295"
