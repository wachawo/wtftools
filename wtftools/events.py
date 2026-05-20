#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Event timeline: collect significant events from journal/wtmp into one view.

Sources (best-effort, each one is skip-able if its underlying tool is missing):
    reboot         `last -x reboot`
    oom            journalctl kernel oom-killer / "out of memory"
    failed-unit    journalctl SYSTEMD_UNIT_RESULT=failed
    kernel-err     journalctl -k -p err
    auth-fail      journalctl ssh.service "Failed password"
    login          `last -F` recent successful sessions

The fan-out is intentional: events are easier to read with categorical icons
than a wall of journal text. Each event normalizes to a single Event row.
"""

import logging
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from wtftools.checks.sysinfo import run

logger = logging.getLogger(__name__)

EVENT_KINDS = ("reboot", "oom", "failed-unit", "kernel-err", "auth-fail", "login")


@dataclass
class Event:
    """One event on the host timeline."""
    timestamp: float            # unix epoch
    kind: str                   # one of EVENT_KINDS
    message: str
    detail: str = ""

    def iso(self) -> str:
        try:
            return datetime.fromtimestamp(self.timestamp, tz=timezone.utc) \
                .astimezone() \
                .strftime("%Y-%m-%d %H:%M:%S")
        except (OverflowError, OSError, ValueError):
            return "????-??-?? ??:??:??"


def collect_events(hours: int = 24, kinds: Optional[List[str]] = None) -> List[Event]:
    """Gather events from all configured sources, sorted newest-first.

    `kinds` filters by EVENT_KINDS. None means all.
    """
    wanted = set(kinds) if kinds else set(EVENT_KINDS)
    events: List[Event] = []
    if "reboot" in wanted:
        events.extend(_collect_reboots(hours))
    if "oom" in wanted:
        events.extend(_collect_oom(hours))
    if "failed-unit" in wanted:
        events.extend(_collect_failed_units(hours))
    if "kernel-err" in wanted:
        events.extend(_collect_kernel_errors(hours))
    if "auth-fail" in wanted:
        events.extend(_collect_auth_failures(hours))
    if "login" in wanted:
        events.extend(_collect_logins(hours))
    events.sort(key=lambda e: e.timestamp, reverse=True)
    return events


def _journal_since(hours: int) -> str:
    return f"{hours} hours ago"


def _parse_iso_lines(text: str) -> List[tuple]:
    """Parse journalctl `-o short-iso` output into (epoch, message) tuples."""
    out: List[tuple] = []
    for line in text.splitlines():
        # Examples:
        #   2026-05-20T08:55:01+0000 host kernel: Out of memory: Killed process …
        #   2026-05-20T08:55:01+0300 host sshd[1234]: Failed password for foo
        match = re.match(
            r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{4})?)\s+(.+)$",
            line,
        )
        if not match:
            continue
        ts_raw, rest = match.group(1), match.group(2)
        try:
            # strptime with %z handles "+0000"; older Python wants tweaking.
            try:
                dt = datetime.strptime(ts_raw, "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                dt = datetime.strptime(ts_raw, "%Y-%m-%dT%H:%M:%S")
                dt = dt.replace(tzinfo=timezone.utc)
            epoch = dt.timestamp()
        except (ValueError, OSError):
            continue
        out.append((epoch, rest))
    return out


def _collect_oom(hours: int) -> List[Event]:
    if not shutil.which("journalctl"):
        return []
    rc, out, _ = run(
        ["journalctl", "-k", "--since", _journal_since(hours),
         "-o", "short-iso", "--no-pager", "-q"],
        timeout=10,
    )
    if rc != 0 or not out:
        return []
    events: List[Event] = []
    for epoch, rest in _parse_iso_lines(out):
        low = rest.lower()
        if "out of memory" in low or "killed process" in low or "oom-killer" in low:
            events.append(Event(timestamp=epoch, kind="oom",
                                message=rest[-180:].strip()))
    return events


def _collect_kernel_errors(hours: int) -> List[Event]:
    if not shutil.which("journalctl"):
        return []
    rc, out, _ = run(
        ["journalctl", "-k", "-p", "err", "--since", _journal_since(hours),
         "-o", "short-iso", "--no-pager", "-q"],
        timeout=10,
    )
    if rc != 0 or not out:
        return []
    return [
        Event(timestamp=epoch, kind="kernel-err",
              message=rest[-180:].strip())
        for epoch, rest in _parse_iso_lines(out)
    ]


def _collect_failed_units(hours: int) -> List[Event]:
    """Look for unit-result=failed events in the user/system journal."""
    if not shutil.which("journalctl"):
        return []
    # JOB_RESULT=failed is the systemd-emitted line when a unit transitions
    # to failed state. Fall back to text-grep if the field-match is empty.
    rc, out, _ = run(
        ["journalctl", "--since", _journal_since(hours),
         "JOB_RESULT=failed", "-o", "short-iso", "--no-pager", "-q"],
        timeout=10,
    )
    events: List[Event] = []
    if rc == 0 and out:
        for epoch, rest in _parse_iso_lines(out):
            events.append(Event(timestamp=epoch, kind="failed-unit",
                                message=rest.strip()))
    return events


def _collect_auth_failures(hours: int) -> List[Event]:
    if not shutil.which("journalctl"):
        return []
    rc, out, _ = run(
        ["journalctl", "--since", _journal_since(hours),
         "-o", "short-iso", "--no-pager", "-q",
         "_SYSTEMD_UNIT=ssh.service", "_SYSTEMD_UNIT=sshd.service"],
        timeout=10,
    )
    if rc != 0 or not out:
        return []
    events: List[Event] = []
    for epoch, rest in _parse_iso_lines(out):
        low = rest.lower()
        if "failed password" in low or "invalid user" in low or "authentication failure" in low:
            events.append(Event(timestamp=epoch, kind="auth-fail",
                                message=rest.strip()))
    return events


def _collect_reboots(hours: int) -> List[Event]:
    """Use `last -x reboot --time-format iso` for explicit reboot rows."""
    if not shutil.which("last"):
        return []
    rc, out, _ = run(["last", "-x", "reboot", "--time-format", "iso"], timeout=5)
    if rc != 0 or not out:
        return []
    cutoff = time.time() - hours * 3600
    events: List[Event] = []
    for line in out.splitlines():
        # Example: "reboot   system boot  6.11.0-29-generic 2026-05-13T22:30:09+01:00 still running"
        match = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:?\d{2})", line)
        if not match:
            continue
        ts_raw = match.group(1)
        # Python wants %z without colon; strip it.
        ts_raw_norm = re.sub(r"([+-]\d{2}):?(\d{2})$", r"\1\2", ts_raw)
        try:
            dt = datetime.strptime(ts_raw_norm, "%Y-%m-%dT%H:%M:%S%z")
            epoch = dt.timestamp()
        except ValueError:
            continue
        if epoch < cutoff:
            continue
        events.append(Event(timestamp=epoch, kind="reboot",
                            message=line.strip()))
    return events


def _collect_logins(hours: int) -> List[Event]:
    if not shutil.which("last"):
        return []
    rc, out, _ = run(["last", "-n", "50", "--time-format", "iso"], timeout=5)
    if rc != 0 or not out:
        return []
    cutoff = time.time() - hours * 3600
    events: List[Event] = []
    for line in out.splitlines():
        # Skip the reboot rows here — they're handled in _collect_reboots.
        if line.strip().startswith("reboot"):
            continue
        if not line.strip() or line.startswith("wtmp"):
            continue
        match = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:?\d{2})", line)
        if not match:
            continue
        ts_raw_norm = re.sub(r"([+-]\d{2}):?(\d{2})$", r"\1\2", match.group(1))
        try:
            dt = datetime.strptime(ts_raw_norm, "%Y-%m-%dT%H:%M:%S%z")
            epoch = dt.timestamp()
        except ValueError:
            continue
        if epoch < cutoff:
            continue
        events.append(Event(timestamp=epoch, kind="login",
                            message=line.strip()))
    return events
