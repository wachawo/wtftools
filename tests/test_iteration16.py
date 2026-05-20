#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for iteration 16: Python plugin SDK + PLUGIN_GUIDE."""

import io
import json
import os
import subprocess
from contextlib import redirect_stdout

import pytest

from wtftools import plugin_sdk

# ---------- result() — non-terminating ----------

def test_result_ok():
    buf = io.StringIO()
    with redirect_stdout(buf):
        plugin_sdk.result("ok", "fine")
    data = json.loads(buf.getvalue())
    assert data["status"] == "ok"
    assert data["message"] == "fine"
    assert "detail" not in data


def test_result_with_detail():
    buf = io.StringIO()
    with redirect_stdout(buf):
        plugin_sdk.result("warn", "soft", detail=["d1", "d2"])
    data = json.loads(buf.getvalue())
    assert data["status"] == "warn"
    assert data["detail"] == ["d1", "d2"]


def test_result_unknown_status_becomes_skip():
    buf = io.StringIO()
    with redirect_stdout(buf):
        plugin_sdk.result("garbage", "x")
    data = json.loads(buf.getvalue())
    assert data["status"] == "skip"


def test_result_coerces_detail_to_strings():
    """Non-string detail items still serialize correctly."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        plugin_sdk.result("ok", "x", detail=[1, 2.5, "three"])
    data = json.loads(buf.getvalue())
    assert data["detail"] == ["1", "2.5", "three"]


# ---------- ok/warn/fail/skip — terminating ----------

@pytest.mark.parametrize("fn, status, code", [
    (plugin_sdk.ok, "ok", plugin_sdk.EXIT_OK),
    (plugin_sdk.warn, "warn", plugin_sdk.EXIT_WARN),
    (plugin_sdk.fail, "fail", plugin_sdk.EXIT_FAIL),
    (plugin_sdk.skip, "skip", plugin_sdk.EXIT_SKIP),
])
def test_terminating_helpers(fn, status, code):
    buf = io.StringIO()
    with redirect_stdout(buf), pytest.raises(SystemExit) as exc:
        fn("hello", detail=["a", "b"])
    assert exc.value.code == code
    data = json.loads(buf.getvalue())
    assert data["status"] == status
    assert data["message"] == "hello"
    assert data["detail"] == ["a", "b"]


def test_helpers_no_message():
    buf = io.StringIO()
    with redirect_stdout(buf), pytest.raises(SystemExit):
        plugin_sdk.ok()
    data = json.loads(buf.getvalue())
    assert data["status"] == "ok"
    assert data["message"] == ""


def test_helpers_no_detail():
    buf = io.StringIO()
    with redirect_stdout(buf), pytest.raises(SystemExit):
        plugin_sdk.warn("only message")
    data = json.loads(buf.getvalue())
    assert "detail" not in data


# ---------- end-to-end via subprocess (real plugin script) ----------

def _write_plugin(tmp_path, code: str) -> str:
    """Write a Python plugin to tmp_path/plugin.py, chmod +x, return path."""
    path = tmp_path / "plugin.py"
    path.write_text("#!/usr/bin/env python3\n" + code)
    path.chmod(0o755)
    return str(path)


def test_plugin_subprocess_ok(tmp_path):
    path = _write_plugin(tmp_path, (
        "import sys\n"
        f"sys.path.insert(0, {repr(os.path.dirname(os.path.dirname(os.path.abspath(plugin_sdk.__file__))))})\n"
        "from wtftools.plugin_sdk import ok\n"
        "ok('all good')\n"
    ))
    result = subprocess.run([path], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0
    data = json.loads(result.stdout.strip())
    assert data["status"] == "ok"
    assert data["message"] == "all good"


def test_plugin_subprocess_fail(tmp_path):
    path = _write_plugin(tmp_path, (
        "import sys\n"
        f"sys.path.insert(0, {repr(os.path.dirname(os.path.dirname(os.path.abspath(plugin_sdk.__file__))))})\n"
        "from wtftools.plugin_sdk import fail\n"
        "fail('broken!', detail=['line1', 'line2'])\n"
    ))
    result = subprocess.run([path], capture_output=True, text=True, timeout=5)
    assert result.returncode == 2
    data = json.loads(result.stdout.strip())
    assert data["status"] == "fail"
    assert data["detail"] == ["line1", "line2"]


def test_plugin_subprocess_integration_with_loader(tmp_path):
    """Spin up the plugin loader against a real Python plugin built with the SDK."""
    from wtftools.checks import plugins
    plugin_path = _write_plugin(tmp_path, (
        "import sys\n"
        f"sys.path.insert(0, {repr(os.path.dirname(os.path.dirname(os.path.abspath(plugin_sdk.__file__))))})\n"
        "from wtftools.plugin_sdk import warn\n"
        "warn('soft warning', detail=['useful context'])\n"
    ))
    pr = plugins.run_plugin(plugin_path)
    assert pr.status == "warn"
    assert pr.message == "soft warning"
    assert "useful context" in pr.detail


# NB: docs/PLUGIN_GUIDE.md and examples/plugins/ were removed from the
# repo — short inline guidance lives in README.md «## Plugins» now.
