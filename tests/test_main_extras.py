#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for new CLI surface: doctor, --check, --only, --since, --watch, --list-checks."""

import io
import json
from contextlib import redirect_stdout

from wtftools import audit, main


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


def test_doctor_text():
    rc, out = _capture(["doctor"])
    assert rc == 0
    assert "DOCTOR" in out
    assert "python" in out


def test_doctor_json():
    rc, out = _capture(["doctor", "--format", "json"])
    assert rc == 0
    data = json.loads(out)
    assert "checks" in data
    assert any(c["name"] == "python" for c in data["checks"])
    assert "version" in data


def test_audit_list_checks():
    rc, out = _capture(["audit", "--list-checks"])
    assert rc == 0
    assert "memory" in out
    assert "disks" in out


def test_audit_check_specific(monkeypatch):
    def fake_mem():
        return audit.CheckResult("memory", "ok", "fine")
    monkeypatch.setitem(audit.CHECK_REGISTRY, "memory", fake_mem)
    rc, out = _capture(["audit", "--check", "memory"])
    assert rc == 0
    assert "memory" in out


def test_audit_check_multiple(monkeypatch):
    monkeypatch.setitem(audit.CHECK_REGISTRY, "memory",
                        lambda: audit.CheckResult("memory", "ok", "x"))
    monkeypatch.setitem(audit.CHECK_REGISTRY, "swap",
                        lambda: audit.CheckResult("swap", "warn", "y"))
    rc, out = _capture(["audit", "--check", "memory", "--check", "swap"])
    assert rc == 0
    assert "memory" in out and "swap" in out


def test_audit_check_unknown():
    rc, out = _capture(["audit", "--check", "nope"])
    assert "nope" in out
    assert "unknown" in out.lower() or "skip" in out.lower()


def test_audit_only_fail(monkeypatch):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [
        audit.CheckResult("a", "ok", ""),
        audit.CheckResult("b", "fail", "boom"),
        audit.CheckResult("c", "warn", "meh"),
    ])
    rc, out = _capture(["audit", "--only", "fail"])
    assert "boom" in out
    assert "meh" not in out
    assert rc == 2


def test_audit_only_problem(monkeypatch):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [
        audit.CheckResult("a", "ok", ""),
        audit.CheckResult("b", "fail", "f"),
        audit.CheckResult("c", "warn", "w"),
    ])
    rc, out = _capture(["audit", "--only", "problem"])
    assert "f" in out and "w" in out
    assert "fine" not in out


def test_audit_only_empty(monkeypatch):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [
        audit.CheckResult("a", "ok", "fine"),
    ])
    rc, out = _capture(["audit", "--only", "fail"])
    assert "no checks matched" in out


def test_audit_only_json_empty(monkeypatch):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [])
    rc, out = _capture(["audit", "--only", "fail", "--format", "json"])
    data = json.loads(out)
    assert data["results"] == []


def test_audit_since_passed_to_module(monkeypatch):
    set_hours = []
    monkeypatch.setattr(audit, "set_since_hours", lambda h: set_hours.append(h))
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [
        audit.CheckResult("x", "ok", "")
    ])
    _capture(["audit", "--since", "6"])
    assert set_hours == [6]


def test_audit_watch_runs_once_then_interrupt(monkeypatch):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [
        audit.CheckResult("x", "ok", "good")
    ])

    def fake_sleep(_):
        raise KeyboardInterrupt
    monkeypatch.setattr(main.time, "sleep", fake_sleep)
    rc, out = _capture(["audit", "--watch", "1"])
    assert rc == 0
    assert "watch stopped" in out


def test_audit_watch_handles_empty_results(monkeypatch):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [])

    def fake_sleep(_):
        raise KeyboardInterrupt
    monkeypatch.setattr(main.time, "sleep", fake_sleep)
    rc, out = _capture(["audit", "--watch", "1", "--only", "fail"])
    assert rc == 0
    assert "no checks matched" in out


def test_status_filters_dict_has_expected_keys():
    assert set(main.STATUS_FILTERS.keys()) == {"fail", "warn", "problem", "skip", "ok", "all"}


def test_gather_doctor_report_handles_missing_psutil(monkeypatch):
    monkeypatch.setattr(main.sysinfo, "HAS_PSUTIL", False)
    report = main._gather_doctor_report()
    psutil_entry = next(c for c in report["checks"] if c["name"] == "psutil")
    assert psutil_entry["status"] == "warn"
    assert "missing" in psutil_entry["detail"]


def test_gather_doctor_report_missing_proc_file(monkeypatch):
    real_exists = main.os.path.exists
    monkeypatch.setattr(main.os.path, "exists",
                        lambda p: False if p == "/proc/meminfo" else real_exists(p))
    report = main._gather_doctor_report()
    meminfo = next(c for c in report["checks"] if c["name"] == "/proc/meminfo")
    assert meminfo["status"] == "fail"
