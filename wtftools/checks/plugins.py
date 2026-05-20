#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plugin system: load and run user-supplied check scripts.

Discovery directories (first match wins for same name):
    /etc/wtf/checks.d/
    /etc/wtftools/checks.d/
    $XDG_CONFIG_HOME/wtftools/checks.d/  (or ~/.config/wtftools/checks.d/)

Each plugin is an executable file. Exit-code convention:
    0   → ok
    1   → warn
    2   → fail
    77  → skip (intentionally inapplicable on this host)
    *   → fail

stdout becomes the result message. Plugins may also emit a single-line JSON
object on stdout: `{"status": "warn", "message": "...", "detail": [...]}`.
"""

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_WARN = 1
EXIT_FAIL = 2
EXIT_SKIP = 77

PLUGIN_TIMEOUT_SECONDS = 15

DEFAULT_PLUGIN_DIRS = (
    "/etc/wtf/checks.d",
    "/etc/wtftools/checks.d",
    os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
        "wtftools", "checks.d",
    ),
)


@dataclass
class PluginResult:
    """Outcome of running a single plugin (consumed by audit.py)."""
    name: str
    status: str
    message: str
    detail: List[str]


def discover_plugins(dirs: Optional[List[str]] = None) -> List[str]:
    """Return executable plugin paths in discovery order, deduped by basename."""
    if dirs is None:
        dirs = list(DEFAULT_PLUGIN_DIRS)
    found: List[str] = []
    seen: set = set()
    for d in dirs:
        if not os.path.isdir(d):
            continue
        try:
            entries = sorted(os.listdir(d))
        except OSError:
            continue
        for name in entries:
            if name.startswith(".") or name.endswith("~"):
                continue
            path = os.path.join(d, name)
            if not os.path.isfile(path):
                continue
            if not os.access(path, os.X_OK):
                continue
            key = name.split(".", 1)[0]
            if key in seen:
                continue
            seen.add(key)
            found.append(path)
    return found


def _plugin_name(path: str) -> str:
    return os.path.basename(path).split(".", 1)[0]


def run_plugin(path: str, timeout: int = PLUGIN_TIMEOUT_SECONDS) -> PluginResult:
    """Execute a single plugin script and convert its result into a PluginResult."""
    name = _plugin_name(path)
    try:
        proc = subprocess.run([path], capture_output=True, text=True,
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return PluginResult(name, "fail", f"plugin timed out after {timeout}s", [])
    except PermissionError:
        return PluginResult(name, "skip", "plugin is not executable", [])
    except Exception as exc:
        logger.warning(f"plugin {name} crashed: {type(exc).__name__}: {exc}")
        return PluginResult(name, "fail", f"{type(exc).__name__}: {exc}", [])

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()

    # JSON contract takes precedence over exit-code contract.
    if stdout.startswith("{"):
        try:
            data = json.loads(stdout)
            status = str(data.get("status", "skip")).lower()
            if status not in ("ok", "warn", "fail", "skip"):
                status = "skip"
            message = str(data.get("message", "") or "")
            detail_raw = data.get("detail", [])
            detail = [str(d) for d in detail_raw] if isinstance(detail_raw, list) else [str(detail_raw)]
            return PluginResult(name, status, message, detail)
        except (json.JSONDecodeError, ValueError):
            pass  # fall through to exit-code contract

    status_map = {EXIT_OK: "ok", EXIT_WARN: "warn", EXIT_FAIL: "fail", EXIT_SKIP: "skip"}
    status = status_map.get(proc.returncode, "fail")
    message = stdout or (f"exit code {proc.returncode}" if status != "ok" else "ok")
    detail: List[str] = []
    if stderr and status in ("warn", "fail"):
        detail = stderr.splitlines()[:5]
    return PluginResult(name, status, message, detail)


def run_all_plugins() -> List[PluginResult]:
    return [run_plugin(p) for p in discover_plugins()]
