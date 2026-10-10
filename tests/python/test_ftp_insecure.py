import io

import sendtoftps as ftp_module


def capture(monkeypatch):
    calls = []
    monkeypatch.setattr(ftp_module.subprocess, "run", lambda cmd, **k: calls.append(cmd))
    return calls


def test_default_requires_tls(monkeypatch, clean_env, capsys):
    clean_env.delenv("FTP_INSECURE", raising=False)
    calls = capture(monkeypatch)
    assert ftp_module.sendtoftps(io.StringIO(), "u", "p", "host", "/up/", "/scans/a.pdf") is True
    assert "--ssl-reqd" in calls[0]
    assert calls[0][-1] == "ftp://host/up/"
    assert "FTPS server host successful" in capsys.readouterr().out


def test_ftp_insecure_env_drops_tls_requirement(monkeypatch, clean_env, capsys):
    clean_env.setenv("FTP_INSECURE", "true")
    calls = capture(monkeypatch)
    assert ftp_module.sendtoftps(io.StringIO(), "u", "p", "host", "/up/", "/scans/a.pdf") is True
    assert "--ssl-reqd" not in calls[0]
    assert calls[0][-1] == "ftp://host/up/", "plain FTP still uses the ftp:// scheme"
    assert "FTP server host successful" in capsys.readouterr().out


def test_ftp_insecure_must_be_exactly_true(monkeypatch, clean_env):
    for value in ["false", "", "yes", "1"]:
        clean_env.setenv("FTP_INSECURE", value)
        calls = capture(monkeypatch)
        ftp_module.sendtoftps(io.StringIO(), "u", "p", "host", "/up/", "/scans/a.pdf")
        assert "--ssl-reqd" in calls[0], f"FTP_INSECURE={value!r} must keep TLS"
    clean_env.setenv("FTP_INSECURE", " TRUE ")
    calls = capture(monkeypatch)
    ftp_module.sendtoftps(io.StringIO(), "u", "p", "host", "/up/", "/scans/a.pdf")
    assert "--ssl-reqd" not in calls[0]


def test_explicit_argument_overrides_env(monkeypatch, clean_env):
    clean_env.setenv("FTP_INSECURE", "true")
    calls = capture(monkeypatch)
    ftp_module.sendtoftps(io.StringIO(), "u", "p", "host", "/up/", "/scans/a.pdf", insecure=False)
    assert "--ssl-reqd" in calls[0]
