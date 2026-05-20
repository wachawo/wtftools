#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for wtftools.checks.plugins — plugin discovery and execution."""

import os
import stat
from unittest import mock

from wtftools.checks import plugins


def _make_plugin(path, body, executable=True):
    path.write_text(body)
    if executable:
        os.chmod(str(path), os.stat(str(path)).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_discover_empty(tmp_path):
    assert plugins.discover_plugins([str(tmp_path)]) == []


def test_discover_finds_executable(tmp_path):
    p = tmp_path / "myplugin.sh"
    _make_plugin(p, "#!/bin/sh\nexit 0\n")
    found = plugins.discover_plugins([str(tmp_path)])
    assert found == [str(p)]


def test_discover_skips_non_executable(tmp_path):
    p = tmp_path / "noexec.sh"
    p.write_text("#!/bin/sh\nexit 0\n")
    # not chmod'd executable
    assert plugins.discover_plugins([str(tmp_path)]) == []


def test_discover_skips_hidden_and_backup(tmp_path):
    _make_plugin(tmp_path / ".hidden", "#!/bin/sh\nexit 0\n")
    _make_plugin(tmp_path / "backup~", "#!/bin/sh\nexit 0\n")
    assert plugins.discover_plugins([str(tmp_path)]) == []


def test_discover_dedup_across_dirs(tmp_path):
    d1 = tmp_path / "a"
    d2 = tmp_path / "b"
    d1.mkdir()
    d2.mkdir()
    _make_plugin(d1 / "check.sh", "#!/bin/sh\nexit 0\n")
    _make_plugin(d2 / "check.sh", "#!/bin/sh\nexit 0\n")
    found = plugins.discover_plugins([str(d1), str(d2)])
    assert len(found) == 1
    assert found[0].startswith(str(d1))  # first dir wins


def test_discover_skips_missing_dir():
    assert plugins.discover_plugins(["/nonexistent/path/zzz"]) == []


def test_discover_default_dirs(monkeypatch):
    # smoke: should not crash on default dirs even when absent
    monkeypatch.setattr(plugins, "DEFAULT_PLUGIN_DIRS", ("/tmp/nonexistent_xxxx",))
    assert plugins.discover_plugins() == []


def test_run_plugin_ok_exit_code(tmp_path):
    p = tmp_path / "ok.sh"
    _make_plugin(p, '#!/bin/sh\necho "all good"\nexit 0\n')
    result = plugins.run_plugin(str(p))
    assert result.status == "ok"
    assert "all good" in result.message
    assert result.name == "ok"


def test_run_plugin_warn_exit_code(tmp_path):
    p = tmp_path / "w.sh"
    _make_plugin(p, '#!/bin/sh\necho "watch it"\nexit 1\n')
    result = plugins.run_plugin(str(p))
    assert result.status == "warn"
    assert "watch it" in result.message


def test_run_plugin_fail_exit_code(tmp_path):
    p = tmp_path / "f.sh"
    _make_plugin(p, '#!/bin/sh\necho "broken"\nexit 2\n')
    result = plugins.run_plugin(str(p))
    assert result.status == "fail"


def test_run_plugin_skip_exit_code(tmp_path):
    p = tmp_path / "s.sh"
    _make_plugin(p, '#!/bin/sh\necho "n/a"\nexit 77\n')
    result = plugins.run_plugin(str(p))
    assert result.status == "skip"


def test_run_plugin_unknown_exit_is_fail(tmp_path):
    p = tmp_path / "e.sh"
    _make_plugin(p, "#!/bin/sh\nexit 42\n")
    result = plugins.run_plugin(str(p))
    assert result.status == "fail"
    assert "42" in result.message


def test_run_plugin_json_contract(tmp_path):
    body = '#!/bin/sh\necho \'{"status":"warn","message":"hi","detail":["a","b"]}\'\nexit 0\n'
    p = tmp_path / "j.sh"
    _make_plugin(p, body)
    result = plugins.run_plugin(str(p))
    assert result.status == "warn"
    assert result.message == "hi"
    assert result.detail == ["a", "b"]


def test_run_plugin_invalid_json_falls_back_to_exit_code(tmp_path):
    body = '#!/bin/sh\necho \'{ broken json\'\nexit 2\n'
    p = tmp_path / "j.sh"
    _make_plugin(p, body)
    result = plugins.run_plugin(str(p))
    assert result.status == "fail"


def test_run_plugin_json_unknown_status_skipped(tmp_path):
    body = '#!/bin/sh\necho \'{"status":"haha"}\'\nexit 0\n'
    p = tmp_path / "j.sh"
    _make_plugin(p, body)
    result = plugins.run_plugin(str(p))
    assert result.status == "skip"


def test_run_plugin_json_non_list_detail(tmp_path):
    body = '#!/bin/sh\necho \'{"status":"ok","detail":"single"}\'\nexit 0\n'
    p = tmp_path / "j.sh"
    _make_plugin(p, body)
    result = plugins.run_plugin(str(p))
    assert result.detail == ["single"]


def test_run_plugin_timeout(tmp_path):
    p = tmp_path / "slow.sh"
    _make_plugin(p, "#!/bin/sh\nsleep 5\nexit 0\n")
    result = plugins.run_plugin(str(p), timeout=1)
    assert result.status == "fail"
    assert "timed out" in result.message


def test_run_plugin_stderr_captured_on_fail(tmp_path):
    p = tmp_path / "noisy.sh"
    _make_plugin(p, "#!/bin/sh\necho stderr-line >&2\nexit 2\n")
    result = plugins.run_plugin(str(p))
    assert result.status == "fail"
    assert any("stderr-line" in d for d in result.detail)


def test_run_plugin_handles_subprocess_exception(tmp_path):
    with mock.patch("subprocess.run", side_effect=RuntimeError("boom")):
        result = plugins.run_plugin("/some/path/x.sh")
    assert result.status == "fail"
    assert "boom" in result.message


def test_run_plugin_handles_permission_error(monkeypatch):
    monkeypatch.setattr("subprocess.run", mock.Mock(side_effect=PermissionError))
    result = plugins.run_plugin("/some/path/x.sh")
    assert result.status == "skip"
    assert "executable" in result.message


def test_run_all_plugins(tmp_path, monkeypatch):
    p = tmp_path / "ok.sh"
    _make_plugin(p, "#!/bin/sh\necho ok\nexit 0\n")
    monkeypatch.setattr(plugins, "DEFAULT_PLUGIN_DIRS", (str(tmp_path),))
    results = plugins.run_all_plugins()
    assert len(results) == 1
    assert results[0].status == "ok"
