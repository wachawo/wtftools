#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""conntrack and journal-disk checks, audit --alert, and wtf explain."""

import io
import json
from contextlib import redirect_stdout

from wtftools import audit, explain, main, sysinfo


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


# ---- conntrack ----


def test_conntrack_first_location(monkeypatch):
    def fake_read(path):
        if path == "/proc/sys/net/netfilter/nf_conntrack_count":
            return "1000"
        if path == "/proc/sys/net/netfilter/nf_conntrack_max":
            return "10000"
        return ""

    monkeypatch.setattr(sysinfo, "read_file", fake_read)
    usage = sysinfo.get_conntrack_usage()
    assert usage == (1000, 10000)


def test_conntrack_second_location(monkeypatch):
    def fake_read(path):
        if "netfilter/nf_conntrack" in path:
            return ""
        if path == "/proc/sys/net/nf_conntrack_count":
            return "5"
        if path == "/proc/sys/net/nf_conntrack_max":
            return "100"
        return ""

    monkeypatch.setattr(sysinfo, "read_file", fake_read)
    assert sysinfo.get_conntrack_usage() == (5, 100)


def test_conntrack_missing(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: "")
    assert sysinfo.get_conntrack_usage() is None


def test_conntrack_bad_value(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: "garbage")
    assert sysinfo.get_conntrack_usage() is None


def test_check_conntrack_skip(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_conntrack_usage", lambda: None)
    assert audit._check_conntrack().status == "skip"


def test_check_conntrack_zero_max(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_conntrack_usage", lambda: (10, 0))
    assert audit._check_conntrack().status == "skip"


def test_check_conntrack_states(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_conntrack_usage", lambda: (10, 100))
    assert audit._check_conntrack().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_conntrack_usage", lambda: (75, 100))
    assert audit._check_conntrack().status == "warn"
    monkeypatch.setattr(audit.sysinfo, "get_conntrack_usage", lambda: (95, 100))
    assert audit._check_conntrack().status == "fail"


# ---- journal disk ----


def test_journal_disk_usage_parses_g(monkeypatch):
    out = "Archived and active journals take up 1.2G in the file system."
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, out, ""))
    bytes_used = sysinfo.get_journal_disk_usage()
    assert bytes_used is not None
    assert bytes_used > 1_000_000_000  # ~1.2 GB


def test_journal_disk_usage_parses_m(monkeypatch):
    out = "Archived and active journals take up 824.0M in the file system."
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, out, ""))
    bytes_used = sysinfo.get_journal_disk_usage()
    assert bytes_used is not None
    assert bytes_used > 800_000_000


def test_journal_disk_usage_missing(monkeypatch):
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (1, "", ""))
    assert sysinfo.get_journal_disk_usage() is None


def test_journal_disk_usage_unparseable(monkeypatch):
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, "no numbers here at all", ""))
    # The regex will not match if no digits → returns None
    result = sysinfo.get_journal_disk_usage()
    assert result is None


def test_check_journal_disk_states(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_journal_disk_usage", lambda: None)
    assert audit._check_journal_disk().status == "skip"
    monkeypatch.setattr(audit.sysinfo, "get_journal_disk_usage", lambda: 100_000_000)
    assert audit._check_journal_disk().status == "ok"
    monkeypatch.setattr(audit.sysinfo, "get_journal_disk_usage", lambda: 5 * 1024**3)
    assert audit._check_journal_disk().status == "warn"
    monkeypatch.setattr(audit.sysinfo, "get_journal_disk_usage", lambda: 20 * 1024**3)
    assert audit._check_journal_disk().status == "fail"


# ---- --alert ----


def test_alert_not_fired_when_no_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("x", "ok", "fine")])
    sentinel = tmp_path / "alert.txt"
    rc, _ = _capture(["audit", "--alert", f"touch {sentinel}"])
    assert not sentinel.exists()


def test_alert_fired_on_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("x", "fail", "boom")])
    sentinel = tmp_path / "alert.txt"
    rc, _ = _capture(["audit", "--alert", f"cat > {sentinel}"])
    assert sentinel.exists()
    body = sentinel.read_text()
    assert "FAIL" in body
    assert "boom" in body


def test_alert_on_warn(monkeypatch, tmp_path):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("x", "warn", "soft")])
    sentinel = tmp_path / "alert.txt"
    _capture(["audit", "--alert", f"touch {sentinel}", "--alert-on", "warn"])
    assert sentinel.exists()


def test_alert_env_vars(monkeypatch, tmp_path):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("a", "fail", "x"),
            audit.CheckResult("b", "warn", "y"),
        ],
    )
    sentinel = tmp_path / "env.txt"
    _capture(["audit", "--alert", f"echo FAIL=$WTF_FAIL_COUNT WARN=$WTF_WARN_COUNT HOST=$WTF_HOST > {sentinel}"])
    text = sentinel.read_text()
    assert "FAIL=1" in text
    assert "WARN=1" in text
    assert "HOST=" in text


def test_alert_timeout_handled(monkeypatch):
    """If the alert command hangs longer than the 30s budget, no crash."""
    import subprocess as sp

    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("x", "fail", "boom")])

    def fake_run(*a, **kw):
        raise sp.TimeoutExpired(cmd="x", timeout=30)

    monkeypatch.setattr("subprocess.run", fake_run)
    rc, _ = _capture(["audit", "--alert", "sleep 99"])
    # cmd_audit returns 2 (FAIL exit code) regardless of alert outcome
    assert rc == 2


# ---- wtf explain ----


def test_suggest_swap():
    r = audit.CheckResult("swap", "fail", "99%")
    s = explain.suggest(r)
    assert "Swap" in s.advice or "swap" in s.advice.lower()


def test_suggest_disk_with_name():
    r = audit.CheckResult("disk /var", "warn", "85%")
    s = explain.suggest(r)
    assert "/var" in s.advice  # callable advice picks up mount path


def test_suggest_inodes_with_name():
    r = audit.CheckResult("inodes /home", "fail", "98%")
    s = explain.suggest(r)
    assert "/home" in s.advice


def test_suggest_unknown_check_uses_fallback():
    r = audit.CheckResult("nonexistent-check-xyz", "fail", "??")
    s = explain.suggest(r)
    assert "No built-in advice" in s.advice


def test_explain_results_filters_ok():
    results = [
        audit.CheckResult("a", "ok", ""),
        audit.CheckResult("b", "warn", ""),
        audit.CheckResult("c", "fail", ""),
    ]
    out = explain.explain_results(results)
    assert len(out) == 2
    assert all(s.status in ("warn", "fail") for s in out)


def test_explain_results_include_ok():
    results = [audit.CheckResult("a", "ok", "")]
    out = explain.explain_results(results, include_ok=True)
    assert len(out) == 1


def test_render_prompt_contains_markers():
    results = [
        audit.CheckResult("uptime", "ok", "3d"),
        audit.CheckResult("swap", "fail", "99%", detail=["d1", "d2"]),
    ]
    out = explain.render_prompt(results, host="myhost")
    assert "myhost" in out
    assert "[ OK ]" in out
    assert "[FAIL]" in out
    assert "d1" in out


def test_render_prompt_without_host():
    results = [audit.CheckResult("x", "warn", "y")]
    out = explain.render_prompt(results)
    assert "[WARN]" in out


def test_cmd_explain_no_problems(monkeypatch):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("x", "ok", "fine")])
    rc, out = _capture(["explain"])
    assert rc == 0
    assert "nothing to explain" in out


def test_cmd_explain_with_problems(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("swap", "fail", "99%"),
        ],
    )
    rc, out = _capture(["explain"])
    assert rc == 0
    assert "EXPLAIN" in out
    assert "swap" in out.lower()
    assert "RAM" in out or "memory" in out.lower()


def test_cmd_explain_prompt_mode(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("swap", "fail", "99%"),
        ],
    )
    rc, out = _capture(["explain", "--prompt"])
    assert rc == 0
    assert "senior SRE" in out  # PROMPT_PREAMBLE leaked
    assert "Audit findings" in out


def test_cmd_explain_json(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("swap", "fail", "x"),
        ],
    )
    rc, out = _capture(["explain", "--format", "json"])
    data = json.loads(out)
    assert len(data) == 1
    assert data[0]["name"] == "swap"
    assert "advice" in data[0]


def test_cmd_explain_all_includes_ok(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("x", "ok", ""),
        ],
    )
    rc, out = _capture(["explain", "--all"])
    assert rc == 0
    assert "x" in out


# ---- registry sanity ----


def test_new_checks_in_registry():
    names = audit.list_check_names()
    assert "conntrack" in names
    assert "journal-disk" in names
