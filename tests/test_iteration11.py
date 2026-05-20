#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for iteration 11: fleet aggregation."""

import http.server
import io
import json
import threading
import time
from contextlib import redirect_stdout

import pytest

from wtftools import fleet, main


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


# ---------- fleet module ----------

def test_normalize_url():
    assert fleet._normalize("host:8765") == "http://host:8765/audit.json"
    assert fleet._normalize("https://x.example/") == "https://x.example/audit.json"
    assert fleet._normalize("host") == "http://host/audit.json"


def test_fetch_one_connection_refused():
    """A definitely-closed port — assume something is unlikely on 1."""
    h = fleet.fetch_one("127.0.0.1:1", timeout=0.5)
    assert h.ok is False
    assert h.error is not None
    assert h.latency_ms is not None


def test_fetch_one_invalid_target():
    h = fleet.fetch_one("not-a-real-host-xyz-12345.invalid:80", timeout=1.0)
    assert h.ok is False
    assert h.error is not None


# Start a tiny fake wtfd-style HTTP server on an ephemeral port to test fetch.

class _FakeAuditHandler(http.server.BaseHTTPRequestHandler):
    payload = {
        "host": "fake1",
        "timestamp": 1234567890,
        "summary": {"ok": 10, "warn": 2, "fail": 1, "skip": 0},
        "results": [
            {"name": "ok-check", "status": "ok", "message": "all fine", "detail": []},
            {"name": "broken", "status": "fail", "message": "boom!", "detail": []},
            {"name": "warn-thing", "status": "warn", "message": "soft warning", "detail": []},
        ],
    }
    require_auth = False
    expected_token = ""

    def do_GET(self):
        if self.require_auth:
            header = self.headers.get("Authorization", "")
            if header != f"Bearer {self.expected_token}":
                self.send_response(401)
                self.end_headers()
                return
        body = json.dumps(self.payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a, **kw):
        pass  # quiet


class _SlowHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        time.sleep(3.0)
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a, **kw):
        pass


@pytest.fixture
def fake_server():
    """Start a fake wtfd-style server on an ephemeral port."""
    _FakeAuditHandler.require_auth = False
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _FakeAuditHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    try:
        yield f"127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_fetch_one_success(fake_server):
    h = fleet.fetch_one(fake_server, timeout=3)
    assert h.ok is True
    assert h.error is None
    assert h.host == "fake1"
    assert h.summary == {"ok": 10, "warn": 2, "fail": 1, "skip": 0}
    assert len(h.results) == 3
    assert h.latency_ms is not None


def test_fetch_one_auth_required(fake_server):
    _FakeAuditHandler.require_auth = True
    _FakeAuditHandler.expected_token = "secret"
    try:
        # Without token
        h = fleet.fetch_one(fake_server, timeout=3)
        assert h.ok is False
        assert "401" in h.error
        # With wrong token
        h = fleet.fetch_one(fake_server, timeout=3, token="wrong")
        assert h.ok is False
        assert "401" in h.error
        # With right token
        h = fleet.fetch_one(fake_server, timeout=3, token="secret")
        assert h.ok is True
    finally:
        _FakeAuditHandler.require_auth = False


def test_fetch_one_invalid_json(monkeypatch, fake_server):
    """Replace the response with non-JSON for one call."""

    class _NonJsonHandler(_FakeAuditHandler):
        def do_GET(self):  # noqa
            body = b"not json at all"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _NonJsonHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    try:
        h = fleet.fetch_one(f"127.0.0.1:{port}", timeout=3)
        assert h.ok is False
        assert "invalid JSON" in h.error
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_fetch_one_timeout():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _SlowHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    try:
        h = fleet.fetch_one(f"127.0.0.1:{port}", timeout=0.5)
        assert h.ok is False
        assert h.error is not None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_fetch_all_empty():
    assert fleet.fetch_all([]) == []


def test_fetch_all_preserves_order(fake_server):
    targets = [fake_server, "127.0.0.1:1", fake_server, "nx.invalid:80"]
    hosts = fleet.fetch_all(targets, timeout=1.0, workers=4)
    assert len(hosts) == 4
    assert hosts[0].ok is True
    assert hosts[1].ok is False
    assert hosts[2].ok is True
    assert hosts[3].ok is False


def test_aggregate_summary():
    hosts = [
        fleet.FleetHost(target="a", url="", ok=True,
                        summary={"ok": 5, "warn": 1, "fail": 0, "skip": 1}),
        fleet.FleetHost(target="b", url="", ok=True,
                        summary={"ok": 3, "warn": 0, "fail": 2, "skip": 0}),
        fleet.FleetHost(target="c", url="", ok=False, error="down"),
    ]
    totals = fleet.aggregate_summary(hosts)
    assert totals == {"ok": 8, "warn": 1, "fail": 2, "skip": 1, "unreachable": 1}


def test_host_severity():
    down = fleet.FleetHost(target="x", url="", ok=False, error="e")
    fail_host = fleet.FleetHost(target="x", url="", ok=True,
                                summary={"ok": 0, "warn": 0, "fail": 1, "skip": 0})
    warn_host = fleet.FleetHost(target="x", url="", ok=True,
                                summary={"ok": 0, "warn": 1, "fail": 0, "skip": 0})
    ok_host = fleet.FleetHost(target="x", url="", ok=True,
                              summary={"ok": 5, "warn": 0, "fail": 0, "skip": 0})
    assert fleet.host_severity(down) < fleet.host_severity(fail_host)
    assert fleet.host_severity(fail_host) < fleet.host_severity(warn_host)
    assert fleet.host_severity(warn_host) < fleet.host_severity(ok_host)


def test_render_prometheus_format():
    hosts = [
        fleet.FleetHost(target="a:8765", url="...", ok=True, host="alpha",
                        summary={"ok": 5, "warn": 1, "fail": 0, "skip": 1}),
        fleet.FleetHost(target="b:8765", url="...", ok=False, error="down"),
    ]
    out = fleet.render_prometheus(hosts)
    assert "wtf_fleet_host_up" in out
    assert 'wtf_fleet_host_up{host="alpha"} 1' in out
    assert 'wtf_fleet_host_up{host="b:8765"} 0' in out
    assert 'wtf_fleet_summary_count{host="alpha",status="warn"} 1' in out


def test_render_prometheus_escapes_quotes():
    hosts = [
        fleet.FleetHost(target='weird"name', url="", ok=True, host='quote"y',
                        summary={"ok": 1, "warn": 0, "fail": 0, "skip": 0}),
    ]
    out = fleet.render_prometheus(hosts)
    assert 'host="quote\\"y"' in out


# ---------- CLI ----------

def test_cli_fleet_no_hosts():
    rc, out = _capture(["fleet"])
    assert rc == 2
    assert "no fleet hosts" in out


def test_cli_fleet_basic(monkeypatch):
    fake_hosts = [
        fleet.FleetHost(target="h1", url="", ok=True, host="alpha",
                        summary={"ok": 5, "warn": 0, "fail": 0, "skip": 0},
                        latency_ms=12.0),
        fleet.FleetHost(target="h2", url="", ok=False, error="connection refused",
                        latency_ms=5.0),
        fleet.FleetHost(target="h3", url="", ok=True, host="beta",
                        summary={"ok": 3, "warn": 1, "fail": 2, "skip": 0},
                        results=[
                            {"name": "swap", "status": "fail", "message": "99%"},
                            {"name": "ram", "status": "warn", "message": "high"},
                        ],
                        latency_ms=18.0),
    ]
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: fake_hosts)
    rc, out = _capture(["fleet", "--hosts", "h1,h2,h3"])
    assert rc == 2  # fleet has a fail somewhere
    assert "alpha" in out
    assert "beta" in out
    assert "connection refused" in out
    # totals line
    assert "Totals across fleet" in out
    assert "unreachable" in out


def test_cli_fleet_json(monkeypatch):
    fake_hosts = [
        fleet.FleetHost(target="h1", url="http://h1/audit.json", ok=True, host="alpha",
                        summary={"ok": 5, "warn": 0, "fail": 0, "skip": 0},
                        latency_ms=10.0),
    ]
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: fake_hosts)
    rc, out = _capture(["fleet", "--hosts", "h1", "--format", "json"])
    data = json.loads(out)
    assert data["totals"]["ok"] == 5
    assert data["hosts"][0]["host"] == "alpha"
    assert rc == 0


def test_cli_fleet_prometheus(monkeypatch):
    fake_hosts = [
        fleet.FleetHost(target="h1", url="", ok=True, host="alpha",
                        summary={"ok": 5, "warn": 0, "fail": 0, "skip": 0}),
    ]
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: fake_hosts)
    rc, out = _capture(["fleet", "--hosts", "h1", "--format", "prometheus"])
    assert "wtf_fleet_host_up" in out
    assert rc == 0


def test_cli_fleet_problem_only(monkeypatch):
    fake_hosts = [
        fleet.FleetHost(target="h1", url="", ok=True, host="alpha",
                        summary={"ok": 5, "warn": 0, "fail": 0, "skip": 0}),
        fleet.FleetHost(target="h2", url="", ok=True, host="beta",
                        summary={"ok": 1, "warn": 0, "fail": 2, "skip": 0},
                        results=[]),
    ]
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: fake_hosts)
    rc, out = _capture(["fleet", "--hosts", "h1,h2", "--problem-only"])
    # Only beta should appear
    assert "beta" in out
    assert "alpha" not in out


def test_cli_fleet_token_file(monkeypatch, tmp_path):
    token_file = tmp_path / "tok"
    token_file.write_text("secret123")
    captured = {}

    def fake_fetch_all(targets, timeout, workers, token):
        captured["token"] = token
        return [fleet.FleetHost(target=t, url="", ok=True, host=t,
                                summary={"ok": 1, "warn": 0, "fail": 0, "skip": 0})
                for t in targets]

    monkeypatch.setattr(fleet, "fetch_all", fake_fetch_all)
    rc, out = _capture(["fleet", "--hosts", "h1",
                        "--token-file", str(token_file)])
    assert captured["token"] == "secret123"


def test_cli_fleet_token_file_missing():
    rc, out = _capture(["fleet", "--hosts", "h1",
                        "--token-file", "/nonexistent/tok"])
    assert rc == 2
    assert "token file" in out


def test_cli_fleet_hosts_file(monkeypatch, tmp_path):
    hf = tmp_path / "hosts"
    hf.write_text("# header\nhost1:8765\nhost2:8765\n\n# blank above ignored\n")
    captured = {}

    def fake_fetch_all(targets, *a, **kw):
        captured["targets"] = targets
        return [fleet.FleetHost(target=t, url="", ok=True, host=t,
                                summary={"ok": 0, "warn": 0, "fail": 0, "skip": 0})
                for t in targets]

    monkeypatch.setattr(fleet, "fetch_all", fake_fetch_all)
    _capture(["fleet", "--hosts-file", str(hf)])
    assert captured["targets"] == ["host1:8765", "host2:8765"]


def test_cli_fleet_dedupes(monkeypatch):
    captured = {}

    def fake_fetch_all(targets, *a, **kw):
        captured["targets"] = targets
        return [fleet.FleetHost(target=t, url="", ok=True, host=t,
                                summary={"ok": 0, "warn": 0, "fail": 0, "skip": 0})
                for t in targets]

    monkeypatch.setattr(fleet, "fetch_all", fake_fetch_all)
    _capture(["fleet", "--hosts", "a,a,b,a"])
    assert captured["targets"] == ["a", "b"]


def test_cli_fleet_config_section(monkeypatch, tmp_path):
    """Hosts can be set in config [thresholds] fleet_hosts."""
    cfg_file = tmp_path / "wtf.ini"
    cfg_file.write_text("[thresholds]\nfleet_hosts = cfg-host:9999, other:9999\n")
    captured = {}

    def fake_fetch_all(targets, *a, **kw):
        captured["targets"] = targets
        return [fleet.FleetHost(target=t, url="", ok=True, host=t,
                                summary={"ok": 0, "warn": 0, "fail": 0, "skip": 0})
                for t in targets]

    monkeypatch.setattr(fleet, "fetch_all", fake_fetch_all)
    rc, _ = _capture(["--config", str(cfg_file), "fleet"])
    assert "cfg-host:9999" in captured["targets"]
    assert "other:9999" in captured["targets"]


def test_cli_fleet_all_unreachable(monkeypatch):
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: [
        fleet.FleetHost(target="h", url="", ok=False, error="down"),
    ])
    rc, out = _capture(["fleet", "--hosts", "h"])
    assert rc == 2


def test_cli_fleet_partial_unreachable(monkeypatch):
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: [
        fleet.FleetHost(target="h1", url="", ok=True, host="h1",
                        summary={"ok": 5, "warn": 0, "fail": 0, "skip": 0}),
        fleet.FleetHost(target="h2", url="", ok=False, error="down"),
    ])
    rc, out = _capture(["fleet", "--hosts", "h1,h2"])
    assert rc == 1  # partial-unreachable but no FAIL


def test_cli_fleet_all_clean(monkeypatch):
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: [
        fleet.FleetHost(target="h", url="", ok=True, host="h",
                        summary={"ok": 5, "warn": 0, "fail": 0, "skip": 0}),
    ])
    rc, _ = _capture(["fleet", "--hosts", "h"])
    assert rc == 0
