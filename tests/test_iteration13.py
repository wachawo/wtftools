#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for iteration 13: wtf compare + doctor --check-updates."""

import io
import json
import urllib.error
import urllib.request
from contextlib import redirect_stdout

from wtftools import fleet, main


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


# ---------- compare_hosts (pure unit) ----------

def _host(target, host_name, results, ok=True, error=None):
    return fleet.FleetHost(
        target=target, url=f"http://{target}/audit.json",
        ok=ok, error=error, host=host_name,
        results=results or [],
    )


def test_compare_identical():
    a = _host("a", "alpha", [
        {"name": "uptime", "status": "ok", "message": "3d"},
        {"name": "swap", "status": "ok", "message": "10%"},
    ])
    b = _host("b", "beta", [
        {"name": "uptime", "status": "ok", "message": "3d"},
        {"name": "swap", "status": "ok", "message": "10%"},
    ])
    rows = fleet.compare_hosts(a, b)
    assert len(rows) == 2
    assert all(r.kind == "same" for r in rows)


def test_compare_differ_status():
    a = _host("a", "alpha",
              [{"name": "swap", "status": "ok", "message": "10%"}])
    b = _host("b", "beta",
              [{"name": "swap", "status": "fail", "message": "99%"}])
    rows = fleet.compare_hosts(a, b)
    assert len(rows) == 1
    assert rows[0].kind == "differ"
    assert rows[0].a_status == "ok"
    assert rows[0].b_status == "fail"


def test_compare_differ_message_same_status():
    """Same status but message differs → still drift."""
    a = _host("a", "alpha",
              [{"name": "uptime", "status": "ok", "message": "3d"}])
    b = _host("b", "beta",
              [{"name": "uptime", "status": "ok", "message": "5d"}])
    rows = fleet.compare_hosts(a, b)
    assert rows[0].kind == "differ"


def test_compare_a_only():
    a = _host("a", "alpha",
              [{"name": "only-a", "status": "ok", "message": "x"}])
    b = _host("b", "beta", [])
    rows = fleet.compare_hosts(a, b)
    assert len(rows) == 1
    assert rows[0].kind == "a-only"
    assert rows[0].b_status is None


def test_compare_b_only():
    a = _host("a", "alpha", [])
    b = _host("b", "beta",
              [{"name": "only-b", "status": "warn", "message": "y"}])
    rows = fleet.compare_hosts(a, b)
    assert len(rows) == 1
    assert rows[0].kind == "b-only"
    assert rows[0].a_status is None


def test_compare_mixed():
    a = _host("a", "alpha", [
        {"name": "uptime", "status": "ok", "message": "3d"},
        {"name": "only-a", "status": "warn", "message": "x"},
        {"name": "swap", "status": "fail", "message": "99%"},
    ])
    b = _host("b", "beta", [
        {"name": "uptime", "status": "ok", "message": "3d"},          # same
        {"name": "swap", "status": "ok", "message": "10%"},            # differ
        {"name": "only-b", "status": "ok", "message": "y"},            # b-only
    ])
    rows = fleet.compare_hosts(a, b)
    kinds = sorted(r.kind for r in rows)
    assert kinds == ["a-only", "b-only", "differ", "same"]


# ---------- CLI: wtf compare ----------

def test_cli_compare_both_ok(monkeypatch):
    fake_a = _host("a:8765", "alpha", [
        {"name": "uptime", "status": "ok", "message": "3d"},
        {"name": "swap", "status": "fail", "message": "99%"},
    ])
    fake_b = _host("b:8765", "beta", [
        {"name": "uptime", "status": "ok", "message": "5d"},
        {"name": "swap", "status": "ok", "message": "10%"},
    ])
    monkeypatch.setattr(fleet, "fetch_all",
                        lambda *a, **kw: [fake_a, fake_b])
    rc, out = _capture(["compare", "a:8765", "b:8765"])
    assert rc == 1  # drift exists
    assert "COMPARE" in out
    assert "alpha" in out and "beta" in out
    assert "DIFF" in out
    assert "3d" in out and "5d" in out


def test_cli_compare_identical(monkeypatch):
    same_results = [{"name": "uptime", "status": "ok", "message": "3d"}]
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: [
        _host("a", "alpha", same_results),
        _host("b", "beta", same_results),
    ])
    rc, out = _capture(["compare", "a", "b"])
    assert rc == 0
    assert "0 drifted" in out
    assert "identical" in out.lower()


def test_cli_compare_only_drift(monkeypatch):
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: [
        _host("a", "alpha", [
            {"name": "uptime", "status": "ok", "message": "3d"},
            {"name": "swap", "status": "fail", "message": "99%"},
        ]),
        _host("b", "beta", [
            {"name": "uptime", "status": "ok", "message": "3d"},
            {"name": "swap", "status": "ok", "message": "10%"},
        ]),
    ])
    rc, out = _capture(["compare", "a", "b", "--only-drift"])
    # uptime is identical → should not show; only swap row visible
    assert "swap" in out
    # Verify uptime row is suppressed: the uptime values appear only in summary
    # we check for the row presence (would have " 3d " value)
    # The "[ =  ]" marker should not be in output.
    assert "[ =  ]" not in out


def test_cli_compare_json(monkeypatch):
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: [
        _host("a", "alpha", [{"name": "x", "status": "ok", "message": "1"}]),
        _host("b", "beta", [{"name": "x", "status": "warn", "message": "2"}]),
    ])
    rc, out = _capture(["compare", "a", "b", "--format", "json"])
    data = json.loads(out)
    assert data["a"]["host"] == "alpha"
    assert data["b"]["host"] == "beta"
    assert data["drift_count"] == 1
    assert len(data["rows"]) == 1
    assert data["rows"][0]["kind"] == "differ"


def test_cli_compare_one_host_down(monkeypatch):
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: [
        _host("a", "alpha", [], ok=True),
        _host("b", "", [], ok=False, error="connection refused"),
    ])
    rc, out = _capture(["compare", "a", "b"])
    assert rc == 2
    assert "connection refused" in out


def test_cli_compare_both_down(monkeypatch):
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: [
        _host("a", "", [], ok=False, error="no route"),
        _host("b", "", [], ok=False, error="timeout"),
    ])
    rc, out = _capture(["compare", "a", "b"])
    assert rc == 2
    assert "no route" in out
    assert "timeout" in out


def test_cli_compare_down_json(monkeypatch):
    monkeypatch.setattr(fleet, "fetch_all", lambda *a, **kw: [
        _host("a", "", [], ok=False, error="down"),
        _host("b", "beta", [{"name": "x", "status": "ok", "message": ""}]),
    ])
    rc, out = _capture(["compare", "a", "b", "--format", "json"])
    data = json.loads(out)
    assert data["a"]["ok"] is False
    assert data["b"]["ok"] is True
    assert rc == 2


def test_cli_compare_token_file(monkeypatch, tmp_path):
    token_file = tmp_path / "tok"
    token_file.write_text("secret")
    captured = {}

    def fake_fetch_all(targets, timeout, token=None, **kw):
        captured["token"] = token
        return [_host("a", "alpha", []), _host("b", "beta", [])]

    monkeypatch.setattr(fleet, "fetch_all", fake_fetch_all)
    rc, _ = _capture(["compare", "a", "b", "--token-file", str(token_file)])
    assert captured["token"] == "secret"


def test_cli_compare_token_missing():
    rc, out = _capture(["compare", "a", "b", "--token-file", "/nonexistent"])
    assert rc == 2
    assert "token" in out.lower()


def test_compare_cell_truncation():
    long_msg = "x" * 100
    out = main._compare_cell("ok", long_msg)
    assert "…" in out


def test_compare_cell_all_statuses():
    assert "ok" in main._compare_cell("ok", "fine")
    assert "warn" in main._compare_cell("warn", "x")
    assert "fail" in main._compare_cell("fail", "y")
    assert "skip" in main._compare_cell("skip", "z")


# ---------- doctor --check-updates ----------

def test_version_tuple_basic():
    assert main._version_tuple("0.1.0") == (0, 1, 0)
    assert main._version_tuple("1.2.3") == (1, 2, 3)
    assert main._version_tuple("2.0") == (2, 0)
    # Non-numeric chunks collapse to 0.
    assert main._version_tuple("0.1.0rc1") == (0, 1, 0)
    assert main._version_tuple("dev") == (0,)


def test_version_tuple_ordering():
    assert main._version_tuple("0.2.0") > main._version_tuple("0.1.0")
    assert main._version_tuple("1.0.0") > main._version_tuple("0.9.99")


def test_fetch_pypi_version_success(monkeypatch):
    body = json.dumps({"info": {"version": "9.9.9"}}).encode("utf-8")

    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return body

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda url, timeout=3.0: FakeResp())
    assert main._fetch_pypi_version() == "9.9.9"


def test_fetch_pypi_version_network_failure(monkeypatch):
    def boom(url, timeout=3.0):
        raise urllib.error.URLError("no net")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert main._fetch_pypi_version() is None


def test_fetch_pypi_version_malformed_json(monkeypatch):
    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return b"not json"

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda url, timeout=3.0: FakeResp())
    assert main._fetch_pypi_version() is None


def test_doctor_check_updates_outdated(monkeypatch):
    """Doctor with --check-updates and PyPI showing a newer version → warn row."""
    monkeypatch.setattr(main, "_fetch_pypi_version", lambda: "99.99.99")
    rc, out = _capture(["doctor", "--check-updates"])
    assert rc == 0
    assert "pypi" in out.lower() or "PyPI" in out
    assert "99.99.99" in out


def test_doctor_check_updates_up_to_date(monkeypatch):
    from wtftools import __version__
    monkeypatch.setattr(main, "_fetch_pypi_version", lambda: __version__)
    rc, out = _capture(["doctor", "--check-updates"])
    assert "up to date" in out


def test_doctor_check_updates_network_skip(monkeypatch):
    monkeypatch.setattr(main, "_fetch_pypi_version", lambda: None)
    rc, out = _capture(["doctor", "--check-updates"])
    assert "could not reach PyPI" in out or "SKIP" in out.upper()


def test_doctor_no_update_check_by_default(monkeypatch):
    """Without --check-updates, doctor does NOT hit the network."""
    called = {"hit": False}
    def boom():
        called["hit"] = True
        return None
    monkeypatch.setattr(main, "_fetch_pypi_version", boom)
    rc, out = _capture(["doctor"])
    assert rc == 0
    assert called["hit"] is False
    assert "pypi" not in out.lower()


def test_doctor_check_updates_json(monkeypatch):
    monkeypatch.setattr(main, "_fetch_pypi_version", lambda: "99.0.0")
    rc, out = _capture(["doctor", "--check-updates", "--format", "json"])
    data = json.loads(out)
    update_row = next((c for c in data["checks"] if c["name"] == "pypi update check"), None)
    assert update_row is not None
    assert update_row["status"] == "warn"
