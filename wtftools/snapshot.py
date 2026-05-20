#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Snapshot + diff for wtftools — `wtfd-lite`.

`wtf audit --save` writes the current run to a JSON file in
`$XDG_CACHE_HOME/wtftools/snapshots/` (or `/var/lib/wtftools/snapshots/` when
running as root). `wtf history` and `wtf diff` consume them.

Snapshots are bounded — the oldest ones rotate out so the directory does not
grow forever.
"""

import json
import logging
import os
import time
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from wtftools.audit import CheckResult

logger = logging.getLogger(__name__)

DEFAULT_KEEP = 48

# Snapshot directory selection:
#   1. WTFTOOLS_SNAPSHOT_DIR env override (test seam + power-user knob)
#   2. /var/lib/wtftools/snapshots if running as root (system-wide history)
#   3. $XDG_CACHE_HOME/wtftools/snapshots else ~/.cache/wtftools/snapshots


def default_snapshot_dir() -> str:
    env_override = os.environ.get("WTFTOOLS_SNAPSHOT_DIR")
    if env_override:
        return env_override
    try:
        if os.geteuid() == 0:
            return "/var/lib/wtftools/snapshots"
    except (AttributeError, OSError):
        pass
    base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    return os.path.join(base, "wtftools", "snapshots")


def ensure_dir(path: str) -> bool:
    """Create the snapshot dir if missing. Returns True on success."""
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError as exc:
        logger.warning(f"cannot create snapshot dir {path}: {exc}")
        return False


def save_snapshot(results: List[CheckResult], host: str,
                  directory: Optional[str] = None) -> Optional[str]:
    """Persist a snapshot. Returns the path written, or None on failure."""
    directory = directory or default_snapshot_dir()
    if not ensure_dir(directory):
        return None
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(directory, f"{ts}.json")
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "epoch": int(time.time()),
        "host": host,
        "results": [asdict(r) for r in results],
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
    except OSError as exc:
        logger.warning(f"cannot write snapshot {path}: {exc}")
        return None
    _rotate(directory)
    return path


def _rotate(directory: str, keep: int = DEFAULT_KEEP) -> None:
    """Delete the oldest snapshots above `keep`."""
    try:
        files = sorted(
            (f for f in os.listdir(directory) if f.endswith(".json")),
        )
    except OSError:
        return
    if len(files) <= keep:
        return
    for old in files[: len(files) - keep]:
        try:
            os.unlink(os.path.join(directory, old))
        except OSError:
            pass


def list_snapshots(directory: Optional[str] = None) -> List[str]:
    """Return snapshot paths sorted oldest → newest."""
    directory = directory or default_snapshot_dir()
    if not os.path.isdir(directory):
        return []
    try:
        return sorted(
            os.path.join(directory, f)
            for f in os.listdir(directory)
            if f.endswith(".json")
        )
    except OSError:
        return []


def load_snapshot(path: str) -> Optional[Dict[str, Any]]:
    """Load a snapshot file. Returns None on parse error."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"cannot load snapshot {path}: {type(exc).__name__}: {exc}\n"
                       f"{traceback.format_exc()}")
        return None


def latest_snapshot(directory: Optional[str] = None) -> Optional[Dict[str, Any]]:
    paths = list_snapshots(directory)
    if not paths:
        return None
    return load_snapshot(paths[-1])


def diff_snapshots(old: Dict[str, Any], new_results: List[CheckResult]) -> List[Dict[str, Any]]:
    """Compare an old snapshot to current results.

    Returns a list of change events, each:
        {"name": str, "kind": "regression"|"recovery"|"worsened"|"improved"
                                |"new"|"removed"|"unchanged",
         "old_status": Optional[str], "new_status": Optional[str],
         "old_message": Optional[str], "new_message": Optional[str]}
    Only non-unchanged events are returned.
    """
    order = ["ok", "skip", "warn", "fail"]

    def severity(s: str) -> int:
        try:
            return order.index(s)
        except ValueError:
            return 1  # unknown → treat as skip-ish

    old_map: Dict[str, Dict[str, str]] = {}
    for r in old.get("results", []) or []:
        old_map[r["name"]] = {"status": r["status"], "message": r.get("message", "")}

    new_map: Dict[str, Dict[str, str]] = {}
    for r in new_results:
        new_map[r.name] = {"status": r.status, "message": r.message}

    events: List[Dict[str, Any]] = []
    for name, new in new_map.items():
        if name not in old_map:
            events.append({
                "name": name, "kind": "new",
                "old_status": None, "new_status": new["status"],
                "old_message": None, "new_message": new["message"],
            })
            continue
        old = old_map[name]
        if old["status"] == new["status"]:
            # Status unchanged. Surface only if message *meaningfully* changed
            # — we skip these in diff to avoid noise from time-varying numbers.
            continue
        old_sev = severity(old["status"])
        new_sev = severity(new["status"])
        if new_sev > old_sev:
            kind = "regression" if (new["status"] == "fail" and old["status"] in ("ok", "skip")) \
                   else "worsened"
        else:
            kind = "recovery" if (old["status"] == "fail" and new["status"] in ("ok", "skip")) \
                   else "improved"
        events.append({
            "name": name, "kind": kind,
            "old_status": old["status"], "new_status": new["status"],
            "old_message": old["message"], "new_message": new["message"],
        })

    for name, old in old_map.items():
        if name not in new_map:
            events.append({
                "name": name, "kind": "removed",
                "old_status": old["status"], "new_status": None,
                "old_message": old["message"], "new_message": None,
            })

    # Sort: regressions first, then worsened, then new, then improved, etc.
    kind_order = {"regression": 0, "worsened": 1, "new": 2, "improved": 3,
                  "recovery": 4, "removed": 5}
    events.sort(key=lambda e: kind_order.get(e["kind"], 99))
    return events
