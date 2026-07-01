#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for wtftools.audit — individual checks and aggregation."""

import logging
import types
from unittest import mock

from wtftools import audit


def test_summarize_counts():
    results = [
        audit.CheckResult("a", "ok", "x"),
        audit.CheckResult("b", "warn", "y"),
        audit.CheckResult("c", "fail", "z"),
        audit.CheckResult("d", "ok", "q"),
        audit.CheckResult("e", "skip", "s"),
    ]
    totals = audit.summarize(results)
    assert totals == {"ok": 2, "warn": 1, "fail": 1, "skip": 1}


def test_check_cron_daemon_ok(monkeypatch):
    monkeypatch.setattr(audit.cron, "check_daemon", lambda: [])
    r = audit._check_cron_daemon()
    assert r.status == "ok"


def test_check_cron_daemon_warn(monkeypatch):
    monkeypatch.setattr(audit.cron, "check_daemon", lambda: ["daemon down"])
    r = audit._check_cron_daemon()
    assert r.status == "warn"
    assert "daemon down" in r.message


def test_check_load_levels(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_cpu_count", lambda: 4)
    monkeypatch.setattr(audit.sysinfo, "get_loadavg", lambda: (1.0, 1.0, 1.0))
    assert audit._check_load().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_loadavg", lambda: (5.0, 5.0, 5.0))
    assert audit._check_load().status == "warn"  # 5.0 / 4 CPUs = 1.25x → warn band
    monkeypatch.setattr(audit.sysinfo, "get_loadavg", lambda: (10.0, 10.0, 10.0))
    assert audit._check_load().status == "fail"


def test_check_memory(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_memory_summary", lambda: {"used": 100, "total": 1000, "percent": 10})
    assert audit._check_memory().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_memory_summary", lambda: {"used": 900, "total": 1000, "percent": 90})
    assert audit._check_memory().status == "warn"
    monkeypatch.setattr(audit.sysinfo, "get_memory_summary", lambda: {"used": 990, "total": 1000, "percent": 96})
    assert audit._check_memory().status == "fail"


def test_check_swap_no_swap(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_memory_summary", lambda: {"swap_total": 0, "swap_used": 0, "swap_percent": 0})
    assert audit._check_swap().status == "skip"


def test_check_swap_states(monkeypatch):
    def with_pct(p):
        return {"swap_total": 100, "swap_used": p, "swap_percent": p}

    monkeypatch.setattr(audit.sysinfo, "get_memory_summary", lambda: with_pct(10))
    assert audit._check_swap().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_memory_summary", lambda: with_pct(40))
    assert audit._check_swap().status == "warn"
    monkeypatch.setattr(audit.sysinfo, "get_memory_summary", lambda: with_pct(80))
    assert audit._check_swap().status == "fail"


def test_check_disks(monkeypatch):
    disks = [
        {"target": "/", "used": 50, "total": 100, "percent": 50},
        {"target": "/var", "used": 90, "total": 100, "percent": 90},
        {"target": "/data", "used": 99, "total": 100, "percent": 99},
    ]
    monkeypatch.setattr(audit.sysinfo, "get_disks", lambda: disks)
    results = audit._check_disks()
    statuses = {r.name: r.status for r in results}
    assert statuses["disk /"] == "ok"
    assert statuses["disk /var"] == "warn"
    assert statuses["disk /data"] == "fail"


def test_check_inodes_only_problems(monkeypatch):
    monkeypatch.setattr(
        audit.sysinfo,
        "get_disks",
        lambda: [
            {"target": "/", "used": 0, "total": 1, "percent": 0},
            {"target": "/var", "used": 0, "total": 1, "percent": 0},
        ],
    )

    def fake_statvfs(path):
        if path == "/":
            return types.SimpleNamespace(f_files=100, f_ffree=99)  # 1% used
        return types.SimpleNamespace(f_files=100, f_ffree=2)  # 98% used → fail

    monkeypatch.setattr(audit.os, "statvfs", fake_statvfs)
    results = audit._check_inodes()
    statuses = {r.name: r.status for r in results}
    assert "inodes /" not in statuses
    assert statuses["inodes /var"] == "fail"


def test_check_inodes_oserror(monkeypatch):
    monkeypatch.setattr(
        audit.sysinfo,
        "get_disks",
        lambda: [
            {"target": "/x", "used": 0, "total": 1, "percent": 0},
        ],
    )
    monkeypatch.setattr(audit.os, "statvfs", mock.Mock(side_effect=OSError))
    assert audit._check_inodes() == []


def test_check_failed_units_none(monkeypatch):
    monkeypatch.setattr(audit.shutil, "which", lambda _: "/bin/systemctl")
    monkeypatch.setattr(audit.sysinfo, "get_failed_units", lambda: [])
    assert audit._check_failed_units().status == "ok"


def test_check_failed_units_present(monkeypatch):
    monkeypatch.setattr(audit.shutil, "which", lambda _: "/bin/systemctl")
    monkeypatch.setattr(audit.sysinfo, "get_failed_units", lambda: ["x.service"])
    r = audit._check_failed_units()
    assert r.status == "fail"
    assert "x.service" in r.detail


def test_check_failed_units_no_systemctl(monkeypatch):
    monkeypatch.setattr(audit.shutil, "which", lambda _: None)
    assert audit._check_failed_units().status == "skip"


def test_check_zombies(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "count_zombie_processes", lambda: 0)
    assert audit._check_zombies().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "count_zombie_processes", lambda: 2)
    assert audit._check_zombies().status == "warn"
    monkeypatch.setattr(audit.sysinfo, "count_zombie_processes", lambda: 10)
    assert audit._check_zombies().status == "fail"


def test_check_oom_kills(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_oom_events", lambda hours: [])
    assert audit._check_oom_kills().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_oom_events", lambda hours: ["killed process"])
    assert audit._check_oom_kills().status == "fail"


def test_check_kernel_errors(monkeypatch):
    monkeypatch.setattr(audit.shutil, "which", lambda _: None)
    assert audit._check_kernel_errors().status == "skip"
    monkeypatch.setattr(audit.shutil, "which", lambda _: "/bin/journalctl")
    monkeypatch.setattr(audit.sysinfo, "get_recent_kernel_errors", lambda hours, limit: [])
    assert audit._check_kernel_errors().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_recent_kernel_errors", lambda hours, limit: ["e1"])
    assert audit._check_kernel_errors().status == "warn"


def test_check_pending_updates(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_pending_updates", lambda: -1)
    assert audit._check_pending_updates().status == "skip"
    monkeypatch.setattr(audit.sysinfo, "get_pending_updates", lambda: 0)
    assert audit._check_pending_updates().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_pending_updates", lambda: 10)
    assert audit._check_pending_updates().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_pending_updates", lambda: 100)
    assert audit._check_pending_updates().status == "warn"


def test_check_fds(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_open_fds", lambda: None)
    assert audit._check_fds().status == "skip"
    monkeypatch.setattr(audit.sysinfo, "get_open_fds", lambda: (10, 1000))
    assert audit._check_fds().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_open_fds", lambda: (700, 1000))
    assert audit._check_fds().status == "warn"
    monkeypatch.setattr(audit.sysinfo, "get_open_fds", lambda: (900, 1000))
    assert audit._check_fds().status == "fail"


def test_check_failed_auth(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_failed_auth_count", lambda hours: 0)
    assert audit._check_failed_auth().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_failed_auth_count", lambda hours: 10)
    assert audit._check_failed_auth().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_failed_auth_count", lambda hours: 100)
    assert audit._check_failed_auth().status == "warn"


def test_check_user_crontabs_no_targets(monkeypatch):
    monkeypatch.setattr(audit.cron, "discover_default_targets", lambda: [])
    assert audit._check_user_crontabs().status == "skip"


def test_check_user_crontabs_ok(monkeypatch):
    monkeypatch.setattr(audit.cron, "discover_default_targets", lambda: [("p", True)])
    monkeypatch.setattr(audit.cron, "check_file", lambda p, is_system_crontab: (3, [], []))
    assert audit._check_user_crontabs().status == "ok"


def test_check_user_crontabs_fail(monkeypatch):
    monkeypatch.setattr(audit.cron, "discover_default_targets", lambda: [("p", True)])
    monkeypatch.setattr(audit.cron, "check_file", lambda p, is_system_crontab: (3, ["e1"], []))
    r = audit._check_user_crontabs()
    assert r.status == "fail"


def test_check_uptime(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_uptime_seconds", lambda: 60.0)
    assert audit._check_uptime().status == "warn"
    monkeypatch.setattr(audit.sysinfo, "get_uptime_seconds", lambda: 100000.0)
    assert audit._check_uptime().status == "ok"


def test_check_system_running(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_system_running_state", lambda: None)
    assert audit._check_system_running().status == "skip"
    monkeypatch.setattr(audit.sysinfo, "get_system_running_state", lambda: "running")
    assert audit._check_system_running().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_system_running_state", lambda: "degraded")
    assert audit._check_system_running().status == "fail"
    monkeypatch.setattr(audit.sysinfo, "get_system_running_state", lambda: "starting")
    assert audit._check_system_running().status == "warn"
    monkeypatch.setattr(audit.sysinfo, "get_system_running_state", lambda: "maintenance")
    assert audit._check_system_running().status == "fail"
    monkeypatch.setattr(audit.sysinfo, "get_system_running_state", lambda: "weird")
    assert audit._check_system_running().status == "warn"


def test_check_enabled_inactive(monkeypatch):
    monkeypatch.setattr(audit.shutil, "which", lambda _: None)
    assert audit._check_enabled_inactive().status == "skip"
    monkeypatch.setattr(audit.shutil, "which", lambda _: "/bin/systemctl")
    monkeypatch.setattr(audit.sysinfo, "get_enabled_inactive_units", lambda: [])
    assert audit._check_enabled_inactive().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_enabled_inactive_units", lambda: [{"name": "x.service", "state": "failed", "sub": "failed", "result": "exit-code"}])
    r = audit._check_enabled_inactive()
    assert r.status == "fail"
    monkeypatch.setattr(audit.sysinfo, "get_enabled_inactive_units", lambda: [{"name": "x.service", "state": "inactive", "sub": "dead", "result": "success"}])
    r = audit._check_enabled_inactive()
    assert r.status == "warn"


def test_check_reboot_required(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_reboot_required", lambda: None)
    assert audit._check_reboot_required().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_reboot_required", lambda: "reboot required")
    assert audit._check_reboot_required().status == "warn"


def test_check_time_sync(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_time_sync_status", lambda: {"synchronized": None, "ntp_active": None, "source": "missing"})
    assert audit._check_time_sync().status == "skip"
    monkeypatch.setattr(audit.sysinfo, "get_time_sync_status", lambda: {"synchronized": True, "ntp_active": True, "source": ""})
    assert audit._check_time_sync().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_time_sync_status", lambda: {"synchronized": False, "ntp_active": True, "source": ""})
    assert audit._check_time_sync().status == "warn"
    monkeypatch.setattr(audit.sysinfo, "get_time_sync_status", lambda: {"synchronized": False, "ntp_active": False, "source": ""})
    assert audit._check_time_sync().status == "fail"


def test_check_readonly_mounts(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_readonly_mounts", lambda: [])
    assert audit._check_readonly_mounts().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_readonly_mounts", lambda: ["/data (ext4)"])
    assert audit._check_readonly_mounts().status == "fail"


def test_check_stuck_processes(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_stuck_processes", lambda: [])
    assert audit._check_stuck_processes().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_stuck_processes", lambda: [{"pid": 1, "name": "a"}])
    assert audit._check_stuck_processes().status == "warn"
    monkeypatch.setattr(audit.sysinfo, "get_stuck_processes", lambda: [{"pid": i, "name": "a"} for i in range(6)])
    assert audit._check_stuck_processes().status == "fail"


def test_check_iowait(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_iowait_percent", lambda: None)
    assert audit._check_iowait().status == "skip"
    monkeypatch.setattr(audit.sysinfo, "get_iowait_percent", lambda: 1.0)
    assert audit._check_iowait().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_iowait_percent", lambda: 15.0)
    assert audit._check_iowait().status == "warn"
    monkeypatch.setattr(audit.sysinfo, "get_iowait_percent", lambda: 50.0)
    assert audit._check_iowait().status == "fail"


def test_check_pid_count(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_pid_count", lambda: (10, 0))
    assert audit._check_pid_count().status == "skip"
    monkeypatch.setattr(audit.sysinfo, "get_pid_count", lambda: (10, 100))
    assert audit._check_pid_count().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_pid_count", lambda: (60, 100))
    assert audit._check_pid_count().status == "warn"
    monkeypatch.setattr(audit.sysinfo, "get_pid_count", lambda: (85, 100))
    assert audit._check_pid_count().status == "fail"


def test_run_audit_handles_exception(monkeypatch, caplog):
    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(audit, "CHECK_REGISTRY", {"only": boom})
    with caplog.at_level(logging.WARNING):
        results = audit.run_audit()
    assert len(results) == 1
    assert results[0].status == "skip"


def test_run_audit_list_outcome(monkeypatch):
    def multi():
        return [audit.CheckResult("x", "ok", "1"), audit.CheckResult("y", "warn", "2")]

    monkeypatch.setattr(audit, "CHECK_REGISTRY", {"only": multi})
    results = audit.run_audit()
    assert len(results) == 2


def test_run_audit_full_runs():
    # Smoke: real run_audit must not crash on the host running tests
    results = audit.run_audit()
    assert len(results) > 0
    assert all(r.status in ("ok", "warn", "fail", "skip") for r in results)
