#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `wtf explain --deep` dynamic investigation."""

import io
import json
from contextlib import redirect_stdout

from wtftools import audit, explain, main, sysinfo


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


# ---------- sysinfo helpers ----------


def test_get_top_paths_in_no_du(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: None)
    assert sysinfo.get_top_paths_in("/var") == []


def test_get_top_paths_in_no_dir(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/du")
    monkeypatch.setattr(sysinfo.os.path, "isdir", lambda _: False)
    assert sysinfo.get_top_paths_in("/nonexistent") == []


def test_get_top_paths_in_parses(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/du")
    monkeypatch.setattr(sysinfo.os.path, "isdir", lambda _: True)
    du_out = (
        "100\t/var/log/journal\n"
        "5000\t/var/log\n"
        "200\t/var/cache\n"
        "5500\t/var\n"  # the directory itself — must be filtered
    )
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, du_out, ""))
    result = sysinfo.get_top_paths_in("/var", limit=5)
    # /var itself is skipped; remaining 3 sorted desc by size
    assert len(result) == 3
    assert result[0]["path"] == "/var/log"
    assert result[0]["bytes"] == 5000
    assert result[1]["path"] == "/var/cache"
    assert result[2]["path"] == "/var/log/journal"


def test_get_top_paths_in_run_failure(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/du")
    monkeypatch.setattr(sysinfo.os.path, "isdir", lambda _: True)
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (1, "", "err"))
    assert sysinfo.get_top_paths_in("/var") == []


def test_get_largest_files_parses(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/find")
    monkeypatch.setattr(sysinfo.os.path, "isdir", lambda _: True)
    find_out = "104857600\t/var/log/journal/big.journal\n" "209715200\t/var/log/auth.log\n" "300000000\t/var/log/syslog\n"
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, find_out, ""))
    result = sysinfo.get_largest_files("/var", limit=2, min_size_mb=100)
    assert len(result) == 2
    assert result[0]["path"] == "/var/log/syslog"
    assert result[0]["bytes"] == 300000000
    assert result[1]["path"] == "/var/log/auth.log"


def test_get_largest_files_no_find(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: None)
    assert sysinfo.get_largest_files("/var") == []


def test_get_docker_disk_usage_no_docker(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: None)
    assert sysinfo.get_docker_disk_usage() is None


def test_get_docker_disk_usage_parses(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/docker")
    out = "Images\t10\t5GB\t2GB (40%)\n" "Containers\t3\t100MB\t50MB (50%)\n" "Local Volumes\t2\t1GB\t0B (0%)\n"
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, out, ""))
    result = sysinfo.get_docker_disk_usage()
    assert len(result) == 3
    assert result[0]["type"] == "Images"
    assert result[0]["size"] == "5GB"
    assert result[0]["reclaimable"] == "2GB (40%)"


def test_get_docker_container_sizes(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/docker")
    out = "nginx\t10MB (virtual 200MB)\tnginx:latest\tUp 3 hours\n" "redis\t5MB (virtual 50MB)\tredis:7\tUp 1 day\n"
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, out, ""))
    result = sysinfo.get_docker_container_sizes()
    assert len(result) == 2
    assert result[0]["name"] == "nginx"
    assert result[0]["size"] == "10MB (virtual 200MB)"


def test_get_docker_log_sizes(monkeypatch, tmp_path):
    # Create two fake log files
    log_a = tmp_path / "a.log"
    log_b = tmp_path / "b.log"
    log_a.write_bytes(b"x" * 1024)
    log_b.write_bytes(b"x" * 4096)

    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/docker")

    calls = {"count": 0}

    def fake_run(cmd, **_):
        calls["count"] += 1
        if calls["count"] == 1:
            # docker ps -aq
            return (0, "abc123\ndef456\n", "")
        # docker inspect
        return (0, f"/container_a\t{log_a}\n/container_b\t{log_b}\n", "")

    monkeypatch.setattr(sysinfo, "run", fake_run)
    result = sysinfo.get_docker_log_sizes(limit=5)
    assert len(result) == 2
    assert result[0]["name"] == "container_b"  # larger first
    assert result[0]["bytes"] == 4096
    assert result[1]["name"] == "container_a"


def test_get_docker_log_sizes_missing_files(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/docker")

    calls = {"count": 0}

    def fake_run(cmd, **_):
        calls["count"] += 1
        if calls["count"] == 1:
            return (0, "abc\n", "")
        return (0, "/x\t/nonexistent/path.log\n", "")

    monkeypatch.setattr(sysinfo, "run", fake_run)
    # Missing files are silently dropped
    assert sysinfo.get_docker_log_sizes() == []


# ---------- explain.investigate() ----------


def test_investigate_non_disk_returns_empty():
    r = audit.CheckResult("swap", "fail", "99%")
    assert explain.investigate(r) == []


def test_investigate_disk_combines_sources(monkeypatch):
    monkeypatch.setattr(explain.sysinfo, "get_top_paths_in", lambda d, limit: [{"path": "/var/log", "bytes": 5_000_000_000}])
    monkeypatch.setattr(explain.sysinfo, "get_largest_files", lambda d, limit, min_size_mb: [{"path": "/var/log/big.log", "bytes": 500_000_000}])
    monkeypatch.setattr(explain.sysinfo, "get_journal_disk_usage", lambda: 2_000_000_000)
    monkeypatch.setattr(explain.sysinfo, "get_docker_disk_usage", lambda: [{"type": "Images", "count": "5", "size": "3GB", "reclaimable": "1GB (33%)"}])
    monkeypatch.setattr(explain.sysinfo, "get_docker_container_sizes", lambda limit: [{"name": "nginx", "size": "10MB", "image": "nginx", "status": "Up"}])
    monkeypatch.setattr(explain.sysinfo, "get_docker_log_sizes", lambda limit: [{"name": "nginx", "log_path": "/var/lib/docker/x.log", "bytes": 1_000_000_000}])
    r = audit.CheckResult("disk /var", "warn", "85%")
    lines = explain.investigate(r)
    body = "\n".join(lines)
    assert "/var/log" in body
    assert "/var/log/big.log" in body
    assert "Journald" in body
    assert "Images" in body
    assert "nginx" in body


def test_investigate_inodes_uses_mount(monkeypatch):
    captured = {}

    def fake_top(d, limit):
        captured["mount"] = d
        return []

    monkeypatch.setattr(explain.sysinfo, "get_top_paths_in", fake_top)
    monkeypatch.setattr(explain.sysinfo, "get_largest_files", lambda d, limit, min_size_mb: [])
    monkeypatch.setattr(explain.sysinfo, "get_journal_disk_usage", lambda: None)
    monkeypatch.setattr(explain.sysinfo, "get_docker_disk_usage", lambda: None)
    monkeypatch.setattr(explain.sysinfo, "get_docker_container_sizes", lambda limit: None)
    monkeypatch.setattr(explain.sysinfo, "get_docker_log_sizes", lambda limit: None)
    explain.investigate(audit.CheckResult("inodes /data", "fail", "99%"))
    assert captured["mount"] == "/data"


def test_investigate_no_data_gives_empty(monkeypatch):
    monkeypatch.setattr(explain.sysinfo, "get_top_paths_in", lambda d, limit: [])
    monkeypatch.setattr(explain.sysinfo, "get_largest_files", lambda d, limit, min_size_mb: [])
    monkeypatch.setattr(explain.sysinfo, "get_journal_disk_usage", lambda: None)
    monkeypatch.setattr(explain.sysinfo, "get_docker_disk_usage", lambda: None)
    monkeypatch.setattr(explain.sysinfo, "get_docker_container_sizes", lambda limit: None)
    monkeypatch.setattr(explain.sysinfo, "get_docker_log_sizes", lambda limit: None)
    assert explain.investigate(audit.CheckResult("disk /var", "warn", "85%")) == []


# ---------- explain_results(deep=True) ----------


def test_explain_results_default_skips_investigation(monkeypatch):
    monkeypatch.setattr(explain, "investigate", lambda r: (_ for _ in ()).throw(AssertionError("should not be called")))
    out = explain.explain_results([audit.CheckResult("disk /", "warn", "85%")])
    assert out[0].investigation == []


def test_explain_results_deep_calls_investigate(monkeypatch):
    monkeypatch.setattr(explain, "investigate", lambda r: ["INVESTIGATION LINE"])
    out = explain.explain_results([audit.CheckResult("disk /", "warn", "85%")], deep=True)
    assert out[0].investigation == ["INVESTIGATION LINE"]


# ---------- CLI integration ----------


def test_cli_explain_deep_renders_investigation(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("disk /var", "warn", "85%"),
        ],
    )
    monkeypatch.setattr(explain, "investigate", lambda r: ["Top dirs:", "  5GB  /var/log"])
    rc, out = _capture(["explain", "--deep"])
    assert "── investigation ──" in out
    assert "/var/log" in out


def test_cli_explain_deep_json(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("disk /var", "warn", "85%"),
        ],
    )
    monkeypatch.setattr(explain, "investigate", lambda r: ["context-line-1", "context-line-2"])
    rc, out = _capture(["explain", "--deep", "--format", "json"])
    data = json.loads(out)
    assert data[0]["investigation"] == ["context-line-1", "context-line-2"]


def test_cli_explain_without_deep_no_investigation(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("disk /var", "warn", "85%"),
        ],
    )
    # explain.investigate should not run when --deep absent
    monkeypatch.setattr(explain, "investigate", lambda r: (_ for _ in ()).throw(AssertionError("called!")))
    rc, out = _capture(["explain"])
    assert "── investigation ──" not in out
