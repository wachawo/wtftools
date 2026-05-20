#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WTFTools — one command to see what is going on with your server.

This module exposes a small **stable public API** for callers that want to
embed wtftools logic instead of running the CLI:

    >>> from wtftools import run_audit, CheckResult
    >>> results = run_audit()
    >>> failed = [r for r in results if r.status == "fail"]

That surface is intentionally narrow — everything else (config helpers,
sysinfo, plugins, daemon) lives in submodules and may change between
versions without a notice. Import the submodules directly if you need them.
"""

__version__ = "0.0.0"
__description__ = "One command to summarize what is happening on your Linux server right now."
__url__ = "https://github.com/wachawo/wtftools"
__author__ = "Aleksandr Pimenov"
__license__ = "MIT"

# Stable embedding-friendly surface. Submodules are imported lazily so the
# `wtftools` module itself stays cheap to import (e.g. for `--version`).
__all__ = [
    "__version__",
    "__description__",
    "__url__",
    "CheckResult",
    "run_audit",
    "summarize",
    "list_check_names",
]


def __getattr__(name):
    """Lazy re-export of the audit module's stable surface."""
    if name in ("CheckResult", "run_audit", "summarize", "list_check_names"):
        from wtftools import audit
        return getattr(audit, name)
    raise AttributeError(f"module 'wtftools' has no attribute {name!r}")
