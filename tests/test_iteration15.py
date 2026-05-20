#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for iteration 15: fleet --watch, fleet --run-now, events --watch, QUICKSTART."""

import http.server
import io
import os
import threading
import time
from contextlib import redirect_stdout

import pytest

from wtftools import events, fleet, main


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


# ---------- fleet.trigger_run_now ----------

class _RunNowHandler(http.server.BaseHTTPRequestHandler):
    """Tiny HTTP server that records POST /run-now hits."""
    hits = []
    response_code = 202

    def do_POST(self):
        _RunNowHandler.hits.append(self.path)
        self.send_response(_RunNowHandler.response_code)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *a, **kw):
        pass


@pytest.fixture
def run_now_server():
    _RunNowHandler.hits = []
    _RunNowHandler.response_code = 202
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _RunNowHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    try:
        yield f"127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_trigger_run_now_empty():
    assert fleet.trigger_run_now([]) == {}


def test_trigger_run_now_success(run_now_server):
    result = fleet.trigger_run_now([run_now_server], timeout=2.0)
    assert result[run_now_server] == "ok"
    assert _RunNowHandler.hits == ["/run-now"]


def test_trigger_run_now_with_token(run_now_server):
    result = fleet.trigger_run_now([run_now_server], token="abc")
    assert result[run_now_server] == "ok"


def test_trigger_run_now_unreachable():
    result = fleet.trigger_run_now(["127.0.0.1:1"], timeout=0.5)
    assert "127.0.0.1:1" in result
    assert result["127.0.0.1:1"] != "ok"


def test_trigger_run_now_non_202(run_now_server):
    _RunNowHandler.response_code = 500
    try:
        result = fleet.trigger_run_now([run_now_server])
        # urllib treats 500 as HTTPError → caught → message contains "HTTP 500"
        assert result[run_now_server] != "ok"
        assert "500" in result[run_now_server]
    finally:
        _RunNowHandler.response_code = 202


# ---------- CLI: fleet --run-now ----------

def test_cli_fleet_run_now_calls_trigger(monkeypatch):
    triggered = {}

    def fake_trigger(targets, timeout, workers, token):
        triggered["targets"] = targets
        triggered["token"] = token
        return dict.fromkeys(targets, "ok")

    monkeypatch.setattr(fleet, "trigger_run_now", fake_trigger)
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: [
        fleet.FleetHost(target="h1", url="", ok=True, host="h1",
                        summary={"ok": 1, "warn": 0, "fail": 0, "skip": 0}),
    ])
    monkeypatch.setattr(main.time, "sleep", lambda _: None)
    rc, out = _capture(["fleet", "--hosts", "h1", "--run-now"])
    assert triggered["targets"] == ["h1"]
    assert rc == 0


def test_cli_fleet_run_now_partial_failure(monkeypatch):
    monkeypatch.setattr(fleet, "trigger_run_now",
                        lambda *a, **kw: {"h1": "ok", "h2": "HTTP 500"})
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: [
        fleet.FleetHost(target="h1", url="", ok=True, host="h1",
                        summary={"ok": 1, "warn": 0, "fail": 0, "skip": 0}),
        fleet.FleetHost(target="h2", url="", ok=True, host="h2",
                        summary={"ok": 1, "warn": 0, "fail": 0, "skip": 0}),
    ])
    monkeypatch.setattr(main.time, "sleep", lambda _: None)
    rc, out = _capture(["fleet", "--hosts", "h1,h2", "--run-now"])
    # text mode prints the partial run-now status
    assert "run-now reached 1/2 peer" in out
    assert rc == 0


def test_cli_fleet_run_now_token_file(monkeypatch, tmp_path):
    token_file = tmp_path / "tok"
    token_file.write_text("secret")
    captured = {}

    def fake_trigger(targets, timeout, workers, token):
        captured["token"] = token
        return dict.fromkeys(targets, "ok")

    monkeypatch.setattr(fleet, "trigger_run_now", fake_trigger)
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: [
        fleet.FleetHost(target="h1", url="", ok=True, host="h1",
                        summary={"ok": 1, "warn": 0, "fail": 0, "skip": 0}),
    ])
    monkeypatch.setattr(main.time, "sleep", lambda _: None)
    _capture(["fleet", "--hosts", "h1", "--run-now",
              "--token-file", str(token_file)])
    assert captured["token"] == "secret"


# ---------- CLI: fleet --watch ----------

def test_cli_fleet_watch_keyboard_interrupt(monkeypatch):
    """--watch loops until Ctrl-C; mock sleep to raise, verify one iteration ran."""
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: [
        fleet.FleetHost(target="h", url="", ok=True, host="h",
                        summary={"ok": 1, "warn": 0, "fail": 0, "skip": 0}),
    ])

    def boom(_):
        raise KeyboardInterrupt

    monkeypatch.setattr(main.time, "sleep", boom)
    rc, out = _capture(["fleet", "--hosts", "h", "--watch", "1"])
    assert rc == 0
    assert "watch stopped" in out
    assert "FLEET" in out


def test_cli_fleet_watch_label(monkeypatch):
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: [])
    monkeypatch.setattr(main.time, "sleep", lambda _: (_ for _ in ()).throw(KeyboardInterrupt))
    rc, out = _capture(["fleet", "--hosts", "h", "--watch", "5"])
    assert "refresh every 5s" in out


# ---------- CLI: events --watch ----------

def test_cli_events_watch_keyboard_interrupt(monkeypatch):
    monkeypatch.setattr(events, "collect_events", lambda hours, kinds: [
        events.Event(timestamp=time.time(), kind="oom", message="killed"),
    ])

    def boom(_):
        raise KeyboardInterrupt

    monkeypatch.setattr(main.time, "sleep", boom)
    rc, out = _capture(["events", "--watch", "2"])
    assert rc == 0
    assert "watch stopped" in out
    assert "EVENTS" in out


def test_cli_events_watch_label(monkeypatch):
    monkeypatch.setattr(events, "collect_events", lambda hours, kinds: [])

    def boom(_):
        raise KeyboardInterrupt

    monkeypatch.setattr(main.time, "sleep", boom)
    rc, out = _capture(["events", "--watch", "3"])
    assert "refresh every 3s" in out


# ---------- QUICKSTART file present ----------

def test_quickstart_file_exists():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "QUICKSTART.md",
    )
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        body = f.read()
    # Sanity: must reference the most-common commands.
    for cmd in ["wtf audit", "wtf info", "wtf doctor", "wtf services",
                "wtf fleet", "wtf events", "wtf init"]:
        assert cmd in body, f"QUICKSTART.md should mention `{cmd}`"
