#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for iteration 12: wtf init wizard."""

import io
import json
import os
from contextlib import redirect_stdout
from unittest import mock

import pytest

from wtftools import main


def _capture(argv, stdin_text=""):
    buf = io.StringIO()
    with redirect_stdout(buf):
        if stdin_text:
            with mock.patch("builtins.input", side_effect=stdin_text.splitlines()):
                rc = main.main(argv)
        else:
            rc = main.main(argv)
    return rc, buf.getvalue()


# ---------- _plan_init ----------

def test_plan_init_defaults():
    ns = mock.Mock(enable_config=None, enable_motd=None,
                   enable_wtfd=False, enable_cron=None, config_path=None)
    actions = main._plan_init(ns)
    keys = [a["key"] for a in actions]
    assert "config" in keys
    assert "motd" in keys
    assert "cron" in keys
    assert "wtfd" not in keys  # off by default


def test_plan_init_all_disabled():
    ns = mock.Mock(enable_config=False, enable_motd=False,
                   enable_wtfd=False, enable_cron=False, config_path=None)
    actions = main._plan_init(ns)
    assert actions == []


def test_plan_init_with_wtfd():
    ns = mock.Mock(enable_config=False, enable_motd=False,
                   enable_wtfd=True, enable_cron=False, config_path=None)
    actions = main._plan_init(ns)
    assert [a["key"] for a in actions] == ["wtfd"]


def test_plan_init_custom_config_path():
    ns = mock.Mock(enable_config=None, enable_motd=False,
                   enable_wtfd=False, enable_cron=False,
                   config_path="/tmp/foo/bar.ini")
    actions = main._plan_init(ns)
    assert actions[0]["key"] == "config"
    assert "/tmp/foo/bar.ini" in actions[0]["title"]


# ---------- CLI: dry-run ----------

def test_init_dry_run_non_interactive():
    rc, out = _capture(["init", "--dry-run", "--non-interactive"])
    assert rc == 0
    assert "DRY RUN" in out
    assert "config" in out
    assert "motd" in out
    assert "cron" in out
    assert "wtfd" not in out  # off by default


def test_init_dry_run_with_wtfd():
    rc, out = _capture(["init", "--dry-run", "--non-interactive",
                        "--enable-wtfd"])
    assert "wtfd" in out


def test_init_dry_run_no_cron_no_motd():
    rc, out = _capture(["init", "--dry-run", "--non-interactive",
                        "--no-cron", "--no-motd"])
    assert "cron" not in out
    assert "motd" not in out
    assert "config" in out


# ---------- CLI: applies ----------

def test_init_writes_config(monkeypatch, tmp_path):
    cfg_target = tmp_path / "etc" / "wtftools" / "config.ini"
    rc, out = _capture(["init", "--non-interactive",
                        "--config-path", str(cfg_target),
                        "--no-motd", "--no-cron"])
    assert rc == 0
    assert cfg_target.exists()
    assert "[thresholds]" in cfg_target.read_text()
    assert "done" in out.lower()


def test_init_writes_motd(monkeypatch, tmp_path):
    motd_dir = tmp_path / "update-motd.d"
    motd_dir.mkdir()
    monkeypatch.setattr(main, "_install_motd", main._install_motd)
    # Redirect motd path via monkeypatching the planner
    real_plan = main._plan_init

    def plan_with_motd(args):
        actions = real_plan(args)
        for a in actions:
            if a["key"] == "motd":
                a["apply"] = lambda: main._install_motd(str(motd_dir / "99-wtf-brief"))
        return actions

    monkeypatch.setattr(main, "_plan_init", plan_with_motd)
    rc, _ = _capture(["init", "--non-interactive", "--no-config", "--no-cron"])
    assert rc == 0
    motd_file = motd_dir / "99-wtf-brief"
    assert motd_file.exists()
    assert "wtf audit --brief" in motd_file.read_text()
    assert os.access(str(motd_file), os.X_OK)


def test_init_writes_cron(monkeypatch, tmp_path):
    cron_dir = tmp_path / "cron.d"
    cron_dir.mkdir()
    real_plan = main._plan_init

    def plan_with_cron(args):
        actions = real_plan(args)
        for a in actions:
            if a["key"] == "cron":
                a["apply"] = lambda: main._install_cron(str(cron_dir / "wtftools-hourly"))
        return actions

    monkeypatch.setattr(main, "_plan_init", plan_with_cron)
    rc, _ = _capture(["init", "--non-interactive", "--no-config", "--no-motd"])
    assert rc == 0
    target = cron_dir / "wtftools-hourly"
    assert target.exists()
    body = target.read_text()
    assert "wtf audit --save" in body


def test_init_handles_apply_failure(monkeypatch, tmp_path):
    """One failing step should not abort the others; rc=1 surfaces the issue."""
    real_plan = main._plan_init

    def plan_with_failure(args):
        actions = real_plan(args)
        for a in actions:
            if a["key"] == "motd":
                def boom():
                    raise OSError("nope")
                a["apply"] = boom
        return actions

    monkeypatch.setattr(main, "_plan_init", plan_with_failure)
    cfg_target = tmp_path / "cfg.ini"
    rc, out = _capture([
        "init", "--non-interactive",
        "--config-path", str(cfg_target),
        "--no-cron",
    ])
    # one step (config) succeeded, one (motd) failed
    assert rc == 1
    assert "✓" in out
    assert "✗" in out
    assert "nope" in out


# ---------- interactive prompts ----------

def test_init_interactive_default_yes(tmp_path):
    """Pressing enter for the config step (default Y) should accept it; the
    other steps we'll decline explicitly so the test does not try to write
    /etc/update-motd.d/ or /etc/cron.d/."""
    cfg_target = tmp_path / "cfg.ini"
    # Three default steps shown: config (Y default), motd (Y), cron (Y).
    # We press enter on config, 'n' on motd, 'n' on cron.
    with mock.patch("builtins.input", side_effect=["", "n", "n"]):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main.main(["init", "--config-path", str(cfg_target)])
    assert rc == 0
    assert cfg_target.exists()


def test_init_interactive_ctrl_c():
    with mock.patch("builtins.input", side_effect=KeyboardInterrupt):
        rc, out = _capture(["init"])
    assert rc == 0
    assert "nothing selected" in out or "aborting" in out


def test_init_interactive_eof():
    with mock.patch("builtins.input", side_effect=EOFError):
        rc, out = _capture(["init"])
    assert rc == 0


def test_init_all_declined():
    """Answering 'n' to everything is a no-op."""
    with mock.patch("builtins.input", side_effect=["n", "n", "n", "n", "n", "n"]):
        rc, out = _capture(["init"])
    assert rc == 0
    assert "nothing" in out.lower() or "done" in out.lower()


# ---------- helpers ----------

def test_install_motd_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        main._install_motd(str(tmp_path / "nonexistent" / "99-wtf"))


def test_install_cron_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        main._install_cron(str(tmp_path / "nonexistent" / "wtf-hourly"))


def test_write_example_config_creates_parent(tmp_path):
    target = tmp_path / "deep" / "nested" / "config.ini"
    main._write_example_config(str(target))
    assert target.exists()


# ---------- schema files ----------

def test_schema_audit_v1_exists():
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs", "schema", "audit-v1.json")
    assert os.path.exists(schema_path)
    with open(schema_path) as f:
        schema = json.load(f)
    assert schema["title"]
    assert "CheckResult" in schema["definitions"]


def test_schema_fleet_v1_exists():
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs", "schema", "fleet-v1.json")
    assert os.path.exists(schema_path)
    with open(schema_path) as f:
        schema = json.load(f)
    assert "FleetHost" in schema["definitions"]


# ---------- example plugins ----------

def test_example_plugins_exist():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    plugins_dir = os.path.join(here, "examples", "plugins")
    assert os.path.isdir(plugins_dir)
    expected = {"check-cert-domain.sh", "check-postgres-connections.sh",
                "check-redis-memory.sh", "check-disk-write.sh"}
    found = set(os.listdir(plugins_dir))
    assert expected.issubset(found)
    # All must be executable
    for name in expected:
        path = os.path.join(plugins_dir, name)
        assert os.access(path, os.X_OK), f"{name} is not executable"
