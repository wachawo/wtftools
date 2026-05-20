#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for iteration 6: snapshot/diff/history, docker, NTP drift, prometheus, info --watch."""

import io
import json
import os
from contextlib import redirect_stdout
from unittest import mock

from wtftools import audit, main, snapshot
from wtftools.checks import sysinfo


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


# ---- snapshot module ----

def test_default_snapshot_dir_env_override(monkeypatch):
    monkeypatch.setenv("WTFTOOLS_SNAPSHOT_DIR", "/tmp/wtf-test-snapshots-xyz")
    assert snapshot.default_snapshot_dir() == "/tmp/wtf-test-snapshots-xyz"


def test_default_snapshot_dir_user(monkeypatch):
    monkeypatch.delenv("WTFTOOLS_SNAPSHOT_DIR", raising=False)
    monkeypatch.setattr(snapshot.os, "geteuid", lambda: 1000)
    monkeypatch.setenv("XDG_CACHE_HOME", "/tmp/cache-test")
    assert snapshot.default_snapshot_dir() == "/tmp/cache-test/wtftools/snapshots"


def test_default_snapshot_dir_root(monkeypatch):
    monkeypatch.delenv("WTFTOOLS_SNAPSHOT_DIR", raising=False)
    monkeypatch.setattr(snapshot.os, "geteuid", lambda: 0)
    assert snapshot.default_snapshot_dir() == "/var/lib/wtftools/snapshots"


def test_ensure_dir(tmp_path):
    target = tmp_path / "snapshots"
    assert snapshot.ensure_dir(str(target)) is True
    assert target.is_dir()
    # Calling again is idempotent
    assert snapshot.ensure_dir(str(target)) is True


def test_ensure_dir_failure(monkeypatch):
    monkeypatch.setattr(snapshot.os, "makedirs", mock.Mock(side_effect=OSError("nope")))
    assert snapshot.ensure_dir("/cannot/create") is False


def test_save_and_load_snapshot(tmp_path):
    results = [
        audit.CheckResult("a", "ok", "fine"),
        audit.CheckResult("b", "fail", "boom"),
    ]
    path = snapshot.save_snapshot(results, host="testhost", directory=str(tmp_path))
    assert path is not None
    assert os.path.exists(path)
    loaded = snapshot.load_snapshot(path)
    assert loaded is not None
    assert loaded["host"] == "testhost"
    assert len(loaded["results"]) == 2
    assert loaded["results"][1]["status"] == "fail"


def test_save_snapshot_dir_failure(monkeypatch):
    monkeypatch.setattr(snapshot, "ensure_dir", lambda _: False)
    assert snapshot.save_snapshot([], host="h") is None


def test_save_snapshot_write_failure(tmp_path, monkeypatch):
    """Write error should be swallowed and reported as None."""
    def boom(*a, **kw):
        raise OSError("disk full")
    monkeypatch.setattr("builtins.open", boom)
    result = snapshot.save_snapshot([audit.CheckResult("a", "ok", "x")],
                                    host="h", directory=str(tmp_path))
    assert result is None


def test_rotate_keeps_newest(tmp_path):
    # Create 5 files; rotate to keep 3.
    for ts in ("20260101T000000Z", "20260101T010000Z", "20260101T020000Z",
               "20260101T030000Z", "20260101T040000Z"):
        (tmp_path / f"{ts}.json").write_text("{}")
    snapshot._rotate(str(tmp_path), keep=3)
    remaining = sorted(os.listdir(str(tmp_path)))
    assert remaining == ["20260101T020000Z.json",
                         "20260101T030000Z.json",
                         "20260101T040000Z.json"]


def test_rotate_no_op_when_below_limit(tmp_path):
    (tmp_path / "20260101T000000Z.json").write_text("{}")
    snapshot._rotate(str(tmp_path), keep=10)
    assert os.listdir(str(tmp_path)) == ["20260101T000000Z.json"]


def test_list_snapshots(tmp_path):
    (tmp_path / "20260101T000000Z.json").write_text("{}")
    (tmp_path / "20260101T010000Z.json").write_text("{}")
    (tmp_path / "ignore.txt").write_text("not a snapshot")
    paths = snapshot.list_snapshots(str(tmp_path))
    assert len(paths) == 2
    assert all(p.endswith(".json") for p in paths)


def test_list_snapshots_no_dir(tmp_path):
    assert snapshot.list_snapshots(str(tmp_path / "nonexistent")) == []


def test_load_snapshot_corrupt(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json")
    assert snapshot.load_snapshot(str(bad)) is None


def test_latest_snapshot(tmp_path):
    a = tmp_path / "20260101T000000Z.json"
    b = tmp_path / "20260101T010000Z.json"
    a.write_text(json.dumps({"timestamp": "a"}))
    b.write_text(json.dumps({"timestamp": "b"}))
    latest = snapshot.latest_snapshot(str(tmp_path))
    assert latest is not None
    assert latest["timestamp"] == "b"


def test_latest_snapshot_empty(tmp_path):
    assert snapshot.latest_snapshot(str(tmp_path)) is None


def test_diff_snapshots_regression():
    old = {"results": [{"name": "swap", "status": "ok", "message": "10%"}]}
    new = [audit.CheckResult("swap", "fail", "99%")]
    events = snapshot.diff_snapshots(old, new)
    assert len(events) == 1
    assert events[0]["kind"] == "regression"
    assert events[0]["old_status"] == "ok"
    assert events[0]["new_status"] == "fail"


def test_diff_snapshots_worsened():
    old = {"results": [{"name": "disk /", "status": "warn", "message": "85%"}]}
    new = [audit.CheckResult("disk /", "fail", "95%")]
    events = snapshot.diff_snapshots(old, new)
    assert events[0]["kind"] == "worsened"


def test_diff_snapshots_recovery():
    old = {"results": [{"name": "swap", "status": "fail", "message": "99%"}]}
    new = [audit.CheckResult("swap", "ok", "10%")]
    events = snapshot.diff_snapshots(old, new)
    assert events[0]["kind"] == "recovery"


def test_diff_snapshots_improved():
    old = {"results": [{"name": "swap", "status": "fail", "message": "99%"}]}
    new = [audit.CheckResult("swap", "warn", "80%")]
    events = snapshot.diff_snapshots(old, new)
    assert events[0]["kind"] == "improved"


def test_diff_snapshots_new_and_removed():
    old = {"results": [{"name": "removed", "status": "ok", "message": "x"}]}
    new = [audit.CheckResult("appeared", "ok", "y")]
    events = snapshot.diff_snapshots(old, new)
    kinds = sorted(e["kind"] for e in events)
    assert kinds == ["new", "removed"]


def test_diff_snapshots_unchanged_skipped():
    old = {"results": [{"name": "x", "status": "ok", "message": "old"}]}
    new = [audit.CheckResult("x", "ok", "new")]
    events = snapshot.diff_snapshots(old, new)
    assert events == []


# ---- docker ----

def test_get_docker_no_docker(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: None)
    assert sysinfo.get_docker_problem_containers() is None


def test_get_docker_daemon_unreachable(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (1, "", "cannot connect"))
    assert sysinfo.get_docker_problem_containers() is None


def test_get_docker_all_healthy(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/docker")
    out = "web\tUp 3 hours (healthy)\trunning\ndb\tUp 1 day\trunning\n"
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, out, ""))
    assert sysinfo.get_docker_problem_containers() == []


def test_get_docker_unhealthy(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/docker")
    out = ("api\tUp 3 hours (unhealthy)\trunning\n"
           "loop\tRestarting (1) 5 seconds ago\trestarting\n"
           "ok\tUp 1 day (healthy)\trunning\n")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, out, ""))
    bad = sysinfo.get_docker_problem_containers()
    assert len(bad) == 2
    problems = sorted(c["problem"] for c in bad)
    assert problems == ["restarting", "unhealthy"]


def test_check_docker_skip(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_docker_problem_containers", lambda: None)
    assert audit._check_docker().status == "skip"


def test_check_docker_ok(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_docker_problem_containers", lambda: [])
    assert audit._check_docker().status == "ok"


def test_check_docker_warn(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_docker_problem_containers",
                        lambda: [{"name": "loop", "problem": "restarting",
                                  "status": "Restarting", "state": "restarting"}])
    r = audit._check_docker()
    assert r.status == "warn"


def test_check_docker_fail(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_docker_problem_containers",
                        lambda: [{"name": "api", "problem": "unhealthy",
                                  "status": "Up (unhealthy)", "state": "running"}])
    r = audit._check_docker()
    assert r.status == "fail"


# ---- NTP drift via chrony ----

def test_chrony_offset_no_chrony(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: None)
    assert sysinfo.get_chrony_offset() is None


def test_chrony_offset_parses(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/chronyc")
    out = ("Reference ID    : 192.168.1.1 (timeserver)\n"
           "System time     : 0.000123456 seconds slow of NTP time\n"
           "Last offset     : +0.000123 seconds\n")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, out, ""))
    offset = sysinfo.get_chrony_offset()
    assert offset is not None
    assert abs(offset - 0.000123456) < 1e-9


def test_chrony_offset_negative(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/chronyc")
    out = "System time     : -0.5 seconds fast of NTP time\n"
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, out, ""))
    assert sysinfo.get_chrony_offset() == 0.5


def test_chrony_offset_no_match(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/chronyc")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, "no system time line", ""))
    assert sysinfo.get_chrony_offset() is None


def test_chrony_offset_failure(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/chronyc")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (1, "", ""))
    assert sysinfo.get_chrony_offset() is None


def test_check_time_sync_drift_warn(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_time_sync_status",
                        lambda: {"synchronized": True, "ntp_active": True, "source": ""})
    monkeypatch.setattr(audit.sysinfo, "get_chrony_offset", lambda: 0.150)  # 150ms
    r = audit._check_time_sync()
    assert r.status == "warn"
    assert "drift" in r.message.lower()


def test_check_time_sync_drift_fail(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_time_sync_status",
                        lambda: {"synchronized": True, "ntp_active": True, "source": ""})
    monkeypatch.setattr(audit.sysinfo, "get_chrony_offset", lambda: 2.5)  # 2.5s
    r = audit._check_time_sync()
    assert r.status == "fail"


def test_check_time_sync_drift_ok(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_time_sync_status",
                        lambda: {"synchronized": True, "ntp_active": True, "source": ""})
    monkeypatch.setattr(audit.sysinfo, "get_chrony_offset", lambda: 0.001)
    r = audit._check_time_sync()
    assert r.status == "ok"
    assert "offset" in r.message


# ---- prometheus output ----

def test_render_prometheus_format():
    results = [
        audit.CheckResult("uptime", "ok", "3d"),
        audit.CheckResult("swap", "fail", "99%"),
        audit.CheckResult("docker", "skip", "n/a"),
    ]
    out = audit.render_prometheus(results)
    assert "# TYPE wtf_check_status gauge" in out
    assert 'wtf_check_status{name="uptime"} 0' in out
    assert 'wtf_check_status{name="swap"} 2' in out
    assert 'wtf_check_status{name="docker"} 3' in out
    assert 'wtf_summary_total{status="ok"} 1' in out
    assert 'wtf_summary_total{status="fail"} 1' in out


def test_render_prometheus_escapes_quotes():
    results = [audit.CheckResult('disk "weird"', "ok", "x")]
    out = audit.render_prometheus(results)
    assert 'name="disk \\"weird\\""' in out


def test_cli_prometheus_format(monkeypatch):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [
        audit.CheckResult("x", "ok", ""),
    ])
    rc, out = _capture(["audit", "--format", "prometheus"])
    assert "wtf_check_status" in out
    assert rc == 0


# ---- info --watch ----

def test_cmd_info_watch(monkeypatch):
    # Avoid invoking real sysinfo (psutil warmup uses time.sleep which we mock).
    monkeypatch.setattr(main.info_mod, "render_info", lambda: "==SYSTEM==\n")

    def boom(_):
        raise KeyboardInterrupt
    monkeypatch.setattr(main.time, "sleep", boom)
    rc, out = _capture(["info", "--watch", "1"])
    assert rc == 0
    assert "SYSTEM" in out
    assert "watch stopped" in out


# ---- snapshot CLI integration ----

def test_audit_save_writes_file(monkeypatch, tmp_path):
    monkeypatch.setenv("WTFTOOLS_SNAPSHOT_DIR", str(tmp_path))
    monkeypatch.setattr(audit, "run_audit",
                        lambda names=None, ignore=None: [audit.CheckResult("x", "ok", "y")])
    rc, out = _capture(["audit", "--save", "--check", "uptime"])
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".json"
    assert "snapshot saved" in out


def test_audit_diff_no_previous(monkeypatch, tmp_path):
    monkeypatch.setenv("WTFTOOLS_SNAPSHOT_DIR", str(tmp_path))
    monkeypatch.setattr(audit, "run_audit",
                        lambda names=None, ignore=None: [audit.CheckResult("x", "ok", "y")])
    rc, out = _capture(["audit", "--diff", "--check", "uptime"])
    assert rc == 0
    assert "no previous snapshot" in out


def test_audit_diff_with_previous(monkeypatch, tmp_path):
    monkeypatch.setenv("WTFTOOLS_SNAPSHOT_DIR", str(tmp_path))
    # Plant a previous snapshot showing swap=ok
    snapshot.save_snapshot(
        [audit.CheckResult("swap", "ok", "10%")],
        host="testhost", directory=str(tmp_path),
    )
    # Current run says swap=fail → regression
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [
        audit.CheckResult("swap", "fail", "99%"),
    ])
    rc, out = _capture(["audit", "--diff", "--check", "swap"])
    assert "regression" in out.lower() or "REG" in out


def test_audit_diff_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("WTFTOOLS_SNAPSHOT_DIR", str(tmp_path))
    snapshot.save_snapshot([audit.CheckResult("x", "ok", "")],
                           host="h", directory=str(tmp_path))
    monkeypatch.setattr(audit, "run_audit",
                        lambda names=None, ignore=None: [audit.CheckResult("x", "ok", "")])
    rc, out = _capture(["audit", "--diff"])
    assert "nothing changed" in out


def test_audit_diff_json(monkeypatch, tmp_path):
    monkeypatch.setenv("WTFTOOLS_SNAPSHOT_DIR", str(tmp_path))
    snapshot.save_snapshot([audit.CheckResult("swap", "ok", "")],
                           host="h", directory=str(tmp_path))
    monkeypatch.setattr(audit, "run_audit",
                        lambda names=None, ignore=None: [audit.CheckResult("swap", "fail", "")])
    rc, out = _capture(["audit", "--diff", "--format", "json"])
    data = json.loads(out)
    assert "changes" in data
    assert any(e["kind"] == "regression" for e in data["changes"])


def test_cmd_history_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("WTFTOOLS_SNAPSHOT_DIR", str(tmp_path))
    rc, out = _capture(["history"])
    assert rc == 0
    assert "no snapshots" in out


def test_cmd_history_lists(monkeypatch, tmp_path):
    monkeypatch.setenv("WTFTOOLS_SNAPSHOT_DIR", str(tmp_path))
    snapshot.save_snapshot([audit.CheckResult("x", "ok", "")],
                           host="h", directory=str(tmp_path))
    rc, out = _capture(["history"])
    assert "HISTORY" in out
    assert "1 snapshot" in out


def test_cmd_history_json(monkeypatch, tmp_path):
    monkeypatch.setenv("WTFTOOLS_SNAPSHOT_DIR", str(tmp_path))
    snapshot.save_snapshot([audit.CheckResult("x", "fail", "")],
                           host="h", directory=str(tmp_path))
    rc, out = _capture(["history", "--format", "json"])
    data = json.loads(out)
    assert len(data) == 1
    assert data[0]["totals"]["fail"] == 1


def test_cmd_history_corrupt_snapshot(monkeypatch, tmp_path):
    monkeypatch.setenv("WTFTOOLS_SNAPSHOT_DIR", str(tmp_path))
    (tmp_path / "20260101T000000Z.json").write_text("not json")
    rc, out = _capture(["history"])
    assert rc == 0
    assert "corrupt" in out.lower()


# ---- new registry entries ----

def test_docker_in_registry():
    assert "docker" in audit.list_check_names()
