#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the stable public API surface exposed at `wtftools` top level."""

import pytest

import wtftools


def test_version_is_semver_ish():
    assert wtftools.__version__
    parts = wtftools.__version__.split(".")
    assert len(parts) >= 2
    # Major and minor must be plain integers.
    assert parts[0].isdigit()
    assert parts[1].isdigit()


def test_version_components_are_integers():
    """Sanity: major + minor must parse as integers (PEP 440 prefix)."""
    major, minor = wtftools.__version__.split(".")[:2]
    assert int(major) >= 0
    assert int(minor) >= 0


def test_description_present():
    assert wtftools.__description__
    assert "Linux" in wtftools.__description__


def test_all_is_documented():
    assert "__version__" in wtftools.__all__
    assert "CheckResult" in wtftools.__all__
    assert "run_audit" in wtftools.__all__
    assert "summarize" in wtftools.__all__
    assert "list_check_names" in wtftools.__all__


def test_check_result_reexport():
    """`from wtftools import CheckResult` must work for embedders."""
    assert wtftools.CheckResult is not None
    r = wtftools.CheckResult(name="x", status="ok", message="y")
    assert r.name == "x"
    assert r.status == "ok"


def test_run_audit_reexport(monkeypatch):
    """`from wtftools import run_audit` must work and behave like the submodule."""
    from wtftools import audit as audit_mod

    monkeypatch.setattr(audit_mod, "CHECK_REGISTRY", {"only": lambda: audit_mod.CheckResult("x", "ok", "")})
    results = wtftools.run_audit()
    assert len(results) == 1
    assert results[0].name == "x"


def test_summarize_reexport():
    results = [
        wtftools.CheckResult("a", "ok", ""),
        wtftools.CheckResult("b", "fail", ""),
    ]
    totals = wtftools.summarize(results)
    assert totals["ok"] == 1
    assert totals["fail"] == 1


def test_list_check_names_reexport():
    names = wtftools.list_check_names()
    assert isinstance(names, list)
    assert "memory" in names
    assert "disks" in names


def test_unknown_attribute_raises():
    with pytest.raises(AttributeError, match="has no attribute"):
        wtftools.does_not_exist  # noqa


def test_lazy_imports_dont_load_submodules_eagerly():
    """`import wtftools` must not pull in heavy submodules.

    This is important for `wtf --version` startup time and for embedders who
    only want `__version__` without paying for psutil/daemon/explain imports.
    """
    import importlib
    import sys

    # Snapshot first: deleting wtftools.* from sys.modules without restoring
    # would poison module identity for every test that runs afterwards.
    saved = {name: mod for name, mod in sys.modules.items() if name == "wtftools" or name.startswith("wtftools.")}
    try:
        for name in saved:
            del sys.modules[name]
        importlib.import_module("wtftools")
        # Heavy submodules must not be pulled in just by `import wtftools`.
        for heavy in ("wtftools.sysinfo", "wtftools.explain", "wtftools.llm", "wtftools.events", "wtftools.snapshot"):
            assert heavy not in sys.modules
    finally:
        for name in [n for n in sys.modules if n == "wtftools" or n.startswith("wtftools.")]:
            if name not in saved:
                del sys.modules[name]
        sys.modules.update(saved)
