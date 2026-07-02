#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for wtftools.main — CLI dispatch."""

import io
import json
import os
import tempfile
from contextlib import redirect_stdout

import pytest

from wtftools import audit, main


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


def test_build_parser_help():
    parser = main.build_parser()
    assert parser.prog == "wtf"


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main.main(["--version"])
    assert exc.value.code == 0


@pytest.mark.integration
def test_cmd_info_text():
    rc, out = _capture(["info"])
    assert rc == 0
    assert "SYSTEM" in out


@pytest.mark.integration
def test_cmd_info_json():
    rc, out = _capture(["info", "--format", "json"])
    assert rc == 0
    data = json.loads(out)
    assert "hostname" in data
    assert "memory" in data


@pytest.mark.integration
def test_cmd_audit_text():
    rc, out = _capture(["audit"])
    assert rc in (0, 2)
    assert "AUDIT" in out
    assert "Summary" in out


@pytest.mark.integration
def test_cmd_audit_json():
    rc, out = _capture(["audit", "--format", "json"])
    data = json.loads(out)
    assert "results" in data
    assert "summary" in data


def test_cmd_audit_verbose_renders_detail(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("x", "fail", "boom", detail=["d1", "d2"]),
        ],
    )
    rc, out = _capture(["-v", "audit"])
    assert "d1" in out and "d2" in out


def test_cmd_audit_exit_code_fail(monkeypatch):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("x", "fail", "boom")])
    rc, _ = _capture(["audit"])
    assert rc == 2


def test_cmd_audit_strict(monkeypatch):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("x", "warn", "boom")])
    rc, _ = _capture(["audit", "--strict"])
    assert rc == 1
    rc, _ = _capture(["audit"])
    assert rc == 0


def test_cmd_audit_exit_zero(monkeypatch):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("x", "fail", "boom")])
    rc, _ = _capture(["audit", "--exit-zero"])
    assert rc == 0


def test_cmd_crontab_explicit_file_clean():
    with tempfile.NamedTemporaryFile("w", suffix="_systemtest", delete=False) as f:
        f.write("0 5 * * * root /usr/bin/true\n")
        path = f.name
    try:
        rc, out = _capture(["crontab", path])
        assert rc == 0
        assert "CRONTAB" in out
    finally:
        os.unlink(path)


def test_cmd_crontab_explicit_file_bad():
    with tempfile.NamedTemporaryFile("w", suffix="_usertest", delete=False) as f:
        f.write("99 * * * * /bin/false\n")
        path = f.name
    try:
        rc, out = _capture(["crontab", path])
        assert rc == 1
        assert "minute" in out
    finally:
        os.unlink(path)


def test_cmd_crontab_json():
    with tempfile.NamedTemporaryFile("w", suffix="_usertest", delete=False) as f:
        f.write("0 5 * * * /usr/bin/true\n")
        path = f.name
    try:
        rc, out = _capture(["crontab", "--format", "json", path])
        data = json.loads(out)
        assert data["total_files"] == 1
        assert data["success"] is True
    finally:
        os.unlink(path)


def test_cmd_crontab_with_username(monkeypatch, tmp_path):
    user_file = tmp_path / "fakecron"
    user_file.write_text("0 5 * * * /usr/bin/true\n")
    monkeypatch.setattr(main.cron, "find_user_crontab", lambda u: str(user_file))
    rc, out = _capture(["crontab", "-u", "alice"])
    assert rc == 0


def test_cmd_crontab_with_unknown_username(monkeypatch):
    monkeypatch.setattr(main.cron, "find_user_crontab", lambda u: None)
    rc, _ = _capture(["crontab", "-u", "nobody"])
    assert rc == 0


def test_cmd_crontab_positional_username(monkeypatch, tmp_path):
    user_file = tmp_path / "fakecron"
    user_file.write_text("0 5 * * * /usr/bin/true\n")
    monkeypatch.setattr(main.cron, "find_user_crontab", lambda u: str(user_file))
    rc, _ = _capture(["crontab", "alice"])
    assert rc == 0


def test_cmd_crontab_directory(tmp_path):
    cron_dir = tmp_path / "crons"
    cron_dir.mkdir()
    (cron_dir / "valid").write_text("0 5 * * * root /usr/bin/true\n")
    rc, _ = _capture(["crontab", str(cron_dir)])
    assert rc == 0


def test_cmd_crontab_missing_positional():
    rc, out = _capture(["crontab", "/nonexistent/cron/file"])
    # Falls back to default discovery; should not crash
    assert rc in (0, 1)


def test_cmd_crontab_garbage_token():
    rc, out = _capture(["crontab", "not-a-real-thing!"])
    assert rc in (0, 1)


def test_cmd_crontab_strict_no_warnings(monkeypatch):
    monkeypatch.setattr(main.cron, "discover_default_targets", lambda: [])
    rc, _ = _capture(["crontab", "--strict"])
    assert rc == 0


def test_cmd_crontab_exit_zero(monkeypatch, tmp_path):
    f = tmp_path / "c"
    f.write_text("99 * * * * /bin/false\n")
    rc, _ = _capture(["crontab", "--exit-zero", str(f)])
    assert rc == 0


def test_cmd_crontab_no_targets(monkeypatch):
    monkeypatch.setattr(main.cron, "discover_default_targets", lambda: [])
    rc, out = _capture(["crontab"])
    assert rc == 0
    assert "no crontab" in out


def test_cmd_crontab_no_targets_json(monkeypatch):
    monkeypatch.setattr(main.cron, "discover_default_targets", lambda: [])
    rc, out = _capture(["crontab", "--format", "json"])
    data = json.loads(out)
    assert data["files"] == []


def test_cmd_crontab_invalid_username_skipped(monkeypatch):
    calls = []
    monkeypatch.setattr(main.cron, "find_user_crontab", lambda n: calls.append(n) or None)
    monkeypatch.setattr(main.cron, "discover_default_targets", lambda: [])
    _capture(["crontab", "-u", "bad;name"])
    assert "bad;name" not in calls  # rejected before reaching `crontab -l -u <name>`
    _capture(["crontab", "-u", "alice"])
    assert "alice" in calls  # a valid name still goes through


def test_default_command_runs_audit(monkeypatch):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("x", "ok", "fine")])
    rc, out = _capture([])
    assert rc == 0
    assert "Summary" in out


def test_verbose_sets_logging(monkeypatch):
    import logging

    root = logging.getLogger()
    prev = root.level
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("x", "ok", "fine")])
    try:
        _capture(["--verbose", "audit"])
        assert root.level == logging.INFO
    finally:
        root.setLevel(prev)


def test_quiet_sets_logging(monkeypatch):
    import logging

    root = logging.getLogger()
    prev = root.level
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("x", "ok", "fine")])
    try:
        _capture(["--quiet", "audit"])
        assert root.level == logging.ERROR
    finally:
        root.setLevel(prev)


def test_keyboard_interrupt(monkeypatch):
    def boom(args):
        raise KeyboardInterrupt

    monkeypatch.setattr(main, "cmd_audit", boom)
    rc = main.main(["audit"])
    assert rc == 130


def test_no_color_flag():
    rc, out = _capture(["--no-color", "info"])
    # no ANSI escapes in output
    assert "\033[" not in out


def test_cmd_crontab_with_S_and_U_flags(tmp_path, monkeypatch):
    sys_file = tmp_path / "sysfile"
    sys_file.write_text("0 5 * * * root /usr/bin/true\n")
    usr_file = tmp_path / "usrfile"
    usr_file.write_text("0 5 * * * /usr/bin/true\n")
    # Bypass owner/permission checks since tmp_path is not root-owned 0644.
    monkeypatch.setattr(main.cron, "check_owner_and_permissions", lambda p: [])
    rc, _ = _capture(["crontab", "-S", str(sys_file), "-U", str(usr_file)])
    assert rc == 0


def test_cmd_audit_runs_default_when_no_subcommand(monkeypatch):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("x", "fail", "boom")])
    rc, _ = _capture([])
    assert rc == 2


def test_default_command_preserves_global_format(monkeypatch):
    # `wtf -f json` (no subcommand) must default to audit AND keep -f json.
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("x", "ok", "fine")])
    rc, out = _capture(["-f", "json"])
    assert rc == 0
    assert '"schema_version"' in out


def test_csv_safe_quotes_formula_cells():
    assert main._csv_safe("=cmd()") == "'=cmd()"
    assert main._csv_safe("+1") == "'+1"
    assert main._csv_safe("-2") == "'-2"
    assert main._csv_safe("@x") == "'@x"
    assert main._csv_safe("normal") == "normal"
    assert main._csv_safe("") == ""


def test_toplevel_exception_returns_error_code(monkeypatch):
    def boom(names=None, ignore=None):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(audit, "run_audit", boom)
    rc, _ = _capture(["audit"])
    assert rc == 1  # one-line error to stderr, no traceback dumped at the user


def test_toplevel_exception_reraises_with_verbose(monkeypatch):
    def boom(names=None, ignore=None):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(audit, "run_audit", boom)
    with pytest.raises(RuntimeError):
        main.main(["--verbose", "audit"])


def test_global_audit_only_format_rejected_on_non_audit():
    # `-f csv` (global) on a resource command is rejected, not silently ignored.
    rc, _ = _capture(["-f", "csv", "cpu"])
    assert rc == 2


def test_global_audit_only_format_allowed_on_audit(monkeypatch):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("x", "ok", "fine")])
    rc, out = _capture(["-f", "csv", "audit"])
    assert rc == 0
    assert "name,status,message,detail" in out
