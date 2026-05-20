#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helpers for writing Python plugins for wtftools.

A wtftools plugin is any executable file in `/etc/wtf/checks.d/` (or one of
the other discovery dirs — see `wtf plugins`). The plugin loader speaks two
contracts: exit codes and JSON. This module makes the JSON path painless for
Python authors:

    #!/usr/bin/env python3
    # /etc/wtf/checks.d/my-check
    from wtftools.plugin_sdk import ok, warn, fail, skip
    import urllib.request

    try:
        with urllib.request.urlopen("http://internal-api/health", timeout=2) as r:
            if r.status != 200:
                fail(f"HTTP {r.status}")
        ok("internal-api healthy")
    except Exception as exc:
        fail(str(exc))

Each helper writes a structured JSON line to stdout and exits with the right
code, so the plugin loader picks it up unambiguously. No need to remember
which exit code maps to which status.

Functions:
    ok(message, detail=None)       0
    warn(message, detail=None)     1
    fail(message, detail=None)     2
    skip(message, detail=None)     77

`detail` is an optional list of strings rendered under the result in
`wtf audit -v`.

Helpers are intentionally *terminal* — they call `sys.exit`. If you need to
emit a result without exiting (e.g. running multiple checks in one script),
use `result(...)` which only writes the JSON.
"""

import json
import sys
from typing import List, Mapping, Optional

__all__ = ["ok", "warn", "fail", "skip", "result"]

EXIT_OK = 0
EXIT_WARN = 1
EXIT_FAIL = 2
EXIT_SKIP = 77

_EXIT_CODES: Mapping[str, int] = {
    "ok": EXIT_OK,
    "warn": EXIT_WARN,
    "fail": EXIT_FAIL,
    "skip": EXIT_SKIP,
}


def result(status: str, message: str = "",
           detail: Optional[List[str]] = None) -> None:
    """Emit a plugin result without exiting. Returns None.

    `status` must be one of: ok, warn, fail, skip. Anything else is treated
    as skip — the plugin loader does the same.
    """
    if status not in _EXIT_CODES:
        status = "skip"
    payload: dict = {"status": status, "message": message}
    if detail:
        payload["detail"] = [str(d) for d in detail]
    print(json.dumps(payload))
    sys.stdout.flush()


def ok(message: str = "", detail: Optional[List[str]] = None) -> None:
    result("ok", message, detail)
    sys.exit(EXIT_OK)


def warn(message: str = "", detail: Optional[List[str]] = None) -> None:
    result("warn", message, detail)
    sys.exit(EXIT_WARN)


def fail(message: str = "", detail: Optional[List[str]] = None) -> None:
    result("fail", message, detail)
    sys.exit(EXIT_FAIL)


def skip(message: str = "", detail: Optional[List[str]] = None) -> None:
    result("skip", message, detail)
    sys.exit(EXIT_SKIP)
