#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""/proc-based collectors and checks: RAID (md), deleted-open files, stale libs."""

import types

from wtftools import audit, sysinfo

MDSTAT_CLEAN = """Personalities : [raid1]
md0 : active raid1 sdb1[1] sda1[0]
      976630464 blocks super 1.2 [2/2] [UU]

unused devices: <none>
"""

MDSTAT_DEGRADED = """Personalities : [raid1]
md0 : active raid1 sda1[0]
      976630464 blocks super 1.2 [2/1] [U_]

unused devices: <none>
"""

MDSTAT_RESYNC = """Personalities : [raid1]
md0 : active raid1 sdb1[1] sda1[0]
      976630464 blocks super 1.2 [2/2] [UU]
      [=====>...............]  resync = 27.3% (266/976) finish=50.0min

unused devices: <none>
"""


# ---- get_md_arrays ----


def test_get_md_arrays_none_without_mdstat(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda p: "")
    assert sysinfo.get_md_arrays() is None


def test_get_md_arrays_clean(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda p: MDSTAT_CLEAN)
    arrays = sysinfo.get_md_arrays()
    assert len(arrays) == 1
    assert arrays[0]["name"] == "md0"
    assert arrays[0]["status"] == "UU"
    assert arrays[0]["degraded"] is False
    assert arrays[0]["recovery"] == ""


def test_get_md_arrays_degraded(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda p: MDSTAT_DEGRADED)
    arrays = sysinfo.get_md_arrays()
    assert arrays[0]["degraded"] is True


def test_get_md_arrays_resync(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda p: MDSTAT_RESYNC)
    arrays = sysinfo.get_md_arrays()
    assert arrays[0]["degraded"] is False
    assert "resync" in arrays[0]["recovery"]


# ---- _check_raid ----


def test_check_raid_skip_no_md(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_md_arrays", lambda: None)
    assert audit._check_raid().status == "skip"


def test_check_raid_ok(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_md_arrays", lambda: [{"name": "md0", "level": "raid1", "status": "UU", "degraded": False, "recovery": ""}])
    assert audit._check_raid().status == "ok"


def test_check_raid_fail_degraded(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_md_arrays", lambda: [{"name": "md0", "level": "raid1", "status": "U_", "degraded": True, "recovery": ""}])
    assert audit._check_raid().status == "fail"


def test_check_raid_warn_rebuilding(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_md_arrays", lambda: [{"name": "md0", "level": "raid1", "status": "UU", "degraded": False, "recovery": "resync 27.3%"}])
    assert audit._check_raid().status == "warn"


# ---- get_deleted_open_files ----


def test_get_deleted_open_files(monkeypatch):
    monkeypatch.setattr(sysinfo.os.path, "isdir", lambda p: True)

    def fake_listdir(path):
        if path == "/proc":
            return ["123", "self", "cpuinfo"]
        if path == "/proc/123/fd":
            return ["3", "4", "5"]
        raise OSError

    def fake_readlink(path):
        return {
            "/proc/123/fd/3": "/var/log/app.log (deleted)",
            "/proc/123/fd/4": "/dev/null",
            "/proc/123/fd/5": "/tmp/small.tmp (deleted)",
        }[path]

    def fake_stat(path):
        return types.SimpleNamespace(st_size={"/proc/123/fd/3": 200 * 1024 * 1024, "/proc/123/fd/5": 10}[path])

    monkeypatch.setattr(sysinfo.os, "listdir", fake_listdir)
    monkeypatch.setattr(sysinfo.os, "readlink", fake_readlink)
    monkeypatch.setattr(sysinfo.os, "stat", fake_stat)
    monkeypatch.setattr(sysinfo, "read_file", lambda p: "app\n")

    files = sysinfo.get_deleted_open_files()
    # /dev/null skipped, small.tmp below the 1 MiB floor, only app.log remains
    assert len(files) == 1
    assert files[0]["path"] == "/var/log/app.log"
    assert files[0]["name"] == "app"
    assert files[0]["bytes"] == 200 * 1024 * 1024


def test_get_deleted_open_files_no_proc(monkeypatch):
    monkeypatch.setattr(sysinfo.os.path, "isdir", lambda p: False)
    assert sysinfo.get_deleted_open_files() is None


# ---- _check_deleted_files ----


def test_check_deleted_files_skip(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_deleted_open_files", lambda: None)
    assert audit._check_deleted_files().status == "skip"


def test_check_deleted_files_ok_when_small(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_deleted_open_files", lambda: [{"pid": 1, "name": "x", "path": "/tmp/a", "bytes": 5 * 1024 * 1024}])
    assert audit._check_deleted_files().status == "ok"


def test_check_deleted_files_warn_over_gib(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_deleted_open_files", lambda: [{"pid": 1, "name": "x", "path": "/var/log/big", "bytes": 2 * 1024**3}])
    r = audit._check_deleted_files()
    assert r.status == "warn"
    assert r.detail


# ---- get_stale_lib_processes ----

MAPS_STALE = """00400000-00452000 r-xp 00000000 08:01 100 /usr/sbin/nginx
7f0000000000-7f0000010000 r-xp 00000000 08:01 200 /usr/lib/x86_64-linux-gnu/libssl.so.3 (deleted)
7f0000020000-7f0000030000 r-xp 00000000 08:01 300 /usr/lib/x86_64-linux-gnu/libc.so.6
"""


def test_get_stale_lib_processes(monkeypatch):
    monkeypatch.setattr(sysinfo.os.path, "isdir", lambda p: True)
    monkeypatch.setattr(sysinfo.os, "listdir", lambda p: ["456", "999", "notapid"])

    def fake_read(path):
        if path == "/proc/456/maps":
            return MAPS_STALE
        if path == "/proc/999/maps":
            return "00400000-00452000 r-xp 0 08:01 1 /bin/bash\n"
        if path.endswith("/comm"):
            return "nginx\n"
        return ""

    monkeypatch.setattr(sysinfo, "read_file", fake_read)
    procs = sysinfo.get_stale_lib_processes()
    assert len(procs) == 1
    assert procs[0]["pid"] == 456
    assert procs[0]["libs"] == ["/usr/lib/x86_64-linux-gnu/libssl.so.3"]


def test_get_stale_lib_processes_no_proc(monkeypatch):
    monkeypatch.setattr(sysinfo.os.path, "isdir", lambda p: False)
    assert sysinfo.get_stale_lib_processes() is None


# ---- _check_stale_libs ----


def test_check_stale_libs_skip(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_stale_lib_processes", lambda: None)
    assert audit._check_stale_libs().status == "skip"


def test_check_stale_libs_ok(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_stale_lib_processes", lambda: [])
    assert audit._check_stale_libs().status == "ok"


def test_check_stale_libs_warn(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_stale_lib_processes", lambda: [{"pid": 456, "name": "nginx", "libs": ["/usr/lib/libssl.so.3"]}])
    r = audit._check_stale_libs()
    assert r.status == "warn"
    assert r.detail


# ---- registry wiring ----


def test_new_checks_registered():
    for key in ("raid", "deleted-files", "stale-libs"):
        assert key in audit.CHECK_REGISTRY
