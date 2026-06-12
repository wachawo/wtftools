#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `--format plain`, the global -f flag and `wtf daily`."""

import io
import json
from contextlib import redirect_stdout

from wtftools import info, main, sections, sysinfo


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


def _patch_sysinfo_basics(monkeypatch):
    monkeypatch.setattr(sysinfo, "get_hostname", lambda: "host1")
    monkeypatch.setattr(sysinfo, "get_os_release", lambda: {"PRETTY_NAME": "Test OS"})
    monkeypatch.setattr(sysinfo, "get_kernel", lambda: "5.0.0-test")
    monkeypatch.setattr(sysinfo, "get_uptime_seconds", lambda: 3600.0)
    monkeypatch.setattr(sysinfo, "get_cpu_model", lambda: "Test CPU")
    monkeypatch.setattr(sysinfo, "get_cpu_count", lambda: 4)
    monkeypatch.setattr(sysinfo, "get_loadavg", lambda: (0.1, 0.2, 0.3))
    monkeypatch.setattr(
        sysinfo,
        "get_memory_summary",
        lambda: {"used": 100, "total": 1000, "percent": 10, "swap_used": 5, "swap_total": 50, "swap_percent": 10},
    )
    monkeypatch.setattr(sysinfo, "get_disks", lambda: [{"target": "/", "used": 50, "total": 100, "percent": 50, "fstype": "ext4"}])
    monkeypatch.setattr(
        sysinfo,
        "get_top_processes",
        lambda by, limit: [{"pid": 1, "name": "proc1", "user": "u", "cpu_percent": 9.0, "rss": 2048}],
    )
    monkeypatch.setattr(sysinfo, "get_network_interfaces", lambda: [{"name": "eth0", "ipv4": ["10.0.0.1"], "ipv6": [], "up": True}])
    monkeypatch.setattr(sysinfo, "get_listening_ports", lambda: [{"addr": "0.0.0.0", "port": 80, "pid": 1}])


def test_info_plain(monkeypatch):
    _patch_sysinfo_basics(monkeypatch)
    rc, out = _capture(["info", "--format", "plain"])
    assert rc == 0
    lines = out.strip().splitlines()
    assert "host\thost1" in lines
    assert "mount\t/\t50\t100\t50\text4" in lines
    assert "listen\t80" in lines


def test_info_json_schema_version(monkeypatch):
    _patch_sysinfo_basics(monkeypatch)
    rc, out = _capture(["info", "--format", "json"])
    assert rc == 0
    payload = json.loads(out)
    assert payload["schema_version"] == 1


def test_global_format_flag_before_subcommand(monkeypatch):
    _patch_sysinfo_basics(monkeypatch)
    rc, out = _capture(["-f", "plain", "info"])
    assert rc == 0
    assert "host\thost1" in out


def test_subcommand_format_overrides_global(monkeypatch):
    _patch_sysinfo_basics(monkeypatch)
    rc, out = _capture(["-f", "plain", "info", "--format", "json"])
    assert rc == 0
    assert json.loads(out)["hostname"] == "host1"


def test_top_plain(monkeypatch):
    _patch_sysinfo_basics(monkeypatch)
    rc, out = _capture(["top", "--limit", "1", "--format", "plain"])
    assert rc == 0
    assert out.strip() == "1\tu\t9.0\t2048\tproc1"


def test_events_plain(monkeypatch):
    from wtftools import events as events_mod

    class FakeEvent:
        timestamp = 0.0
        kind = "reboot"
        message = "system boot"
        detail = []

        def iso(self):
            return "2026-01-01T00:00:00"

    monkeypatch.setattr(events_mod, "collect_events", lambda hours, kinds=None: [FakeEvent()])
    rc, out = _capture(["events", "--format", "plain"])
    assert rc == 0
    assert out.strip() == "2026-01-01T00:00:00\treboot\tsystem boot"


def test_render_info_plain_direct(monkeypatch):
    _patch_sysinfo_basics(monkeypatch)
    out = info.render_info_plain()
    assert "kernel\t5.0.0-test" in out
    assert "top_cpu\t1\tu\t9.0\tproc1" in out
    assert "iface\teth0\tup\t10.0.0.1" in out


def test_sections_render_plain_shapes(monkeypatch):
    _patch_sysinfo_basics(monkeypatch)
    monkeypatch.setattr(sysinfo, "get_readonly_mounts", lambda: [])
    monkeypatch.setattr(sections, "get_inode_percent", lambda target: 3)
    disk_plain = sections.render_disk_plain(sections.collect_disk())
    assert disk_plain == "mount\t/\t50\t100\t50\text4\trw\t3"

    monkeypatch.setattr(sysinfo, "get_pressure", lambda resource: {"some": {"avg10": 1.5}})
    monkeypatch.setattr(sysinfo, "get_iowait_percent", lambda: 0.5)
    cpu_plain = sections.render_cpu_plain(sections.collect_cpu())
    assert "load\t0.1\t0.2\t0.3" in cpu_plain
    assert "psi_cpu\t1.5" in cpu_plain


def test_daily_text_first_run(monkeypatch, tmp_path):
    from wtftools import snapshot as snapshot_mod
    from wtftools.audit import CheckResult

    monkeypatch.setattr(main, "_run_audit_once", lambda args: ([CheckResult("memory", "ok", "fine")], 0))
    monkeypatch.setattr(snapshot_mod, "list_snapshots", lambda directory=None: [])
    monkeypatch.setattr(snapshot_mod, "save_snapshot", lambda results, host, directory=None: str(tmp_path / "snap.json"))
    monkeypatch.setattr(main.events_mod, "collect_events", lambda hours, kinds=None: [])
    rc, out = _capture(["daily"])
    assert rc == 0
    assert "first run" in out
    assert "EVENTS" in out
    assert "AUDIT" in out
    assert "snapshot saved" in out


def test_daily_json(monkeypatch, tmp_path):
    from wtftools import snapshot as snapshot_mod
    from wtftools.audit import CheckResult

    results = [CheckResult("memory", "ok", "fine")]
    old = {"timestamp": "2026-01-01", "results": [{"name": "memory", "status": "warn", "message": "high"}]}
    snap = tmp_path / "old.json"
    snap.write_text("{}")
    monkeypatch.setattr(main, "_run_audit_once", lambda args: (results, 0))
    monkeypatch.setattr(snapshot_mod, "list_snapshots", lambda directory=None: [str(snap)])
    monkeypatch.setattr(snapshot_mod, "load_snapshot", lambda path: old)
    monkeypatch.setattr(snapshot_mod, "save_snapshot", lambda results, host, directory=None: str(tmp_path / "new.json"))
    monkeypatch.setattr(main.events_mod, "collect_events", lambda hours, kinds=None: [])
    rc, out = _capture(["daily", "--format", "json"])
    assert rc == 0
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    assert payload["summary"]["ok"] == 1
    assert any(c["kind"] == "improved" for c in payload["changes"])


def test_ports_plain_fallback(monkeypatch):
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, *args, **kwargs):
        if name == "psutil":
            raise ImportError("no module")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    monkeypatch.setattr(main.sysinfo, "get_listening_ports", lambda: [{"addr": "0.0.0.0", "port": 80, "pid": None}])
    rc, out = _capture(["ports", "--format", "plain"])
    assert rc == 0
    assert out.strip() == "80\ttcp\t0.0.0.0\t-\t-\t-"


def test_logs_plain(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda name: "/usr/bin/journalctl")
    entry = json.dumps({"_SYSTEMD_UNIT": "app.service", "MESSAGE": "boom"})
    monkeypatch.setattr(main.sysinfo, "run", lambda cmd, timeout=5: (0, entry, ""))
    rc, out = _capture(["logs", "--format", "plain"])
    assert rc == 0
    assert out.strip() == "app\tboom"


def test_services_plain(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda name: "/usr/bin/systemctl")
    details = {
        "Id": "app.service",
        "ActiveState": "active",
        "SubState": "running",
        "Result": "success",
        "UnitFileState": "enabled",
        "MainPID": "42",
        "NRestarts": "1",
        "MemoryCurrent": "1024",
    }
    monkeypatch.setattr(main.sysinfo, "get_service_details", lambda unit: details)
    monkeypatch.setattr(main.sysinfo, "get_service_journal", lambda unit, lines=20: ["line one"])
    monkeypatch.setattr(main, "_ports_for_pid", lambda pid: [{"port": 8080, "addr": "0.0.0.0"}])
    rc, out = _capture(["service", "app", "--format", "plain"])
    assert rc == 0
    lines = out.strip().splitlines()
    assert "id\tapp.service" in lines
    assert "state\tactive\trunning\tsuccess" in lines
    assert "port\t8080\t0.0.0.0" in lines
    assert "journal\tline one" in lines
