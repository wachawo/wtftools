#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for additions in iteration 2: restart-loops, network-errors, brief mode."""

import io
from contextlib import redirect_stdout

from wtftools import audit, main, sysinfo


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


# ---- restart loops ----


def test_get_service_restart_counts_none(monkeypatch):
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, "", ""))
    assert sysinfo.get_service_restart_counts() == []


def test_get_service_restart_counts_parses(monkeypatch):
    list_out = "ssh.service loaded active running OpenSSH\nnginx.service loaded active running nginx\n"
    show_out = "Id=ssh.service\nNRestarts=0\n\n" "Id=nginx.service\nNRestarts=12\n"

    def fake_run(cmd, **_):
        if "list-units" in cmd:
            return (0, list_out, "")
        return (0, show_out, "")

    monkeypatch.setattr(sysinfo, "run", fake_run)
    result = sysinfo.get_service_restart_counts(threshold=3)
    assert len(result) == 1
    assert result[0]["name"] == "nginx.service"
    assert result[0]["restarts"] == 12


def test_get_service_restart_counts_bad_value(monkeypatch):
    list_out = "x.service loaded active running\n"
    show_out = "Id=x.service\nNRestarts=garbage\n"

    def fake_run(cmd, **_):
        if "list-units" in cmd:
            return (0, list_out, "")
        return (0, show_out, "")

    monkeypatch.setattr(sysinfo, "run", fake_run)
    assert sysinfo.get_service_restart_counts() == []


def test_check_restart_loops_skip_no_systemctl(monkeypatch):
    monkeypatch.setattr(audit.shutil, "which", lambda _: None)
    assert audit._check_restart_loops().status == "skip"


def test_check_restart_loops_ok(monkeypatch):
    monkeypatch.setattr(audit.shutil, "which", lambda _: "/bin/systemctl")
    monkeypatch.setattr(audit.sysinfo, "get_service_restart_counts", lambda threshold: [])
    assert audit._check_restart_loops().status == "ok"


def test_check_restart_loops_warn(monkeypatch):
    monkeypatch.setattr(audit.shutil, "which", lambda _: "/bin/systemctl")
    monkeypatch.setattr(audit.sysinfo, "get_service_restart_counts", lambda threshold: [{"name": "x.service", "restarts": 4}])
    r = audit._check_restart_loops()
    assert r.status == "warn"


def test_check_restart_loops_fail(monkeypatch):
    monkeypatch.setattr(audit.shutil, "which", lambda _: "/bin/systemctl")
    monkeypatch.setattr(audit.sysinfo, "get_service_restart_counts", lambda threshold: [{"name": "x.service", "restarts": 50}])
    r = audit._check_restart_loops()
    assert r.status == "fail"


# ---- network errors ----


def test_get_network_errors_returns_list(monkeypatch):
    monkeypatch.setattr(sysinfo.os.path, "isdir", lambda p: True)
    monkeypatch.setattr(sysinfo.os, "listdir", lambda p: ["lo", "eth0", "veth0", "eth1"])

    def fake_read(path):
        if "eth0" in path:
            if path.endswith("rx_errors"):
                return "5"
            if path.endswith("tx_errors"):
                return "10"
            if path.endswith("rx_dropped"):
                return "100"
            if path.endswith("tx_dropped"):
                return "0"
        if "eth1" in path:
            return "0"
        return ""

    monkeypatch.setattr(sysinfo, "read_file", fake_read)
    out = sysinfo.get_network_errors()
    assert len(out) == 1
    assert out[0]["iface"] == "eth0"
    assert out[0]["total"] == 115


def test_get_network_errors_no_sysfs(monkeypatch):
    monkeypatch.setattr(sysinfo.os.path, "isdir", lambda p: False)
    assert sysinfo.get_network_errors() == []


def test_get_network_errors_listdir_error(monkeypatch):
    monkeypatch.setattr(sysinfo.os.path, "isdir", lambda p: True)

    def boom(_):
        raise OSError

    monkeypatch.setattr(sysinfo.os, "listdir", boom)
    assert sysinfo.get_network_errors() == []


def test_check_network_errors_ok(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_network_errors", lambda: [])
    assert audit._check_network_errors().status == "ok"


def test_check_network_errors_minor(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_network_errors", lambda: [{"iface": "eth0", "rx_errors": 1, "tx_errors": 0, "rx_dropped": 1, "tx_dropped": 0, "total": 2}])
    r = audit._check_network_errors()
    assert r.status == "ok"


def test_check_network_errors_severe(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_network_errors", lambda: [{"iface": "eth0", "rx_errors": 1500, "tx_errors": 0, "rx_dropped": 0, "tx_dropped": 0, "total": 1500}])
    r = audit._check_network_errors()
    assert r.status == "warn"


# ---- brief mode ----


def test_brief_all_good(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("a", "ok", ""),
            audit.CheckResult("b", "ok", ""),
            audit.CheckResult("c", "skip", ""),
        ],
    )
    rc, out = _capture(["audit", "--brief"])
    assert rc == 0
    assert "all good" in out


def test_brief_with_fail(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("a", "fail", "boom message"),
            audit.CheckResult("b", "warn", "watch me"),
        ],
    )
    rc, out = _capture(["audit", "--brief"])
    assert rc == 2
    assert "fail" in out
    assert "boom" in out


def test_brief_with_only_warns(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("a", "warn", "soft"),
        ],
    )
    rc, _ = _capture(["audit", "--brief"])
    assert rc == 1


def test_brief_truncates_long_messages(monkeypatch):
    long = "x" * 200
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("n", "fail", long),
        ],
    )
    _, out = _capture(["audit", "--brief"])
    assert "…" in out


def test_brief_more_than_three_problems(monkeypatch):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult(f"a{i}", "warn", "x") for i in range(5)])
    _, out = _capture(["audit", "--brief"])
    assert "+2 more" in out


# NB: plugin infrastructure (wtftools/plugin_sdk.py, wtftools/checks/plugins.py
# and the `plugin:*` registry merge in audit.run_audit) was removed entirely
# in v0.1.0 — wtftools is a one-shot CLI with built-in checks only.
