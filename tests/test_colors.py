#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for wtftools.colors — ANSI helpers."""

from unittest import mock

from wtftools import colors


def test_init_colors_force_no_color():
    colors.init_colors(force_no_color=True)
    assert colors.colored("x", colors.FG_GREEN) == "x"


def test_init_colors_no_color_env(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    colors.init_colors(force_no_color=False)
    assert colors.colored("x", colors.FG_GREEN) == "x"


def test_init_colors_non_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    with mock.patch("sys.stdout") as stdout:
        stdout.isatty.return_value = False
        colors.init_colors(force_no_color=False)
        assert colors.colored("x", colors.FG_GREEN) == "x"


def test_init_colors_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    with mock.patch("sys.stdout") as stdout:
        stdout.isatty.return_value = True
        colors.init_colors(force_no_color=False)
        assert "\033[32m" in colors.colored("x", colors.FG_GREEN)


def test_color_wrappers_disabled():
    colors.init_colors(force_no_color=True)
    assert colors.green("a") == "a"
    assert colors.red("a", bold=True) == "a"
    assert colors.yellow("a") == "a"
    assert colors.cyan("a") == "a"
    assert colors.blue("a") == "a"
    assert colors.dim("a") == "a"
    assert colors.bold("a") == "a"


def test_color_wrappers_enabled(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    with mock.patch("sys.stdout") as stdout:
        stdout.isatty.return_value = True
        colors.init_colors(force_no_color=False)
    assert "\033[32m" in colors.green("a")
    assert "\033[31m" in colors.red("a")
    assert "\033[33m" in colors.yellow("a")
    assert "\033[36m" in colors.cyan("a")
    assert "\033[34m" in colors.blue("a")
    assert "\033[2m" in colors.dim("a")
    assert "\033[1m" in colors.bold("a")
    assert "\033[1m" in colors.red("a", bold=True)
    colors.init_colors(force_no_color=True)


def test_status_marker_each_status():
    assert "OK" in colors.status_marker("ok")
    assert "WARN" in colors.status_marker("warn")
    assert "FAIL" in colors.status_marker("fail")
    assert "FAIL" in colors.status_marker("error")
    assert "FAIL" in colors.status_marker("critical")
    assert "INFO" in colors.status_marker("info")
    assert "SKIP" in colors.status_marker("skip")
    assert colors.status_marker("unknown") == "[UNKNOWN]"


def test_section_with_width():
    out = colors.section("HELLO", width=20)
    assert "HELLO" in out


def test_section_default_width():
    import os as _os

    with mock.patch("wtftools.colors.shutil.get_terminal_size", return_value=_os.terminal_size((80, 24))):
        out = colors.section("HELLO")
    assert "HELLO" in out


def test_section_oversized_title():
    # title longer than width — still contains text
    out = colors.section("A very long title that exceeds width", width=10)
    assert "very long title" in out
