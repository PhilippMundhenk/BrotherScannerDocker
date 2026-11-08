import io
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import threading

import pytest

import sendtoftps as ftp_module
import trigger_inotify as inotify_module
import trigger_telegram as telegram_module


class FakeResponse:
    def __init__(self, ok=True):
        self.ok = ok

    def raise_for_status(self):
        if not self.ok:
            raise telegram_module.requests.exceptions.HTTPError("boom")


def test_telegram_skips_without_token_or_chat(monkeypatch):
    posted = []
    monkeypatch.setattr(telegram_module.requests, "post", lambda *a, **k: posted.append((a, k)) or FakeResponse())
    telegram_module.trigger_telegram(io.StringIO(), "hi", None, "42")
    telegram_module.trigger_telegram(io.StringIO(), "hi", "bot1:x", None)
    assert posted == []


def test_telegram_sends_plain_text_not_url_encoded(monkeypatch):
    """Regression: the message was percent-encoded before being sent as JSON."""
    posted = []
    monkeypatch.setattr(telegram_module.requests, "post", lambda url, **k: posted.append((url, k)) or FakeResponse())
    telegram_module.trigger_telegram(io.StringIO(), "Scanner: 2026.pdf (front) scanned", "bot1:x", "42")
    url, kwargs = posted[0]
    assert url == "https://api.telegram.org/bot1:x/sendMessage"
    assert kwargs["json"] == {"chat_id": "42", "text": "Scanner: 2026.pdf (front) scanned"}


def test_telegram_failure_does_not_raise(monkeypatch):
    monkeypatch.setattr(telegram_module.requests, "post", lambda *a, **k: FakeResponse(ok=False))
    telegram_module.trigger_telegram(io.StringIO(), "hi", "bot1:x", "42")


@pytest.mark.parametrize("status, expected", [(200, True), (503, False)])
def test_telegram_with_real_http_response(monkeypatch, status, expected):
    """Exercise Requests' JSON encoding and HTTP error handling without Telegram."""
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append((self.path, self.headers["Content-Type"], json.loads(body)))
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    session = telegram_module.requests.Session()
    session.trust_env = False

    def local_post(url, **kwargs):
        assert url == "https://api.telegram.org/bot1:x/sendMessage"
        assert kwargs["timeout"] == 30
        return session.post(f"http://127.0.0.1:{server.server_port}/sendMessage", **kwargs)

    monkeypatch.setattr(telegram_module.requests, "post", local_post)
    try:
        message = "Scan: café & page 2.pdf"
        assert telegram_module.trigger_telegram(io.StringIO(), message, "bot1:x", "42") is expected
        assert received == [("/sendMessage", "application/json", {"chat_id": "42", "text": message})]
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()
        session.close()


def test_ftp_skips_when_incomplete(monkeypatch):
    calls = []
    monkeypatch.setattr(ftp_module.subprocess, "run", lambda *a, **k: calls.append(a))
    ftp_module.sendtoftps(io.StringIO(), "", "pw", "host", "/path/", "file.pdf")
    ftp_module.sendtoftps(io.StringIO(), "u", "pw", "host", "/path/", None)
    assert calls == []


def test_ftp_invokes_curl_with_credentials_and_url(monkeypatch):
    calls = []
    monkeypatch.setattr(ftp_module.subprocess, "run", lambda cmd, **k: calls.append(cmd))
    ftp_module.sendtoftps(io.StringIO(), "alice", "secret", "ftp.example", "/uploads/", "/scans/scan.pdf")
    cmd = calls[0]
    assert cmd[0] == "curl" and "alice:secret" in cmd and "ftp://ftp.example/uploads/" in cmd
    assert "/scans/scan.pdf" in cmd


def test_ftp_failure_reports_but_does_not_exit(monkeypatch):
    """Regression: a failed upload used to call exit(1) inside the pipeline process."""

    def failing(cmd, **kwargs):
        raise subprocess.CalledProcessError(22, cmd)

    monkeypatch.setattr(ftp_module.subprocess, "run", failing)
    log = io.StringIO()
    result = ftp_module.sendtoftps(log, "alice", "secret", "ftp.example", "/uploads/", "/scans/scan.pdf")
    assert result is False


def test_inotify_skips_when_incomplete(monkeypatch):
    calls = []
    monkeypatch.setattr(inotify_module.subprocess, "run", lambda *a, **k: calls.append(a))
    inotify_module.trigger_inotify(io.StringIO(), None, "pw", "host", "/path", "f.pdf")
    assert calls == []


def test_inotify_invokes_sshpass_and_survives_failure(monkeypatch):
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        raise subprocess.CalledProcessError(5, cmd)

    monkeypatch.setattr(inotify_module.subprocess, "run", run)
    result = inotify_module.trigger_inotify(io.StringIO(), "alice", "secret", "host.example", "/remote", "scan.pdf")
    assert result is False
    cmd = calls[0]
    assert cmd[0] == "sshpass" and "alice@host.example" in cmd
    assert any("/remote/scan.pdf" in part for part in cmd)
