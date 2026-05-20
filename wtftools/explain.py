#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnostic advice: turn (check, status) → actionable suggestion.

Two modes:

1. **Text mode** (`wtf explain`): rule-based, deterministic, no network.
   Each WARN/FAIL result is matched against a suggestion table.

2. **Prompt mode** (`wtf explain --prompt`): emit an LLM-ready prompt that
   includes the audit findings — pipe to `claude`, `ollama run`, or any other
   LLM and get a synthesized diagnosis without bundling an LLM dependency.
"""

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple, Union

from wtftools.audit import CheckResult
from wtftools.checks import sysinfo


@dataclass
class Suggestion:
    """A diagnostic suggestion for one CheckResult."""

    name: str
    status: str
    message: str
    advice: str
    investigation: List[str] = field(default_factory=list)


SuggestionAdvice = Union[str, Callable[[CheckResult], str]]

# Each entry: (predicate, advice). The first matching entry wins.
# Advice is either a literal string or a callable that builds it from the result.
_RULES: List[Tuple[Callable[[CheckResult], bool], SuggestionAdvice]] = [
    (
        lambda r: r.name == "swap" and r.status in ("warn", "fail"),
        "Swap is heavily used. Likely causes: a leaking process is being paged out, "
        "memory pressure forces swap. Action: identify top RAM consumers via "
        "`wtf info`, restart the offender or tune memory limits, consider adding "
        "RAM/swap. Recurrent on cron-jobs → consider OOM-protecting critical services.",
    ),
    (
        lambda r: r.name == "memory" and r.status in ("warn", "fail"),
        "Memory headroom is low. Find the consumer via `wtf info` (TOP BY RAM). "
        "Quick fixes: restart the bloated service, lower its memory limits, scale "
        "out. Long-term: add monitoring/alerts.",
    ),
    (
        lambda r: r.name.startswith("disk ") and r.status in ("warn", "fail"),
        lambda r: (
            f"Filesystem {r.name[5:]} is filling up. Common culprits: log files "
            f"in /var/log, journald, docker overlay, core dumps. "
            f"Run `du -sh {r.name[5:]}/* | sort -h` to find the largest. "
            f"For journald: `journalctl --vacuum-size=4G`."
        ),
    ),
    (
        lambda r: r.name.startswith("inodes ") and r.status in ("warn", "fail"),
        lambda r: (
            f"Inode exhaustion on {r.name[7:]}. Hidden small-file accumulation: "
            f"PHP sessions, mailq, sysvshm, broken caches. "
            f"`find {r.name[7:]} -xdev -type f | head -1000` to sample."
        ),
    ),
    (
        lambda r: r.name == "load average" and r.status in ("warn", "fail"),
        "Run queue depth exceeds CPU count. Combine with `wtf audit --check iowait psi` " "to separate CPU-bound from IO-bound. `wtf info` (TOP BY CPU) shows the consumer.",
    ),
    (
        lambda r: r.name == "CPU iowait" and r.status in ("warn", "fail"),
        "High iowait — processes blocked on disk/network IO. Check `iostat -x 1` "
        "for the busy device. Could be a saturated disk, network FS hang, or "
        "kernel-task stuck in D state (`wtf audit --check d-state`).",
    ),
    (
        lambda r: r.name.startswith("PSI ") and r.status in ("warn", "fail"),
        lambda r: (
            "Pressure stall on " + r.name[4:] + " — real contention even if classic "
            "metrics look OK. avg10 is the recent (10s) share of time tasks were "
            "stalled. Drill into the matching subsystem: cpu→load/top, "
            "memory→`wtf info`, io→iostat/iotop."
        ),
    ),
    (
        lambda r: r.name == "failed systemd units" and r.status == "fail",
        lambda r: ("Failed unit(s): " + ", ".join(r.detail) + ". " "Inspect each with `wtf services <name>` or `systemctl status <name>` " "+ `journalctl -u <name> -n 50`."),
    ),
    (
        lambda r: r.name == "restart loops" and r.status in ("warn", "fail"),
        lambda r: (
            "Service(s) restarted many times since boot. systemd is hiding flapping. "
            "List: " + ", ".join(r.detail) + ". "
            "Use `wtf services <name>` for journal + last cause. "
            "Consider Restart=on-failure with StartLimitBurst, or fix the underlying bug."
        ),
    ),
    (
        lambda r: r.name == "enabled but down" and r.status in ("warn", "fail"),
        lambda r: ("Service is enabled but not running. " "Cause is in: " + ", ".join(r.detail[:3]) + ". " "Run `systemctl status <name>` for the last fail reason."),
    ),
    (
        lambda r: r.name.startswith("OOM kills") and r.status == "fail",
        "Kernel killed processes due to OOM. Identify the victim and the bloated "
        "process: `journalctl -k --since '24h ago' | grep -i 'oom\\|killed'`. "
        "Address: add RAM, fix leak, tune oom_score_adj for critical services.",
    ),
    (
        lambda r: r.name == "kernel taint" and r.status in ("warn", "fail"),
        "Kernel saw something it didn't like (proprietary module, oops, machine "
        "check…). Check `dmesg | grep -i 'taint\\|oops\\|bug'` and "
        "`cat /proc/sys/kernel/tainted`. MACHINE_CHECK = hardware error.",
    ),
    (
        lambda r: r.name == "cert expiry" and r.status in ("warn", "fail"),
        lambda r: (
            "TLS certificate(s) expiring soon. Renew via `certbot renew` (Let's "
            "Encrypt) or your CA flow. Most urgent: " + (r.detail[0] if r.detail else "see audit detail") + ". "
            "Automate renewal + reload hook for the consumer (nginx/haproxy/etc)."
        ),
    ),
    (
        lambda r: r.name == "TCP retransmits" and r.status in ("warn", "fail"),
        "Network is dropping packets. Check switch port errors (`ethtool -S eth0`), " "MTU mismatch, congestion. `ss -ti` shows per-connection retrans counts.",
    ),
    (
        lambda r: r.name == "network errors" and r.status in ("warn", "fail"),
        "NIC accumulated rx/tx errors or drops. Likely a hardware/cable issue or " "buffer overflow under burst. `ethtool -S <iface>`, `ip -s link show <iface>`.",
    ),
    (
        lambda r: r.name == "D-state processes" and r.status in ("warn", "fail"),
        "Processes stuck in uninterruptible sleep — typically blocked on a hung "
        "mount or storage device. `ps -eLo pid,stat,wchan:25,comm | grep ' D'` "
        "shows where each is waiting in the kernel.",
    ),
    (
        lambda r: r.name == "conntrack" and r.status in ("warn", "fail"),
        "Connection tracking table near limit. Will silently drop new connections "
        "when full. Quick fix: `sysctl -w net.netfilter.nf_conntrack_max=<2x>`. "
        "Long-term: tune timeouts (nf_conntrack_tcp_timeout_established), "
        "exempt high-throughput flows via NOTRACK, or scale out.",
    ),
    (
        lambda r: r.name == "journal disk" and r.status in ("warn", "fail"),
        "journald has grown large. `journalctl --vacuum-size=2G` or " "`--vacuum-time=7d`. To bound permanently: edit " "/etc/systemd/journald.conf → `SystemMaxUse=4G`.",
    ),
    (
        lambda r: r.name == "reboot required" and r.status in ("warn", "fail"),
        "Pending kernel/library update needs a reboot. Schedule the reboot to " "pick up security fixes. The pkg list shows what triggered it.",
    ),
    (
        lambda r: r.name == "system state" and r.status in ("warn", "fail"),
        "systemd reports 'degraded' — at least one unit is failed. Use " "`wtf audit --check failed-units` for the list, then `wtf services <name>`.",
    ),
    (
        lambda r: r.name == "time sync" and r.status in ("warn", "fail"),
        "Clock not synchronized. Effects: TLS cert failures, log misalignment, "
        "auth replay protection breaks. Run `timedatectl set-ntp true`, check "
        "`chronyc tracking` for drift, ensure firewall allows NTP.",
    ),
    (
        lambda r: r.name == "zombie processes" and r.status in ("warn", "fail"),
        "Zombie processes — parents not reap()ing exited children. Find the "
        "parent: `ps -eo pid,ppid,stat,comm | awk '$3 ~ /Z/'`. Usually a "
        "supervisor/process-manager bug; restarting the parent reaps the zombie.",
    ),
    (
        lambda r: r.name == "read-only mounts" and r.status == "fail",
        lambda r: (
            "Filesystem(s) unexpectedly read-only: " + ", ".join(r.detail) + ". "
            "Cause: kernel remount-ro on IO error or fsck failure. Check "
            "`dmesg | grep -i 'EXT4-fs error\\|remount'`. May need fsck + reboot."
        ),
    ),
    (
        lambda r: r.name.startswith("kernel errors") and r.status in ("warn", "fail"),
        "Recent kernel error lines — could indicate hardware (memory, disk), " "driver, or filesystem issue. `journalctl -k -p err --since '24h ago'`.",
    ),
    (
        lambda r: r.name == "open file descriptors" and r.status in ("warn", "fail"),
        "File descriptor pressure. Find offenders: " '`for p in /proc/[0-9]*; do echo "$(ls $p/fd 2>/dev/null | wc -l) $p"; done | sort -n | tail`.',
    ),
    (
        lambda r: r.name == "process count" and r.status in ("warn", "fail"),
        "PID table filling — fork-bomb, runaway service, or insufficient pid_max. " "Find the parent: `ps -eo pid,ppid,comm --sort=-pid | head -20`.",
    ),
    (lambda r: r.name.startswith("plugin:") and r.status in ("warn", "fail"), "Custom plugin reported a problem. Re-run the plugin manually to inspect " "its full output."),
]

_FALLBACK = "No built-in advice for this check yet. Use `wtf audit -v --check <name>` " "to see the full detail, or pipe `wtf explain --prompt` to an LLM."


def suggest(result: CheckResult) -> Suggestion:
    """Return a Suggestion for one CheckResult."""
    for predicate, advice in _RULES:
        if predicate(result):
            text = advice(result) if callable(advice) else advice
            return Suggestion(name=result.name, status=result.status, message=result.message, advice=text)
    return Suggestion(name=result.name, status=result.status, message=result.message, advice=_FALLBACK)


def investigate(result: CheckResult) -> List[str]:
    """Collect dynamic context for one CheckResult — heavier than static advice.

    Returns a list of rendered lines (no markup; caller adds indentation).
    Skipped silently when underlying tools are unavailable.

    Currently specialised for disk-fill findings (`disk /…` and `inodes /…`).
    Future scope: per-finding investigation for swap, failed-units, OOM, etc.
    """
    lines: List[str] = []
    name = result.name
    if name.startswith("disk ") or name.startswith("inodes "):
        prefix_len = 5 if name.startswith("disk ") else 7
        mount = name[prefix_len:]

        top = sysinfo.get_top_paths_in(mount, limit=6)
        if top:
            lines.append(f"Top directories under {mount}:")
            for entry in top:
                lines.append(f"  {sysinfo.format_bytes(entry['bytes']):>10}  {entry['path']}")

        big_files = sysinfo.get_largest_files(mount, limit=5, min_size_mb=100)
        if big_files:
            lines.append(f"Largest files (>100MB) under {mount}:")
            for entry in big_files:
                lines.append(f"  {sysinfo.format_bytes(entry['bytes']):>10}  {entry['path']}")

        journal_bytes = sysinfo.get_journal_disk_usage()
        if journal_bytes:
            lines.append(f"Journald: {sysinfo.format_bytes(journal_bytes)}  " f"(`journalctl --vacuum-size=2G` to trim)")

        docker_df = sysinfo.get_docker_disk_usage()
        if docker_df:
            lines.append("Docker `system df`:")
            for row in docker_df:
                lines.append(f"  {row['type']:<14} count={row['count']:<4} " f"size={row['size']:<10} reclaimable={row['reclaimable']}")

        containers = sysinfo.get_docker_container_sizes(limit=5)
        if containers:
            lines.append("Largest Docker containers (RW + base image):")
            for c in containers:
                lines.append(f"  {c['size']:>14}  {c['name']:<24} {c['image']}")

        logs = sysinfo.get_docker_log_sizes(limit=5)
        if logs:
            lines.append("Largest Docker JSON log files:")
            for entry in logs:
                lines.append(f"  {sysinfo.format_bytes(entry['bytes']):>10}  " f"{entry['name']:<24} {entry['log_path']}")
    return lines


def explain_results(results: List[CheckResult], include_ok: bool = False, deep: bool = False) -> List[Suggestion]:
    """Return Suggestions for every problem result (or all when include_ok).

    When `deep=True`, each suggestion is enriched with the output of
    `investigate(result)` — slower but gives concrete next-action data.
    """
    out: List[Suggestion] = []
    for r in results:
        if not include_ok and r.status not in ("warn", "fail"):
            continue
        s = suggest(r)
        if deep:
            s.investigation = investigate(r)
        out.append(s)
    return out


PROMPT_PREAMBLE = """You are a senior SRE. Below is a wtftools audit of a Linux host.
For each WARN/FAIL finding, give a 1-2 sentence likely root cause and 2-3 concrete actions.
Keep it tight: a paragraph per finding, no preamble. Output the highest-priority finding first.
"""


def render_prompt(results: List[CheckResult], host: Optional[str] = None) -> str:
    """Render an LLM-ready prompt summarizing the audit."""
    lines = [PROMPT_PREAMBLE]
    if host:
        lines.append(f"Host: {host}")
    lines.append("")
    lines.append("Audit findings (all rows; FAIL/WARN are the priorities):")
    for r in results:
        marker = {"ok": "[ OK ]", "warn": "[WARN]", "fail": "[FAIL]", "skip": "[SKIP]"}.get(r.status, "[????]")
        lines.append(f"  {marker} {r.name:<30} {r.message}")
        for d in r.detail[:3]:
            lines.append(f"          • {d}")
    return "\n".join(lines) + "\n"
