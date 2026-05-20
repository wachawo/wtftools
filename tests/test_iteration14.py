#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for iteration 14: wtf events + POST /run-now in wtfd."""

import io
import json
import threading
import time
import urllib.error
import urllib.request
from contextlib import redirect_stdout

from wtftools import audit, daemon, events, main


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


# ---------- events module ----------

def test_event_iso_format():
    e = events.Event(timestamp=1779278105.0, kind="oom", message="x")
    out = e.iso()
    assert "2026" in out or "2027" in out  # broad assertion: timestamp is in the right ballpark
    assert ":" in out


def test_event_iso_invalid_timestamp():
    e = events.Event(timestamp=float("inf"), kind="oom", message="x")
    out = e.iso()
    assert "?" in out


def test_parse_iso_lines_basic():
    txt = ("2026-05-20T08:55:01+0000 host kernel: out of memory\n"
           "2026-05-20T08:55:02+0000 host sshd: failed password\n"
           "garbage line with no timestamp\n")
    rows = events._parse_iso_lines(txt)
    assert len(rows) == 2
    assert rows[0][1].startswith("host kernel")


def test_parse_iso_lines_no_tz():
    txt = "2026-05-20T08:55:01 host kernel: thing\n"
    rows = events._parse_iso_lines(txt)
    assert len(rows) == 1


def test_parse_iso_lines_malformed_skipped():
    txt = ("garbage\n"
           "2026-13-99T99:99:99+0000 not-a-date\n"  # invalid date
           "2026-05-20T08:55:01+0000 valid line\n")
    rows = events._parse_iso_lines(txt)
    # at least the valid line should parse
    assert any("valid line" in r[1] for r in rows)


def test_collect_oom_no_journalctl(monkeypatch):
    monkeypatch.setattr(events.shutil, "which", lambda _: None)
    assert events._collect_oom(24) == []


def test_collect_oom_parses(monkeypatch):
    monkeypatch.setattr(events.shutil, "which", lambda _: "/bin/journalctl")
    sample = ("2026-05-20T08:55:01+0000 host kernel: Out of memory: Killed process 123\n"
              "2026-05-20T08:55:02+0000 host kernel: normal message\n"
              "2026-05-20T09:00:00+0000 host kernel: oom-killer invoked\n")
    monkeypatch.setattr(events, "run", lambda cmd, **_: (0, sample, ""))
    out = events._collect_oom(24)
    assert len(out) == 2
    assert all(e.kind == "oom" for e in out)


def test_collect_oom_failure(monkeypatch):
    monkeypatch.setattr(events.shutil, "which", lambda _: "/bin/journalctl")
    monkeypatch.setattr(events, "run", lambda cmd, **_: (1, "", "err"))
    assert events._collect_oom(24) == []


def test_collect_kernel_errors(monkeypatch):
    monkeypatch.setattr(events.shutil, "which", lambda _: "/bin/journalctl")
    sample = "2026-05-20T08:55:01+0000 host kernel: I/O error\n"
    monkeypatch.setattr(events, "run", lambda cmd, **_: (0, sample, ""))
    out = events._collect_kernel_errors(24)
    assert len(out) == 1
    assert out[0].kind == "kernel-err"


def test_collect_failed_units(monkeypatch):
    monkeypatch.setattr(events.shutil, "which", lambda _: "/bin/journalctl")
    sample = "2026-05-20T08:55:01+0000 host systemd: nginx.service: failed\n"
    monkeypatch.setattr(events, "run", lambda cmd, **_: (0, sample, ""))
    out = events._collect_failed_units(24)
    assert len(out) == 1
    assert out[0].kind == "failed-unit"


def test_collect_auth_failures(monkeypatch):
    monkeypatch.setattr(events.shutil, "which", lambda _: "/bin/journalctl")
    sample = ("2026-05-20T08:55:01+0000 host sshd: Failed password for root\n"
              "2026-05-20T08:55:02+0000 host sshd: Connection from 1.2.3.4\n"
              "2026-05-20T08:55:03+0000 host sshd: Invalid user foo\n")
    monkeypatch.setattr(events, "run", lambda cmd, **_: (0, sample, ""))
    out = events._collect_auth_failures(24)
    assert len(out) == 2
    assert all(e.kind == "auth-fail" for e in out)


def test_collect_reboots_no_last(monkeypatch):
    monkeypatch.setattr(events.shutil, "which", lambda _: None)
    assert events._collect_reboots(24) == []


def test_collect_reboots_parses(monkeypatch):
    monkeypatch.setattr(events.shutil, "which", lambda _: "/usr/bin/last")
    # Build an ISO timestamp that's safely in the recent past (within 24h)
    from datetime import datetime, timedelta, timezone
    recent_dt = datetime.now(timezone.utc) - timedelta(hours=1)
    iso = recent_dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    # Insert colon into tz to match `last` output
    iso = iso[:-2] + ":" + iso[-2:]
    sample = f"reboot   system boot  6.11.0-29-generic {iso} still running\n"
    monkeypatch.setattr(events, "run", lambda cmd, **_: (0, sample, ""))
    out = events._collect_reboots(24)
    assert len(out) == 1
    assert out[0].kind == "reboot"


def test_collect_reboots_outside_window(monkeypatch):
    monkeypatch.setattr(events.shutil, "which", lambda _: "/usr/bin/last")
    # 2000-01-01 — clearly outside any reasonable window
    sample = "reboot   system boot  5.x 2000-01-01T00:00:00+00:00 - down\n"
    monkeypatch.setattr(events, "run", lambda cmd, **_: (0, sample, ""))
    assert events._collect_reboots(24) == []


def test_collect_logins_parses(monkeypatch):
    monkeypatch.setattr(events.shutil, "which", lambda _: "/usr/bin/last")
    from datetime import datetime, timedelta, timezone
    recent = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S%z")
    recent = recent[:-2] + ":" + recent[-2:]
    sample = (
        f"alice  pts/0  10.1.1.5  {recent} still logged in\n"
        f"reboot   system boot   6.x  {recent} still running\n"  # filtered
        "\n"
        "wtmp begins ...\n"
    )
    monkeypatch.setattr(events, "run", lambda cmd, **_: (0, sample, ""))
    out = events._collect_logins(24)
    assert len(out) == 1
    assert out[0].kind == "login"
    assert "alice" in out[0].message


def test_collect_events_filters_kinds(monkeypatch):
    """Asking only for 'oom' should not invoke other collectors."""
    called = {"oom": False, "reboot": False, "auth": False}
    monkeypatch.setattr(events, "_collect_oom",
                        lambda h: (called.__setitem__("oom", True) or []))
    monkeypatch.setattr(events, "_collect_reboots",
                        lambda h: (called.__setitem__("reboot", True) or []))
    monkeypatch.setattr(events, "_collect_auth_failures",
                        lambda h: (called.__setitem__("auth", True) or []))
    events.collect_events(hours=1, kinds=["oom"])
    assert called["oom"] is True
    assert called["reboot"] is False
    assert called["auth"] is False


def test_collect_events_sorts_newest_first(monkeypatch):
    e_old = events.Event(timestamp=1000, kind="oom", message="old")
    e_new = events.Event(timestamp=2000, kind="reboot", message="new")
    monkeypatch.setattr(events, "_collect_oom", lambda h: [e_old])
    monkeypatch.setattr(events, "_collect_reboots", lambda h: [e_new])
    monkeypatch.setattr(events, "_collect_failed_units", lambda h: [])
    monkeypatch.setattr(events, "_collect_kernel_errors", lambda h: [])
    monkeypatch.setattr(events, "_collect_auth_failures", lambda h: [])
    monkeypatch.setattr(events, "_collect_logins", lambda h: [])
    out = events.collect_events(hours=24)
    assert out[0].message == "new"
    assert out[1].message == "old"


# ---------- CLI ----------

def test_cli_events_no_events(monkeypatch):
    monkeypatch.setattr(events, "collect_events", lambda hours, kinds: [])
    rc, out = _capture(["events", "--since", "24"])
    assert rc == 0
    assert "no events" in out.lower()


def test_cli_events_text(monkeypatch):
    monkeypatch.setattr(events, "collect_events", lambda hours, kinds: [
        events.Event(timestamp=1000.0, kind="oom", message="killed proc"),
        events.Event(timestamp=900.0, kind="reboot", message="system boot"),
    ])
    rc, out = _capture(["events", "--since", "24"])
    assert "EVENTS" in out
    assert "oom" in out
    assert "reboot" in out
    assert "killed proc" in out


def test_cli_events_json(monkeypatch):
    monkeypatch.setattr(events, "collect_events", lambda hours, kinds: [
        events.Event(timestamp=1000.0, kind="oom", message="killed"),
    ])
    rc, out = _capture(["events", "--format", "json"])
    data = json.loads(out)
    assert data["since_hours"] == 24
    assert len(data["events"]) == 1
    assert data["events"][0]["kind"] == "oom"


def test_cli_events_kind_filter(monkeypatch):
    captured = {}
    def fake(hours, kinds=None):
        captured["kinds"] = kinds
        return []
    monkeypatch.setattr(events, "collect_events", fake)
    _capture(["events", "--kind", "oom", "--kind", "reboot"])
    assert captured["kinds"] == ["oom", "reboot"]


def test_cli_events_limit(monkeypatch):
    monkeypatch.setattr(events, "collect_events", lambda hours, kinds: [
        events.Event(timestamp=i, kind="oom", message=f"n{i}") for i in range(10)
    ])
    rc, out = _capture(["events", "--limit", "3"])
    assert rc == 0
    # Three rows shown — count occurrences of the kind label
    assert out.count("oom") == 3


def test_cli_events_long_message_truncated(monkeypatch):
    long_msg = "x" * 300
    monkeypatch.setattr(events, "collect_events", lambda hours, kinds: [
        events.Event(timestamp=time.time(), kind="oom", message=long_msg),
    ])
    rc, out = _capture(["events"])
    assert "…" in out


# ---------- POST /run-now ----------

def test_daemon_state_wake_request():
    s = daemon.DaemonState()
    assert s.wake_event().is_set() is False
    s.request_run_now()
    assert s.wake_event().is_set() is True


def test_daemon_audit_loop_responds_to_wake(monkeypatch):
    """Setting the wake event should cut the interval short and trigger a re-run."""
    s = daemon.DaemonState()
    monkeypatch.setattr(audit, "run_audit",
                        lambda: [audit.CheckResult("x", "ok", "")])
    stop = threading.Event()
    t = threading.Thread(target=daemon._audit_loop,
                         args=(s, 30.0, stop, False), daemon=True)
    t.start()
    # Give the first run a moment to complete.
    time.sleep(0.1)
    first_count = s.run_count
    s.request_run_now()
    # The wake should pick up within ~1s; give it some headroom.
    time.sleep(1.5)
    assert s.run_count > first_count
    stop.set()
    t.join(timeout=2)


def test_post_run_now_endpoint(monkeypatch):
    """Spin up a real wtfd HTTP server, POST /run-now, check it triggered."""
    s = daemon.DaemonState()
    s.record_run([audit.CheckResult("x", "ok", "")])
    handler = daemon.make_handler(s)
    server = daemon.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, args=(0.05,),
                              daemon=True)
    thread.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/run-now", method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 202
        assert s.wake_event().is_set() is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_post_unknown_path_404(monkeypatch):
    s = daemon.DaemonState()
    handler = daemon.make_handler(s)
    server = daemon.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, args=(0.05,),
                              daemon=True)
    thread.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/unknown", method="POST", data=b"")
        try:
            urllib.request.urlopen(req, timeout=3)
            assert False, "expected 404"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_post_run_now_auth(monkeypatch):
    s = daemon.DaemonState()
    handler = daemon.make_handler(s, auth_token="secret")
    server = daemon.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, args=(0.05,),
                              daemon=True)
    thread.start()
    try:
        # No token → 401
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/run-now", method="POST", data=b"")
        try:
            urllib.request.urlopen(req, timeout=3)
            assert False, "expected 401"
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        # With token → 202
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/run-now", method="POST", data=b"",
            headers={"Authorization": "Bearer secret"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 202
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
