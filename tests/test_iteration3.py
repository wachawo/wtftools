#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for iteration-3 additions: TCP retransmits, wtf services, --ignore, config integration."""

import io
import json
from contextlib import redirect_stdout

from wtftools import audit, config, main
from wtftools.checks import sysinfo


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


# ---- TCP retransmits ----

SAMPLE_SNMP_FIRST = """Ip: Forwarding DefaultTTL InReceives
Ip: 1 64 1000
Tcp: RtoAlgorithm RtoMin RtoMax MaxConn ActiveOpens PassiveOpens AttemptFails EstabResets CurrEstab InSegs OutSegs RetransSegs InErrs OutRsts
Tcp: 1 200 120000 -1 100 200 0 0 5 1000 2000 10 0 0
"""

SAMPLE_SNMP_SECOND = """Ip: Forwarding DefaultTTL InReceives
Ip: 1 64 1500
Tcp: RtoAlgorithm RtoMin RtoMax MaxConn ActiveOpens PassiveOpens AttemptFails EstabResets CurrEstab InSegs OutSegs RetransSegs InErrs OutRsts
Tcp: 1 200 120000 -1 110 220 0 0 5 1100 2100 20 0 0
"""


def test_snap_tcp_parses(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: SAMPLE_SNMP_FIRST)
    snap = sysinfo._snap_tcp()
    assert snap is not None
    assert snap["OutSegs"] == 2000
    assert snap["RetransSegs"] == 10


def test_snap_tcp_no_file(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: "")
    assert sysinfo._snap_tcp() is None


def test_snap_tcp_malformed(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: "Tcp: only one line\n")
    assert sysinfo._snap_tcp() is None


def test_tcp_retransmit_rate(monkeypatch):
    state = {"calls": 0}

    def fake_read(_):
        state["calls"] += 1
        return SAMPLE_SNMP_FIRST if state["calls"] == 1 else SAMPLE_SNMP_SECOND

    monkeypatch.setattr(sysinfo, "read_file", fake_read)
    monkeypatch.setattr(sysinfo.time, "sleep", lambda _: None)
    rate = sysinfo.get_tcp_retransmit_rate()
    # delta out = 100, delta retrans = 10 → 10%
    assert rate == 10.0


def test_tcp_retransmit_zero_traffic(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: SAMPLE_SNMP_FIRST)
    monkeypatch.setattr(sysinfo.time, "sleep", lambda _: None)
    assert sysinfo.get_tcp_retransmit_rate() == 0.0


def test_tcp_retransmit_first_fails(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: "")
    monkeypatch.setattr(sysinfo.time, "sleep", lambda _: None)
    assert sysinfo.get_tcp_retransmit_rate() is None


def test_tcp_retransmit_second_fails(monkeypatch):
    state = {"calls": 0}

    def fake_read(_):
        state["calls"] += 1
        return SAMPLE_SNMP_FIRST if state["calls"] == 1 else ""

    monkeypatch.setattr(sysinfo, "read_file", fake_read)
    monkeypatch.setattr(sysinfo.time, "sleep", lambda _: None)
    assert sysinfo.get_tcp_retransmit_rate() is None


def test_check_tcp_retransmits_states(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_tcp_retransmit_rate", lambda: None)
    assert audit._check_tcp_retransmits().status == "skip"
    monkeypatch.setattr(audit.sysinfo, "get_tcp_retransmit_rate", lambda: 0.1)
    assert audit._check_tcp_retransmits().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_tcp_retransmit_rate", lambda: 2.0)
    assert audit._check_tcp_retransmits().status == "warn"
    monkeypatch.setattr(audit.sysinfo, "get_tcp_retransmit_rate", lambda: 10.0)
    assert audit._check_tcp_retransmits().status == "fail"


# ---- wtf services ----

def test_get_service_details_not_found(monkeypatch):
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, "", ""))
    assert sysinfo.get_service_details("nope") is None


def test_get_service_details_parses(monkeypatch):
    out = ("Id=nginx.service\nDescription=High-perf web\nActiveState=active\n"
           "SubState=running\nResult=success\nMainPID=1234\nNRestarts=0\n"
           "LoadState=loaded\nUnitFileState=enabled\nMemoryCurrent=8388608\n"
           "TasksCurrent=4\n")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, out, ""))
    d = sysinfo.get_service_details("nginx")
    assert d is not None
    assert d["Id"] == "nginx.service"
    assert d["ActiveState"] == "active"


def test_get_service_details_not_found_via_loadstate(monkeypatch):
    out = "Id=fake.service\nLoadState=not-found\n"
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, out, ""))
    assert sysinfo.get_service_details("fake") is None


def test_get_service_journal(monkeypatch):
    monkeypatch.setattr(sysinfo, "run",
                        lambda cmd, **_: (0, "line1\nline2\n\nline3\n", ""))
    out = sysinfo.get_service_journal("nginx")
    assert out == ["line1", "line2", "line3"]


def test_get_service_journal_failure(monkeypatch):
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (1, "", ""))
    assert sysinfo.get_service_journal("nginx") == []


def test_cmd_services_no_systemctl(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda _: None)
    rc, out = _capture(["services", "nginx"])
    assert rc == 2
    assert "not available" in out


def test_cmd_services_not_found(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda _: "/bin/systemctl")
    monkeypatch.setattr(sysinfo, "get_service_details", lambda name: None)
    rc, out = _capture(["services", "fake"])
    assert rc == 1
    assert "not found" in out


def test_cmd_services_active(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda _: "/bin/systemctl")
    monkeypatch.setattr(sysinfo, "get_service_details", lambda name: {
        "Id": "nginx.service", "Description": "web", "ActiveState": "active",
        "SubState": "running", "Result": "success", "MainPID": "1234",
        "NRestarts": "0", "UnitFileState": "enabled", "MemoryCurrent": "1048576",
        "TasksCurrent": "2", "FragmentPath": "/lib/systemd/system/nginx.service",
    })
    monkeypatch.setattr(sysinfo, "get_service_journal", lambda name, lines: ["log line 1"])
    monkeypatch.setattr(main, "_ports_for_pid", lambda pid: [{"port": 80, "addr": "0.0.0.0"}])
    rc, out = _capture(["services", "nginx"])
    assert rc == 0
    assert "active" in out
    assert "nginx" in out.lower()
    assert "80" in out


def test_cmd_services_failed(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda _: "/bin/systemctl")
    monkeypatch.setattr(sysinfo, "get_service_details", lambda name: {
        "Id": "x.service", "ActiveState": "failed", "SubState": "failed",
        "Result": "exit-code", "MainPID": "0", "NRestarts": "5",
    })
    monkeypatch.setattr(sysinfo, "get_service_journal", lambda name, lines: [])
    rc, out = _capture(["services", "x"])
    assert rc == 1
    assert "failed" in out


def test_cmd_services_json(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda _: "/bin/systemctl")
    monkeypatch.setattr(sysinfo, "get_service_details", lambda name: {
        "Id": "x.service", "ActiveState": "active", "SubState": "running",
        "Result": "success", "MainPID": "1",
    })
    monkeypatch.setattr(sysinfo, "get_service_journal", lambda name, lines: ["L"])
    monkeypatch.setattr(main, "_ports_for_pid", lambda pid: [])
    rc, out = _capture(["services", "x", "--format", "json"])
    data = json.loads(out)
    assert data["details"]["Id"] == "x.service"
    assert data["journal"] == ["L"]


def test_cmd_services_json_not_found(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda _: "/bin/systemctl")
    monkeypatch.setattr(sysinfo, "get_service_details", lambda name: None)
    rc, out = _capture(["services", "x", "--format", "json"])
    data = json.loads(out)
    assert "error" in data


def test_ports_for_pid_invalid_pid():
    assert main._ports_for_pid("0") == []
    assert main._ports_for_pid("garbage") == []
    assert main._ports_for_pid("") == []


def test_ports_for_pid_no_psutil(monkeypatch):
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", False)
    assert main._ports_for_pid("1234") == []


# ---- --ignore flag ----

def test_audit_ignore_short_name(monkeypatch):
    monkeypatch.setattr(audit, "_all_check_callables", lambda: {
        "memory": lambda: audit.CheckResult("memory", "ok", ""),
        "swap": lambda: audit.CheckResult("swap", "fail", "boom"),
    })
    results = audit.run_audit(ignore=["swap"])
    assert {r.name for r in results} == {"memory"}


def test_audit_ignore_result_name(monkeypatch):
    def disks():
        return [
            audit.CheckResult("disk /", "warn", "70%"),
            audit.CheckResult("disk /mnt/Backup", "fail", "98%"),
        ]
    monkeypatch.setattr(audit, "_all_check_callables", lambda: {"disks": disks})
    results = audit.run_audit(ignore=["disk /mnt/Backup"])
    names = [r.name for r in results]
    assert "disk /" in names
    assert "disk /mnt/Backup" not in names


def test_audit_ignore_via_config(monkeypatch):
    cfg = config.Config(ignored_checks={"swap"})
    config.set_config(cfg)
    monkeypatch.setattr(audit, "_all_check_callables", lambda: {
        "memory": lambda: audit.CheckResult("memory", "ok", ""),
        "swap": lambda: audit.CheckResult("swap", "fail", "boom"),
    })
    results = audit.run_audit()
    assert {r.name for r in results} == {"memory"}
    config.set_config(config.Config())


def test_cli_ignore_flag(monkeypatch):
    monkeypatch.setattr(audit, "run_audit",
                        lambda names=None, ignore=None:
                        [audit.CheckResult("memory", "ok", "x")] if "swap" in (ignore or [])
                        else [audit.CheckResult("memory", "ok", "x"), audit.CheckResult("swap", "fail", "y")])
    rc, out = _capture(["audit", "--ignore", "swap"])
    assert "swap" not in out


# ---- wtf config CLI ----

def test_cmd_config_text():
    rc, out = _capture(["config"])
    assert rc == 0
    assert "CONFIG" in out
    assert "disk_warn_pct" in out


def test_cmd_config_json():
    rc, out = _capture(["config", "--format", "json"])
    assert rc == 0
    data = json.loads(out)
    assert "effective" in data
    assert "search_paths" in data


def test_cmd_config_example():
    rc, out = _capture(["config", "--example"])
    assert rc == 0
    assert "[thresholds]" in out
    assert "[ignore]" in out


def test_global_config_flag(monkeypatch, tmp_path):
    f = tmp_path / "x.ini"
    f.write_text("[thresholds]\ndisk_warn = 1\ndisk_fail = 2\n")
    monkeypatch.setattr(audit, "run_audit", lambda **kw: [audit.CheckResult("x", "ok", "")])
    _capture(["--config", str(f), "audit", "--check", "uptime"])
    assert config.get_config().disk_warn_pct == 1
    config.set_config(config.Config())  # restore


# ---- thresholds actually applied ----

def test_config_thresholds_used_by_memory_check(monkeypatch):
    config.set_config(config.Config(mem_warn_pct=10, mem_fail_pct=20))
    monkeypatch.setattr(audit.sysinfo, "get_memory_summary",
                        lambda: {"used": 15, "total": 100, "percent": 15})
    r = audit._check_memory()
    assert r.status == "warn"
    config.set_config(config.Config())


def test_config_thresholds_used_by_disk_check(monkeypatch):
    config.set_config(config.Config(disk_warn_pct=30, disk_fail_pct=70))
    monkeypatch.setattr(audit.sysinfo, "get_disks",
                        lambda: [{"target": "/", "used": 50, "total": 100, "percent": 50}])
    results = audit._check_disks()
    assert results[0].status == "warn"
    config.set_config(config.Config())


def test_config_thresholds_used_by_pid_check(monkeypatch):
    config.set_config(config.Config(pid_warn_pct=10, pid_fail_pct=20))
    monkeypatch.setattr(audit.sysinfo, "get_pid_count", lambda: (25, 100))
    r = audit._check_pid_count()
    assert r.status == "fail"
    config.set_config(config.Config())
