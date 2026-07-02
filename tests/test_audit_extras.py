#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for new audit-module surface: registry, filter, since-hours, run_audit(names)."""

import pytest

from wtftools import audit


def test_list_check_names_non_empty():
    names = audit.list_check_names()
    assert "memory" in names
    assert "disks" in names
    assert "crontab" in names
    assert len(names) >= 15


def test_run_audit_with_names_subset(monkeypatch):
    called = []

    def fake_check():
        called.append("mem")
        return audit.CheckResult("memory", "ok", "ok")

    monkeypatch.setitem(audit.CHECK_REGISTRY, "memory", fake_check)
    results = audit.run_audit(names=["memory"])
    assert called == ["mem"]
    assert len(results) == 1
    assert results[0].name == "memory"


def test_run_audit_with_unknown_name(monkeypatch):
    results = audit.run_audit(names=["nonexistent-check-xyz"])
    assert len(results) == 1
    assert results[0].status == "skip"
    assert "unknown" in results[0].message


@pytest.mark.integration
def test_run_audit_full_still_works():
    results = audit.run_audit()
    assert len(results) >= 15


def test_filter_by_status_fail_only():
    results = [
        audit.CheckResult("a", "ok", ""),
        audit.CheckResult("b", "fail", ""),
        audit.CheckResult("c", "warn", ""),
    ]
    filtered = audit.filter_by_status(results, ["fail"])
    assert [r.name for r in filtered] == ["b"]


def test_filter_by_status_problem():
    results = [
        audit.CheckResult("a", "ok", ""),
        audit.CheckResult("b", "fail", ""),
        audit.CheckResult("c", "warn", ""),
        audit.CheckResult("d", "skip", ""),
    ]
    filtered = audit.filter_by_status(results, ["fail", "warn"])
    assert {r.name for r in filtered} == {"b", "c"}


def test_set_since_hours_clamps():
    audit.set_since_hours(0)
    assert audit._SINCE_HOURS == 1
    audit.set_since_hours(48)
    assert audit._SINCE_HOURS == 48
    # restore default
    audit.set_since_hours(24)


def test_since_hours_used_by_oom_check(monkeypatch):
    audit.set_since_hours(6)
    seen = {}

    def fake_oom(hours):
        seen["hours"] = hours
        return []

    monkeypatch.setattr(audit.sysinfo, "get_oom_events", fake_oom)
    r = audit._check_oom_kills()
    assert seen["hours"] == 6
    assert "6h" in r.name
    audit.set_since_hours(24)


def test_since_hours_used_by_kernel(monkeypatch):
    audit.set_since_hours(3)
    monkeypatch.setattr(audit.shutil, "which", lambda _: "/bin/journalctl")
    monkeypatch.setattr(audit.sysinfo, "get_recent_kernel_errors", lambda hours, limit: [])
    r = audit._check_kernel_errors()
    assert "3h" in r.name
    audit.set_since_hours(24)


def test_since_hours_used_by_auth(monkeypatch):
    audit.set_since_hours(2)
    monkeypatch.setattr(audit.sysinfo, "get_failed_auth_count", lambda hours: 0)
    r = audit._check_failed_auth()
    assert "2h" in r.name
    audit.set_since_hours(24)


@pytest.mark.integration
def test_check_registry_callables():
    """All registered checks must be callable and not crash on smoke invocation."""
    for name, fn in audit.CHECK_REGISTRY.items():
        try:
            result = fn()
        except Exception as exc:  # pragma: no cover — fail loudly if regressed
            assert False, f"{name} crashed: {exc}"
        if isinstance(result, list):
            for r in result:
                assert isinstance(r, audit.CheckResult)
        else:
            assert isinstance(result, audit.CheckResult)
