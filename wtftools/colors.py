#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ANSI color helpers for wtftools terminal output."""

import os
import shutil
import sys
from typing import Optional

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

FG_BLACK = "\033[30m"
FG_RED = "\033[31m"
FG_GREEN = "\033[32m"
FG_YELLOW = "\033[33m"
FG_BLUE = "\033[34m"
FG_MAGENTA = "\033[35m"
FG_CYAN = "\033[36m"
FG_WHITE = "\033[37m"
FG_BRIGHT_BLACK = "\033[90m"

_color_enabled = True


def init_colors(force_no_color: bool = False) -> None:
    """Decide whether colored output should be enabled."""
    global _color_enabled
    if force_no_color:
        _color_enabled = False
        return
    if os.getenv("NO_COLOR"):
        _color_enabled = False
        return
    if not sys.stdout.isatty():
        _color_enabled = False
        return
    _color_enabled = True


def colored(text: str, color: str, bold: bool = False) -> str:
    """Wrap text in ANSI color codes when colors are enabled."""
    if not _color_enabled:
        return text
    prefix = (BOLD if bold else "") + color
    return f"{prefix}{text}{RESET}"


def green(text: str, bold: bool = False) -> str:
    return colored(text, FG_GREEN, bold=bold)


def red(text: str, bold: bool = False) -> str:
    return colored(text, FG_RED, bold=bold)


def yellow(text: str, bold: bool = False) -> str:
    return colored(text, FG_YELLOW, bold=bold)


def cyan(text: str, bold: bool = False) -> str:
    return colored(text, FG_CYAN, bold=bold)


def blue(text: str, bold: bool = False) -> str:
    return colored(text, FG_BLUE, bold=bold)


def dim(text: str) -> str:
    if not _color_enabled:
        return text
    return f"{DIM}{text}{RESET}"


def bold(text: str) -> str:
    if not _color_enabled:
        return text
    return f"{BOLD}{text}{RESET}"


def status_marker(status: str) -> str:
    """Render a status marker like [OK] / [WARN] / [FAIL]."""
    s = status.upper()
    if s == "OK":
        return green("[ OK ]", bold=True)
    if s in ("WARN", "WARNING"):
        return yellow("[WARN]", bold=True)
    if s in ("FAIL", "ERROR", "CRIT", "CRITICAL"):
        return red("[FAIL]", bold=True)
    if s in ("INFO", "SKIP", "N/A"):
        return cyan(f"[{s:^4}]")
    return f"[{s}]"


def section(title: str, width: Optional[int] = None) -> str:
    """Render a section header."""
    if width is None:
        try:
            width = shutil.get_terminal_size((80, 24)).columns
        except OSError:
            width = 80
    title = f" {title.strip()} "
    if len(title) >= width:
        return bold(title)
    side = (width - len(title)) // 2
    bar = "─" * side
    line = f"{bar}{title}{bar}"
    if len(line) < width:
        line += "─"
    return cyan(line, bold=True)
