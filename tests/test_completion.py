#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `wtf completion` and the shell-completion source of truth."""

import io
import os
from contextlib import redirect_stdout

from wtftools import completion, main


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


def test_bash_script_shape():
    script = completion.bash()
    assert "_wtf_complete()" in script
    assert "complete -F _wtf_complete wtf" in script
    assert "complete -F _wtf_complete wtftools" in script


def test_zsh_wraps_bash_with_bashcompinit():
    script = completion.zsh()
    assert "bashcompinit" in script
    assert "_wtf_complete()" in script  # bash body still present


def test_repo_completion_file_matches_module():
    # completions/wtf is a generated mirror — guard against drift.
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(repo_root, "completions", "wtf")
    with open(path, encoding="utf-8") as f:
        assert f.read() == completion.bash()


def test_cmd_completion_bash():
    rc, out = _capture(["completion", "bash"])
    assert rc == 0
    assert "complete -F _wtf_complete wtf" in out


def test_cmd_completion_zsh():
    rc, out = _capture(["completion", "zsh"])
    assert rc == 0
    assert "bashcompinit" in out


def test_cmd_completion_instructions():
    rc, out = _capture(["completion"])
    assert rc == 0
    assert "eval" in out
    assert "bash" in out and "zsh" in out
