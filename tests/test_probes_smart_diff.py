#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP/TCP probes, SMART, wtf diff, and --format plain."""

import io
import json
from contextlib import redirect_stdout
from unittest import mock

import pytest

from wtftools import audit, config, main, snapshot, sysinfo


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


# ---- HTTP probe ----


def test_probe_http_invalid_scheme():
    r = sysinfo.probe_http("ftp://example")
    assert r["error"] is not None
    assert "scheme" in r["error"]


def test_probe_http_success(monkeypatch):
    import http.client as hc

    fake_resp = mock.Mock(status=200)
    fake_conn = mock.Mock()
    fake_conn.getresponse.return_value = fake_resp
    monkeypatch.setattr(hc, "HTTPConnection", lambda *a, **kw: fake_conn)
    r = sysinfo.probe_http("http://example.com/")
    assert r["status_code"] == 200
    assert r["error"] is None
    assert r["latency_ms"] is not None


def test_probe_http_https_branch(monkeypatch):
    import http.client as hc

    fake_resp = mock.Mock(status=204)
    fake_conn = mock.Mock()
    fake_conn.getresponse.return_value = fake_resp
    called = {"https": False}

    def fake_https(*a, **kw):
        called["https"] = True
        return fake_conn

    monkeypatch.setattr(hc, "HTTPSConnection", fake_https)
    r = sysinfo.probe_http("https://secure.example/")
    assert r["status_code"] == 204
    assert called["https"] is True


def test_probe_http_failure(monkeypatch):
    import http.client as hc

    def boom(*a, **kw):
        raise ConnectionError("refused")

    monkeypatch.setattr(hc, "HTTPConnection", boom)
    r = sysinfo.probe_http("http://example/")
    assert r["status_code"] is None
    assert "ConnectionError" in r["error"]


# ---- TCP probe ----


def test_probe_tcp_invalid_format():
    r = sysinfo.probe_tcp("no_colon")
    assert "expected host:port" in r["error"]


def test_probe_tcp_bad_port():
    r = sysinfo.probe_tcp("localhost:nope")
    assert "invalid port" in r["error"]


def test_probe_tcp_success(monkeypatch):
    fake_sock = mock.Mock()
    monkeypatch.setattr("socket.create_connection", lambda *a, **kw: fake_sock)
    r = sysinfo.probe_tcp("localhost:80")
    assert r["error"] is None
    assert r["latency_ms"] is not None
    fake_sock.close.assert_called_once()


def test_probe_tcp_refused(monkeypatch):
    def boom(*a, **kw):
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr("socket.create_connection", boom)
    r = sysinfo.probe_tcp("localhost:65535")
    assert r["latency_ms"] is None
    assert "ConnectionRefusedError" in r["error"]


def test_probe_tcp_ipv6_bracket(monkeypatch):
    captured = {}

    def fake_conn(addr, timeout):
        captured["host"] = addr[0]
        return mock.Mock()

    monkeypatch.setattr("socket.create_connection", fake_conn)
    sysinfo.probe_tcp("[::1]:80")
    assert captured["host"] == "::1"


# ---- HTTP/TCP probe checks ----


def test_check_http_probes_empty(monkeypatch):
    config.set_config(config.Config(http_probes=""))
    assert audit._check_http_probes() == []
    config.set_config(config.Config())


def test_check_http_probes_ok(monkeypatch):
    config.set_config(config.Config(http_probes="http://x"))
    monkeypatch.setattr(audit.sysinfo, "probe_http", lambda url, timeout: {"url": url, "status_code": 200, "latency_ms": 10.0, "error": None})
    results = audit._check_http_probes()
    assert len(results) == 1
    assert results[0].status == "ok"
    config.set_config(config.Config())


def test_check_http_probes_slow(monkeypatch):
    config.set_config(config.Config(http_probes="http://x", probe_slow_ms=100))
    monkeypatch.setattr(audit.sysinfo, "probe_http", lambda url, timeout: {"url": url, "status_code": 200, "latency_ms": 500.0, "error": None})
    r = audit._check_http_probes()[0]
    assert r.status == "warn"
    config.set_config(config.Config())


def test_check_http_probes_500(monkeypatch):
    config.set_config(config.Config(http_probes="http://x"))
    monkeypatch.setattr(audit.sysinfo, "probe_http", lambda url, timeout: {"url": url, "status_code": 503, "latency_ms": 5.0, "error": None})
    r = audit._check_http_probes()[0]
    assert r.status == "fail"
    config.set_config(config.Config())


def test_check_http_probes_error(monkeypatch):
    config.set_config(config.Config(http_probes="http://x"))
    monkeypatch.setattr(audit.sysinfo, "probe_http", lambda url, timeout: {"url": url, "status_code": None, "latency_ms": None, "error": "timeout"})
    r = audit._check_http_probes()[0]
    assert r.status == "fail"
    config.set_config(config.Config())


def test_check_tcp_probes_ok(monkeypatch):
    config.set_config(config.Config(tcp_probes="host:80,host:443"))
    monkeypatch.setattr(audit.sysinfo, "probe_tcp", lambda target, timeout: {"target": target, "latency_ms": 5.0, "error": None})
    results = audit._check_tcp_probes()
    assert len(results) == 2
    assert all(r.status == "ok" for r in results)
    config.set_config(config.Config())


def test_check_tcp_probes_slow(monkeypatch):
    config.set_config(config.Config(tcp_probes="host:80", probe_slow_ms=10))
    monkeypatch.setattr(audit.sysinfo, "probe_tcp", lambda target, timeout: {"target": target, "latency_ms": 50.0, "error": None})
    assert audit._check_tcp_probes()[0].status == "warn"
    config.set_config(config.Config())


def test_check_tcp_probes_refused(monkeypatch):
    config.set_config(config.Config(tcp_probes="host:99999"))
    monkeypatch.setattr(audit.sysinfo, "probe_tcp", lambda target, timeout: {"target": target, "latency_ms": None, "error": "ConnectionRefusedError"})
    assert audit._check_tcp_probes()[0].status == "fail"
    config.set_config(config.Config())


def test_check_tcp_probes_empty():
    config.set_config(config.Config(tcp_probes=""))
    assert audit._check_tcp_probes() == []
    config.set_config(config.Config())


# ---- SMART ----


def test_get_block_devices_no_lsblk(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: None)
    assert sysinfo.get_block_devices() == []


def test_get_block_devices_parses(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/lsblk")
    out = "sda disk\nsda1 part\nsdb disk\nloop0 loop\nnvme0n1 disk\n"
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, out, ""))
    devices = sysinfo.get_block_devices()
    assert "/dev/sda" in devices
    assert "/dev/sdb" in devices
    assert "/dev/nvme0n1" in devices
    assert "/dev/loop0" not in devices
    assert "/dev/sda1" not in devices


def test_get_block_devices_failure(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/lsblk")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (1, "", ""))
    assert sysinfo.get_block_devices() == []


def test_get_smart_status_no_smartctl(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: None)
    assert sysinfo.get_smart_status() is None


def test_get_smart_status_no_devices(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/sbin/smartctl")
    monkeypatch.setattr(sysinfo, "get_block_devices", lambda: [])
    assert sysinfo.get_smart_status() == []


def test_get_smart_status_passing(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/sbin/smartctl")
    monkeypatch.setattr(sysinfo, "get_block_devices", lambda: ["/dev/sda"])
    json_out = json.dumps({"smart_status": {"passed": True}})
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, json_out, ""))
    result = sysinfo.get_smart_status()
    assert len(result) == 1
    assert result[0]["passed"] is True


def test_get_smart_status_failing(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/sbin/smartctl")
    monkeypatch.setattr(sysinfo, "get_block_devices", lambda: ["/dev/sda"])
    json_out = json.dumps({"smart_status": {"passed": False}})
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (8, json_out, ""))
    result = sysinfo.get_smart_status()
    assert result[0]["passed"] is False


def test_get_smart_status_unparseable(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/sbin/smartctl")
    monkeypatch.setattr(sysinfo, "get_block_devices", lambda: ["/dev/sda"])
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, "not json", ""))
    assert sysinfo.get_smart_status() == []


def test_check_smart_skip(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_smart_status", lambda: None)
    assert audit._check_smart().status == "skip"
    monkeypatch.setattr(audit.sysinfo, "get_smart_status", lambda: [])
    assert audit._check_smart().status == "skip"


def test_check_smart_ok(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_smart_status", lambda: [{"device": "/dev/sda", "passed": True, "exit_code": 0, "message": ""}])
    assert audit._check_smart().status == "ok"


def test_check_smart_fail(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_smart_status", lambda: [{"device": "/dev/sda", "passed": False, "exit_code": 8, "message": "media error"}])
    r = audit._check_smart()
    assert r.status == "fail"
    assert "FAILED" in " ".join(r.detail)


# ---- wtf diff ----


def test_diff_no_snapshots(monkeypatch, tmp_path):
    monkeypatch.setenv("WTFTOOLS_SNAPSHOT_DIR", str(tmp_path))
    rc, out = _capture(["diff"])
    assert rc == 0
    assert "no snapshots" in out


def test_diff_json_no_snapshots(monkeypatch, tmp_path):
    monkeypatch.setenv("WTFTOOLS_SNAPSHOT_DIR", str(tmp_path))
    rc, out = _capture(["diff", "--format", "json"])
    data = json.loads(out)
    assert data["diff"] == []


def test_diff_latest(monkeypatch, tmp_path):
    monkeypatch.setenv("WTFTOOLS_SNAPSHOT_DIR", str(tmp_path))
    snapshot.save_snapshot([audit.CheckResult("swap", "ok", "10%")], host="h", directory=str(tmp_path))
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("swap", "fail", "99%")])
    rc, out = _capture(["diff"])
    assert rc == 0
    assert "REG" in out or "regression" in out.lower()


def test_diff_snapshot_index(monkeypatch, tmp_path):
    monkeypatch.setenv("WTFTOOLS_SNAPSHOT_DIR", str(tmp_path))
    snapshot.save_snapshot([audit.CheckResult("a", "ok", "")], host="h", directory=str(tmp_path))
    # Make sure timestamps differ
    import time as _t

    _t.sleep(1.1)
    snapshot.save_snapshot([audit.CheckResult("a", "warn", "")], host="h", directory=str(tmp_path))
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("a", "fail", "")])
    # Default --snapshot=0 → diff vs newest (warn → fail)
    rc, out = _capture(["diff"])
    assert "WRSE" in out or "worsened" in out.lower()
    # --snapshot=1 → diff vs older (ok → fail)
    rc, out = _capture(["diff", "--snapshot", "1"])
    assert "REG" in out or "regression" in out.lower()


def test_diff_against_two_files(tmp_path):
    a = tmp_path / "20260101T000000Z.json"
    b = tmp_path / "20260101T010000Z.json"
    a.write_text(
        json.dumps(
            {
                "timestamp": "old",
                "host": "h",
                "results": [{"name": "x", "status": "ok", "message": "fine", "detail": []}],
            }
        )
    )
    b.write_text(
        json.dumps(
            {
                "timestamp": "new",
                "host": "h",
                "results": [{"name": "x", "status": "fail", "message": "broke", "detail": []}],
            }
        )
    )
    rc, out = _capture(["diff", "--against", str(a), str(b)])
    assert rc == 0
    assert "REG" in out or "regression" in out.lower()


def test_diff_against_bad_args(tmp_path):
    a = tmp_path / "a.json"
    a.write_text("{}")
    # argparse rejects --against with 1 arg (nargs=2) → SystemExit(2)
    with pytest.raises(SystemExit) as exc:
        _capture(["diff", "--against", str(a)])
    assert exc.value.code != 0


def test_diff_against_unreadable(tmp_path):
    rc, out = _capture(["diff", "--against", "/nonexistent/a.json", "/nonexistent/b.json"])
    assert rc == 1
    assert "cannot read" in out


def test_diff_corrupt_snapshot(monkeypatch, tmp_path):
    monkeypatch.setenv("WTFTOOLS_SNAPSHOT_DIR", str(tmp_path))
    (tmp_path / "20260101T000000Z.json").write_text("not json")
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("x", "ok", "")])
    rc, out = _capture(["diff"])
    assert rc == 1
    assert "cannot read" in out


# ---- --format plain ----


def test_audit_plain_format(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("a", "ok", "fine"),
            audit.CheckResult("b", "fail", "broke"),
        ],
    )
    rc, out = _capture(["audit", "--format", "plain"])
    lines = out.strip().split("\n")
    assert lines == ["ok\ta\tfine", "fail\tb\tbroke"]
    assert rc == 2


# ---- registry ----


def test_new_checks_in_registry():
    names = audit.list_check_names()
    assert "smart" in names
    assert "http-probes" in names
    assert "tcp-probes" in names
