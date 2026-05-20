#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for wtftools.checks.cron — vendored crontab validator."""

import os
from unittest import mock

import pytest

from wtftools.checks import cron


def test_check_filename_valid():
    assert cron.check_filename("/etc/cron.d/myjob") == ""
    assert cron.check_filename("anacron") == ""


@pytest.mark.parametrize("name,expected", [
    ("", "empty"),
    (".hidden", "starts with '.'"),
    ("backup~", "ends with '~'"),
    ("backup.sh", "contains '.'"),
    ("backup#", "contains '#'"),
    ("a,b", "contains ','"),
    ("$weird", "outside [A-Za-z0-9_-]"),
])
def test_check_filename_invalid(name, expected):
    out = cron.check_filename(name)
    assert expected in out


def test_check_daemon_active():
    with mock.patch("subprocess.run") as p:
        p.return_value = mock.Mock(returncode=0, stdout="active\n", stderr="")
        assert cron.check_daemon() == []


def test_check_daemon_inactive_fallback_to_crond():
    calls = []
    def fake_run(cmd, **_):
        calls.append(cmd[-1])
        if "crond" in cmd:
            return mock.Mock(returncode=3, stdout="inactive\n", stderr="")
        return mock.Mock(returncode=3, stdout="inactive\n", stderr="")
    with mock.patch("subprocess.run", side_effect=fake_run):
        errors = cron.check_daemon()
    assert errors and "not active" in errors[0]


def test_check_daemon_not_found():
    with mock.patch("subprocess.run", side_effect=FileNotFoundError):
        errors = cron.check_daemon()
    assert any("systemctl" in e for e in errors)


def test_check_daemon_other_exception():
    with mock.patch("subprocess.run", side_effect=RuntimeError("x")):
        errors = cron.check_daemon()
    assert errors and "cron daemon" in errors[0]


def test_check_kind_regular(tmp_path):
    f = tmp_path / "x"
    f.write_text("")
    assert cron.check_kind(str(f)) == "regular_file"


def test_check_kind_directory(tmp_path):
    assert cron.check_kind(str(tmp_path)) == "directory"


def test_check_kind_symlink(tmp_path):
    target = tmp_path / "t"
    target.write_text("")
    link = tmp_path / "l"
    link.symlink_to(target)
    assert cron.check_kind(str(link), follow_symlink=False) == "symlink"


def test_check_owner_and_permissions_missing():
    errors = cron.check_owner_and_permissions("/nonexistent/path/xyz")
    assert any("does not exist" in e for e in errors)


def test_check_owner_and_permissions_real(tmp_path):
    f = tmp_path / "cron"
    f.write_text("0 5 * * * root /usr/bin/true\n")
    os.chmod(str(f), 0o600)
    # Will at least flag wrong permissions; owner depends on test env.
    errors = cron.check_owner_and_permissions(str(f), owner_uid=os.getuid())
    assert any("permissions" in e for e in errors)


def test_check_owner_and_permissions_correct(tmp_path):
    f = tmp_path / "cron"
    f.write_text("")
    os.chmod(str(f), 0o644)
    errors = cron.check_owner_and_permissions(str(f), owner_uid=os.getuid())
    assert errors == []


def test_check_owner_and_permissions_broken_symlink(tmp_path):
    link = tmp_path / "link"
    link.symlink_to("/nope/nope")
    errors = cron.check_owner_and_permissions(str(link), owner_uid=os.getuid())
    assert any("broken symlink" in e for e in errors)


def test_get_line_content(tmp_path):
    f = tmp_path / "c"
    f.write_text("a\nb\nc\n")
    assert cron.get_line_content(str(f), 2) == "b"
    assert cron.get_line_content(str(f), 99) == ""
    assert cron.get_line_content("/nope", 1) == ""


def test_clean_line_for_output():
    assert cron.clean_line_for_output("a\t\tb   c") == "a b c"


def test_check_dangerous_commands():
    assert cron.check_dangerous_commands("rm -rf /") != []
    assert cron.check_dangerous_commands(":(){ :|: & };:") != []
    assert cron.check_dangerous_commands("mkfs.ext4 /dev/sda") != []
    assert cron.check_dangerous_commands("dd if=/dev/zero of=/dev/sda") != []
    assert cron.check_dangerous_commands("/usr/bin/true") == []


@pytest.mark.parametrize("value,field,min_val,max_val,ok", [
    ("*", "minutes", 0, 59, True),
    ("0", "minutes", 0, 59, True),
    ("59", "minutes", 0, 59, True),
    ("60", "minutes", 0, 59, False),
    ("0-30", "minutes", 0, 59, True),
    ("30-10", "minutes", 0, 59, False),
    ("*/5", "minutes", 0, 59, True),
    ("*/0", "minutes", 0, 59, False),
    ("*/x", "minutes", 0, 59, False),
    ("1,2,3", "minutes", 0, 59, True),
    ("1,1,2", "minutes", 0, 59, False),
    ("1,,2", "minutes", 0, 59, False),
    ("99-200", "minutes", 0, 59, False),
])
def test_validate_time_field_logic(value, field, min_val, max_val, ok):
    errors = cron.validate_time_field_logic(value, field, min_val, max_val)
    if ok:
        assert errors == []
    else:
        assert errors


def test_check_time_field_invalid_format():
    errors = cron.check_time_field("garbage", "minutes", cron.MINUTE_PATTERN, 0, 59)
    assert errors


def test_check_user_valid_and_invalid():
    err, _ = cron.check_user("")
    assert err
    err, _ = cron.check_user("user with space")
    assert err
    err, warnings = cron.check_user("root")
    assert err == []


def test_check_user_unknown(monkeypatch):
    monkeypatch.setattr(cron, "check_user_exists", lambda u: False)
    err, warnings = cron.check_user("alice")
    assert warnings


def test_check_user_exists_root():
    assert cron.check_user_exists("root") is True


def test_check_user_exists_subprocess(monkeypatch):
    def fake_run(cmd, **_):
        if cmd[0] == "id":
            return mock.Mock(returncode=0, stdout="", stderr="")
        return mock.Mock(returncode=1, stdout="", stderr="")
    monkeypatch.setattr("subprocess.run", fake_run)
    assert cron.check_user_exists("anyone") is True


def test_check_user_exists_subprocess_failure(monkeypatch):
    monkeypatch.setattr("subprocess.run", mock.Mock(side_effect=FileNotFoundError))
    assert cron.check_user_exists("x") is True


def test_check_command_empty_and_dangerous():
    assert cron.check_command("") == ["missing command"]
    assert cron.check_command("/usr/bin/true") == []
    assert cron.check_command("rm -rf /") != []


def test_check_special_valid_user():
    assert cron.check_special("@reboot", ["@reboot", "/usr/bin/true"], is_system_crontab=False) == []


def test_check_special_user_missing_command():
    errors = cron.check_special("@daily", ["@daily"], is_system_crontab=False)
    assert errors


def test_check_special_system_valid():
    assert cron.check_special("@daily", ["@daily", "root", "/usr/bin/true"], is_system_crontab=True) == []


def test_check_special_system_missing_user():
    errors = cron.check_special("@daily", ["@daily", "root"], is_system_crontab=True)
    assert errors


def test_check_special_invalid_keyword():
    errors = cron.check_special("@bogus", ["@bogus", "x"], is_system_crontab=False)
    assert errors


def test_check_line_env_var():
    errors, warnings = cron.check_line("PATH=/usr/bin", 1, "f")
    assert errors == [] and warnings == []


def test_check_line_special():
    errors, _ = cron.check_line("@daily /usr/bin/true", 1, "f", is_system_crontab=False)
    assert errors == []


def test_check_line_special_too_few():
    errors, _ = cron.check_line("@daily", 1, "f")
    assert errors


def test_check_line_user_short():
    errors, _ = cron.check_line("0 5 * *", 1, "f")
    assert errors


def test_check_line_user_valid():
    errors, _ = cron.check_line("0 5 * * * /usr/bin/true", 1, "f")
    assert errors == []


def test_check_line_system_valid():
    errors, _ = cron.check_line("0 5 * * * root /usr/bin/true", 1, "f", is_system_crontab=True)
    assert errors == []


def test_check_line_bad_minute():
    errors, _ = cron.check_line("99 5 * * * /usr/bin/true", 1, "f")
    assert any("minute" in e for e in errors)


def test_check_file(tmp_path):
    f = tmp_path / "c"
    f.write_text("# comment\n\n0 5 * * * /usr/bin/true\n99 * * * * /bin/false\n")
    rows, errors, warnings = cron.check_file(str(f), is_system_crontab=False)
    assert rows == 2
    assert any("minute" in e for e in errors)


def test_check_file_with_continuation(tmp_path):
    f = tmp_path / "c"
    f.write_text("0 5 * * * /usr/bin/echo line one \\\n line two\n")
    rows, errors, _ = cron.check_file(str(f), is_system_crontab=False)
    assert rows == 1


def test_check_file_unreadable(monkeypatch):
    def boom(*a, **kw):
        raise OSError("cannot read")
    monkeypatch.setattr("builtins.open", boom)
    rows, errors, _ = cron.check_file("/nonexistent/zzz")
    assert rows == 0
    assert errors


def test_get_crontab(monkeypatch):
    def fake_run(cmd, **_):
        return mock.Mock(returncode=0, stdout="0 5 * * * /bin/true\n", stderr="")
    monkeypatch.setattr("subprocess.run", fake_run)
    assert cron.get_crontab("alice") is not None


def test_get_crontab_none(monkeypatch):
    def fake_run(cmd, **_):
        return mock.Mock(returncode=1, stdout="", stderr="")
    monkeypatch.setattr("subprocess.run", fake_run)
    assert cron.get_crontab("noone") is None


def test_get_crontab_exception(monkeypatch):
    monkeypatch.setattr("subprocess.run", mock.Mock(side_effect=RuntimeError))
    assert cron.get_crontab("noone") is None


def test_find_user_crontab_in_spool(monkeypatch):
    real_exists = os.path.exists
    monkeypatch.setattr(cron.os.path, "exists",
                        lambda p: p == "/var/spool/cron/crontabs/alice" or real_exists(p))
    # cron.find_user_crontab calls os.path.exists on the candidate paths.
    # The patched version says the spool path exists, so it short-circuits.
    result = cron.find_user_crontab("alice")
    assert result == "/var/spool/cron/crontabs/alice"


def test_find_user_crontab_via_crontab_cmd(monkeypatch):
    real_exists = os.path.exists

    def fake_exists(p):
        # Only the well-known spool locations are "missing"; everything else
        # (such as the tempfile we'll create) keeps real behavior.
        if p.startswith("/var/spool/cron/"):
            return False
        return real_exists(p)

    monkeypatch.setattr(cron.os.path, "exists", fake_exists)
    monkeypatch.setattr(cron, "get_crontab", lambda u: "0 5 * * * /bin/true\n")
    path = cron.find_user_crontab("alice")
    assert path is not None
    assert real_exists(path)
    os.unlink(path)


def test_find_user_crontab_not_found(monkeypatch):
    monkeypatch.setattr(cron.os.path, "exists", lambda _: False)
    monkeypatch.setattr(cron, "get_crontab", lambda u: None)
    assert cron.find_user_crontab("nope") is None


def test_discover_default_targets(monkeypatch, tmp_path):
    crontab = tmp_path / "crontab"
    crontab.write_text("")
    cron_d = tmp_path / "cron.d"
    cron_d.mkdir()
    (cron_d / "valid").write_text("")
    (cron_d / "bad.name").write_text("")  # filtered

    real_exists = os.path.exists
    real_isdir = os.path.isdir
    real_isfile = os.path.isfile
    real_listdir = os.listdir

    def fake_exists(p):
        if p == "/etc/crontab":
            return True
        return real_exists(p)
    def fake_isdir(p):
        if p == "/etc/cron.d":
            return True
        if p == "/var/spool/cron/crontabs":
            return False
        return real_isdir(p)
    def fake_listdir(p):
        if p == "/etc/cron.d":
            return ["valid", "bad.name"]
        return real_listdir(p)
    def fake_isfile(p):
        if p.startswith("/etc/"):
            return True
        return real_isfile(p)
    def fake_join(a, b):
        return f"{a}/{b}"

    monkeypatch.setattr(cron.os.path, "exists", fake_exists)
    monkeypatch.setattr(cron.os.path, "isdir", fake_isdir)
    monkeypatch.setattr(cron.os.path, "isfile", fake_isfile)
    monkeypatch.setattr(cron.os.path, "join", fake_join)
    monkeypatch.setattr(cron.os, "listdir", fake_listdir)

    targets = cron.discover_default_targets()
    paths = {p for p, _ in targets}
    assert "/etc/crontab" in paths
    assert "/etc/cron.d/valid" in paths
    assert "/etc/cron.d/bad.name" not in paths
