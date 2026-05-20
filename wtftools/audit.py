#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit checks for `wtf audit`. Each returns a structured CheckResult."""

import logging
import os
import shutil
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from wtftools import config as config_mod
from wtftools.checks import cron, sysinfo
from wtftools.checks import plugins as plugins_mod

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Outcome of a single audit check."""

    name: str
    status: str  # ok | warn | fail | skip
    message: str
    detail: List[str] = field(default_factory=list)


# Time-windowed checks (OOM, auth, kernel errors) read this value at run time.
# Override via set_since_hours() — used by `wtf audit --since N`.
_SINCE_HOURS: int = 24


def set_since_hours(hours: int) -> None:
    """Override the look-back window for time-bounded checks."""
    global _SINCE_HOURS
    _SINCE_HOURS = max(1, int(hours))


def _check_cron_daemon() -> CheckResult:
    errors = cron.check_daemon()
    if not errors:
        return CheckResult("cron daemon", "ok", "active")
    return CheckResult("cron daemon", "warn", "; ".join(errors))


def _check_load() -> CheckResult:
    cfg = config_mod.get_config()
    load1, load5, load15 = sysinfo.get_loadavg()
    cpus = sysinfo.get_cpu_count()
    ratio = load1 / max(cpus, 1)
    msg = f"load avg {load1:.2f} {load5:.2f} {load15:.2f} / {cpus} CPU"
    if ratio >= cfg.load_fail_ratio:
        return CheckResult("load average", "fail", msg + f" (1m load is {ratio:.1f}x CPUs)")
    if ratio >= cfg.load_warn_ratio:
        return CheckResult("load average", "warn", msg + f" (1m load is {ratio:.1f}x CPUs)")
    return CheckResult("load average", "ok", msg)


def _check_memory() -> CheckResult:
    cfg = config_mod.get_config()
    mem = sysinfo.get_memory_summary()
    pct = mem["percent"]
    used = sysinfo.format_bytes(mem["used"])
    total = sysinfo.format_bytes(mem["total"])
    msg = f"{used} / {total} used ({pct}%)"
    if pct >= cfg.mem_fail_pct:
        return CheckResult("memory", "fail", msg)
    if pct >= cfg.mem_warn_pct:
        return CheckResult("memory", "warn", msg)
    return CheckResult("memory", "ok", msg)


def _check_swap() -> CheckResult:
    cfg = config_mod.get_config()
    mem = sysinfo.get_memory_summary()
    if mem["swap_total"] == 0:
        return CheckResult("swap", "skip", "no swap configured")
    pct = mem["swap_percent"]
    used = sysinfo.format_bytes(mem["swap_used"])
    total = sysinfo.format_bytes(mem["swap_total"])
    msg = f"{used} / {total} used ({pct}%)"
    if pct >= cfg.swap_fail_pct:
        return CheckResult("swap", "fail", msg)
    if pct >= cfg.swap_warn_pct:
        return CheckResult("swap", "warn", msg)
    return CheckResult("swap", "ok", msg)


def _check_disks() -> List[CheckResult]:
    cfg = config_mod.get_config()
    results: List[CheckResult] = []
    for disk in sysinfo.get_disks():
        target = disk["target"]
        pct = disk["percent"]
        used = sysinfo.format_bytes(disk["used"])
        total = sysinfo.format_bytes(disk["total"])
        msg = f"{used} / {total} used ({pct}%)"
        name = f"disk {target}"
        if pct >= cfg.disk_fail_pct:
            results.append(CheckResult(name, "fail", msg))
        elif pct >= cfg.disk_warn_pct:
            results.append(CheckResult(name, "warn", msg))
        else:
            results.append(CheckResult(name, "ok", msg))
    return results


def _check_inodes() -> List[CheckResult]:
    results: List[CheckResult] = []
    for disk in sysinfo.get_disks():
        try:
            stat = os.statvfs(disk["target"])
        except OSError:
            continue
        if stat.f_files == 0:
            continue
        used = stat.f_files - stat.f_ffree
        pct = int(round(100 * used / stat.f_files)) if stat.f_files else 0
        msg = f"{pct}% inodes used"
        name = f"inodes {disk['target']}"
        if pct >= 95:
            results.append(CheckResult(name, "fail", msg))
        elif pct >= 85:
            results.append(CheckResult(name, "warn", msg))
        # skip ok inodes from default output for brevity — only surface problems
    return results


def _check_failed_units() -> CheckResult:
    if not shutil.which("systemctl"):
        return CheckResult("failed systemd units", "skip", "systemctl not available")
    units = sysinfo.get_failed_units()
    if not units:
        return CheckResult("failed systemd units", "ok", "no failed units")
    return CheckResult("failed systemd units", "fail", f"{len(units)} failed unit(s)", detail=units)


def _check_zombies() -> CheckResult:
    count = sysinfo.count_zombie_processes()
    if count == 0:
        return CheckResult("zombie processes", "ok", "0 zombies")
    if count >= 5:
        return CheckResult("zombie processes", "fail", f"{count} zombies")
    return CheckResult("zombie processes", "warn", f"{count} zombie(s)")


def _check_oom_kills() -> CheckResult:
    hrs = _SINCE_HOURS
    events = sysinfo.get_oom_events(hours=hrs)
    label = f"OOM kills ({hrs}h)"
    if not events:
        return CheckResult(label, "ok", "none")
    return CheckResult(label, "fail", f"{len(events)} OOM event(s)", detail=events[:3])


def _check_kernel_errors() -> CheckResult:
    hrs = _SINCE_HOURS
    label = f"kernel errors ({hrs}h)"
    if not shutil.which("journalctl"):
        return CheckResult(label, "skip", "journalctl not available")
    errors = sysinfo.get_recent_kernel_errors(hours=hrs, limit=5)
    if not errors:
        return CheckResult(label, "ok", "none")
    return CheckResult(label, "warn", f"{len(errors)} recent kernel error line(s)", detail=errors)


def _check_pending_updates() -> CheckResult:
    count = sysinfo.get_pending_updates()
    if count < 0:
        return CheckResult("pending updates", "skip", "apt not available")
    if count == 0:
        return CheckResult("pending updates", "ok", "all packages up to date")
    if count >= 50:
        return CheckResult("pending updates", "warn", f"{count} package(s) upgradable")
    return CheckResult("pending updates", "ok", f"{count} package(s) upgradable")


def _check_fds() -> CheckResult:
    cfg = config_mod.get_config()
    fds = sysinfo.get_open_fds()
    if fds is None:
        return CheckResult("open file descriptors", "skip", "cannot read /proc/sys/fs/file-nr")
    used, max_fd = fds
    pct = int(round(100 * used / max_fd)) if max_fd else 0
    msg = f"{used} / {max_fd} ({pct}%)"
    if pct >= cfg.fd_fail_pct:
        return CheckResult("open file descriptors", "fail", msg)
    if pct >= cfg.fd_warn_pct:
        return CheckResult("open file descriptors", "warn", msg)
    return CheckResult("open file descriptors", "ok", msg)


def _check_failed_auth() -> CheckResult:
    cfg = config_mod.get_config()
    hrs = _SINCE_HOURS
    label = f"failed auth ({hrs}h)"
    count = sysinfo.get_failed_auth_count(hours=hrs)
    if count == 0:
        return CheckResult(label, "ok", "none")
    if count >= cfg.auth_warn_count:
        return CheckResult(label, "warn", f"{count} failed login attempts")
    return CheckResult(label, "ok", f"{count} failed login attempt(s)")


def _check_user_crontabs() -> CheckResult:
    errors: List[str] = []
    rows = 0
    for path, is_system in cron.discover_default_targets():
        r, e, _ = cron.check_file(path, is_system_crontab=is_system)
        rows += r
        errors.extend(e)
    if rows == 0:
        return CheckResult("crontab syntax", "skip", "no crontab files visible")
    if not errors:
        return CheckResult("crontab syntax", "ok", f"{rows} cron line(s), no errors")
    return CheckResult("crontab syntax", "fail", f"{len(errors)} error(s) in {rows} cron line(s)", detail=errors[:5])


def _check_uptime() -> CheckResult:
    uptime = sysinfo.get_uptime_seconds()
    msg = sysinfo.format_duration(uptime)
    if uptime < 300:
        return CheckResult("uptime", "warn", f"recently rebooted ({msg} ago)")
    return CheckResult("uptime", "ok", msg)


def _check_system_running() -> CheckResult:
    state = sysinfo.get_system_running_state()
    if state is None:
        return CheckResult("system state", "skip", "systemctl unavailable")
    if state == "running":
        return CheckResult("system state", "ok", "running")
    if state == "degraded":
        return CheckResult("system state", "fail", "system is in 'degraded' state")
    if state in ("initializing", "starting"):
        return CheckResult("system state", "warn", state)
    if state == "maintenance":
        return CheckResult("system state", "fail", "system is in maintenance mode")
    return CheckResult("system state", "warn", state)


def _check_enabled_inactive() -> CheckResult:
    if not shutil.which("systemctl"):
        return CheckResult("enabled but down", "skip", "systemctl unavailable")
    units = sysinfo.get_enabled_inactive_units()
    if not units:
        return CheckResult("enabled but down", "ok", "all enabled services are running")
    rendered = [f"{u['name']} (ActiveState={u['state']}, Result={u['result']})" for u in units]
    if any(u["state"] == "failed" for u in units):
        return CheckResult("enabled but down", "fail", f"{len(units)} enabled service(s) not running", detail=rendered)
    return CheckResult("enabled but down", "warn", f"{len(units)} enabled service(s) not running", detail=rendered)


def _check_reboot_required() -> CheckResult:
    msg = sysinfo.get_reboot_required()
    if msg is None:
        return CheckResult("reboot required", "ok", "no")
    return CheckResult("reboot required", "warn", msg)


def _check_time_sync() -> CheckResult:
    status = sysinfo.get_time_sync_status()
    if status["synchronized"] is None:
        return CheckResult("time sync", "skip", status["source"])
    # When chrony is available, the magnitude of drift is far more useful than
    # the binary sync/no-sync flag from timedatectl.
    offset_s = sysinfo.get_chrony_offset()
    suffix = ""
    drift_severity: Optional[str] = None
    if offset_s is not None:
        ms = offset_s * 1000.0
        suffix = f" · offset={ms:.1f}ms"
        if ms >= 1000:
            drift_severity = "fail"
        elif ms >= 100:
            drift_severity = "warn"
    if status["synchronized"]:
        msg = "NTP synchronized" + suffix
        if drift_severity == "fail":
            return CheckResult("time sync", "fail", msg + " (drift >1s)")
        if drift_severity == "warn":
            return CheckResult("time sync", "warn", msg + " (drift >100ms)")
        return CheckResult("time sync", "ok", msg)
    if status["ntp_active"]:
        return CheckResult("time sync", "warn", "NTP active but not synchronized" + suffix)
    return CheckResult("time sync", "fail", "NTP disabled and clock not synchronized" + suffix)


def _check_fail2ban() -> CheckResult:
    jails = sysinfo.get_fail2ban_jails()
    if jails is None:
        return CheckResult("fail2ban", "skip", "fail2ban-client not installed / daemon down")
    if not jails:
        return CheckResult("fail2ban", "ok", "active, no jails configured")
    banned_now = sum(j["banned"] for j in jails)
    banned_total = sum(j["total"] for j in jails)
    detail = [f"{j['name']}: {j['banned']} banned now / {j['total']} total" for j in jails]
    # Active bans are informational, not a problem. We surface them so the
    # SRE knows fail2ban is actually doing something.
    msg = f"{banned_now} IP(s) currently banned across " f"{len(jails)} jail(s)  · {banned_total} total since boot"
    return CheckResult("fail2ban", "ok", msg, detail=detail)


def _check_http_probes() -> List[CheckResult]:
    """One result row per configured HTTP probe (HEAD)."""
    cfg = config_mod.get_config()
    urls = [u.strip() for u in cfg.http_probes.split(",") if u.strip()]
    if not urls:
        return []
    results: List[CheckResult] = []
    for url in urls:
        outcome = sysinfo.probe_http(url, timeout=cfg.probe_timeout)
        name = f"http probe {url}"
        if outcome["error"]:
            results.append(CheckResult(name, "fail", outcome["error"]))
            continue
        status = outcome["status_code"] or 0
        latency = outcome["latency_ms"] or 0.0
        msg = f"HTTP {status} · {latency:.0f}ms"
        if status < 200 or status >= 400:
            results.append(CheckResult(name, "fail", msg))
        elif latency >= cfg.probe_slow_ms:
            results.append(CheckResult(name, "warn", msg + " (slow)"))
        else:
            results.append(CheckResult(name, "ok", msg))
    return results


def _check_tcp_probes() -> List[CheckResult]:
    """One result row per configured TCP probe (connect)."""
    cfg = config_mod.get_config()
    targets = [t.strip() for t in cfg.tcp_probes.split(",") if t.strip()]
    if not targets:
        return []
    results: List[CheckResult] = []
    for target in targets:
        outcome = sysinfo.probe_tcp(target, timeout=cfg.probe_timeout)
        name = f"tcp probe {target}"
        if outcome["error"]:
            results.append(CheckResult(name, "fail", outcome["error"]))
            continue
        latency = outcome["latency_ms"] or 0.0
        msg = f"connected · {latency:.0f}ms"
        if latency >= cfg.probe_slow_ms:
            results.append(CheckResult(name, "warn", msg + " (slow)"))
        else:
            results.append(CheckResult(name, "ok", msg))
    return results


def _check_smart() -> CheckResult:
    """Per-disk SMART health via smartctl."""
    result = sysinfo.get_smart_status()
    if result is None:
        return CheckResult("disk SMART", "skip", "smartctl not installed (apt install smartmontools)")
    if not result:
        return CheckResult("disk SMART", "skip", "no SMART-capable disks found")
    failed = [r for r in result if r["passed"] is False]
    detail = [
        f"{r['device']}: " + ("PASSED" if r["passed"] else ("FAILED — replace soon" if r["passed"] is False else "unknown")) + (f" ({r['message']})" if r["message"] else "")
        for r in result
    ]
    if failed:
        return CheckResult("disk SMART", "fail", f"{len(failed)} disk(s) reporting SMART failure", detail=detail)
    return CheckResult("disk SMART", "ok", f"all {len(result)} disk(s) passing SMART", detail=detail)


def _check_temperatures() -> CheckResult:
    cfg = config_mod.get_config()
    temps = sysinfo.get_temperatures()
    if not temps:
        return CheckResult("hw temperatures", "skip", "no /sys/class/hwmon sensors found")
    hottest = max(temps, key=lambda t: t["celsius"])
    summary = f"max {hottest['celsius']}°C " f"({hottest['sensor']}/{hottest['label']})  " f"· {len(temps)} sensor(s)"
    detail = [f"{t['celsius']:5.1f}°C  {t['sensor']}/{t['label']}" for t in temps]
    if hottest["celsius"] >= cfg.temp_fail_c:
        return CheckResult("hw temperatures", "fail", summary, detail=detail)
    if hottest["celsius"] >= cfg.temp_warn_c:
        return CheckResult("hw temperatures", "warn", summary, detail=detail)
    return CheckResult("hw temperatures", "ok", summary)


def _check_dns() -> CheckResult:
    cfg = config_mod.get_config()
    hosts = [h.strip() for h in cfg.dns_probe_hosts.split(",") if h.strip()]
    if not hosts:
        return CheckResult("dns resolution", "skip", "no probe hosts configured")
    results: List[Tuple[str, Optional[float]]] = []
    for host in hosts:
        results.append((host, sysinfo.resolve_hostname(host, timeout=cfg.dns_probe_timeout)))
    succeeded = [(h, ms) for h, ms in results if ms is not None]
    failed = [h for h, ms in results if ms is None]
    detail = [f"{h}: {ms:.0f}ms" for h, ms in succeeded] + [f"{h}: FAILED (timeout/error)" for h in failed]
    if not succeeded:
        return CheckResult("dns resolution", "fail", f"{len(failed)} probe(s) failed (no DNS reachable)", detail=detail)
    if failed:
        return CheckResult("dns resolution", "warn", f"{len(failed)}/{len(hosts)} probe(s) failed", detail=detail)
    slowest = max(ms for _, ms in succeeded)
    msg = f"all {len(hosts)} resolved (slowest: {slowest:.0f}ms)"
    return CheckResult("dns resolution", "ok", msg)


def _check_docker() -> CheckResult:
    problems = sysinfo.get_docker_problem_containers()
    if problems is None:
        return CheckResult("docker", "skip", "docker not installed or daemon unreachable")
    if not problems:
        return CheckResult("docker", "ok", "no unhealthy/restarting containers")
    detail = [f"{c['name']}: {c['problem']} ({c['status']})" for c in problems]
    has_unhealthy = any(c["problem"] == "unhealthy" for c in problems)
    status = "fail" if has_unhealthy else "warn"
    return CheckResult("docker", status, f"{len(problems)} container(s) unhealthy/restarting", detail=detail)


def _check_readonly_mounts() -> CheckResult:
    mounts = sysinfo.get_readonly_mounts()
    if not mounts:
        return CheckResult("read-only mounts", "ok", "none unexpected")
    return CheckResult("read-only mounts", "fail", f"{len(mounts)} unexpectedly read-only mount(s)", detail=mounts)


def _check_stuck_processes() -> CheckResult:
    stuck = sysinfo.get_stuck_processes()
    if not stuck:
        return CheckResult("D-state processes", "ok", "none")
    if len(stuck) >= 5:
        return CheckResult("D-state processes", "fail", f"{len(stuck)} stuck process(es)", detail=[f"pid={p['pid']} {p['name']}" for p in stuck[:5]])
    return CheckResult("D-state processes", "warn", f"{len(stuck)} stuck process(es)", detail=[f"pid={p['pid']} {p['name']}" for p in stuck])


def _check_iowait() -> CheckResult:
    cfg = config_mod.get_config()
    iowait = sysinfo.get_iowait_percent()
    if iowait is None:
        return CheckResult("CPU iowait", "skip", "cannot read /proc/stat")
    msg = f"{iowait:.1f}%"
    if iowait >= cfg.iowait_fail_pct:
        return CheckResult("CPU iowait", "fail", msg)
    if iowait >= cfg.iowait_warn_pct:
        return CheckResult("CPU iowait", "warn", msg)
    return CheckResult("CPU iowait", "ok", msg)


def _check_tcp_retransmits() -> CheckResult:
    cfg = config_mod.get_config()
    rate = sysinfo.get_tcp_retransmit_rate()
    if rate is None:
        return CheckResult("TCP retransmits", "skip", "cannot read /proc/net/snmp")
    msg = f"{rate:.2f}% retransmitted (1s sample)"
    if rate >= cfg.tcp_retrans_fail_pct:
        return CheckResult("TCP retransmits", "fail", msg)
    if rate >= cfg.tcp_retrans_warn_pct:
        return CheckResult("TCP retransmits", "warn", msg)
    return CheckResult("TCP retransmits", "ok", msg)


def _check_restart_loops() -> CheckResult:
    cfg = config_mod.get_config()
    if not shutil.which("systemctl"):
        return CheckResult("restart loops", "skip", "systemctl unavailable")
    restarts = sysinfo.get_service_restart_counts(threshold=cfg.restart_warn_threshold)
    if not restarts:
        return CheckResult("restart loops", "ok", "no services restarting frequently")
    detail = [f"{r['name']} (NRestarts={r['restarts']})" for r in restarts]
    if any(r["restarts"] >= cfg.restart_fail_threshold for r in restarts):
        return CheckResult("restart loops", "fail", f"{len(restarts)} service(s) restart-looping", detail=detail)
    return CheckResult("restart loops", "warn", f"{len(restarts)} service(s) with multiple restarts", detail=detail)


def _check_network_errors() -> CheckResult:
    errors = sysinfo.get_network_errors()
    if not errors:
        return CheckResult("network errors", "ok", "no rx/tx errors or drops")
    detail = [f"{e['iface']}: rx_err={e['rx_errors']} tx_err={e['tx_errors']} " f"rx_drop={e['rx_dropped']} tx_drop={e['tx_dropped']}" for e in errors]
    severe = [e for e in errors if e["total"] >= 1000]
    if severe:
        return CheckResult("network errors", "warn", f"{len(severe)} interface(s) with high error counts (≥1000)", detail=detail)
    return CheckResult("network errors", "ok", "minor counters present (below threshold)", detail=detail)


def _check_psi() -> List[CheckResult]:
    """Pressure Stall Information — kernel 4.20+'s honest contention signal."""
    cfg = config_mod.get_config()
    results: List[CheckResult] = []
    for resource in ("cpu", "memory", "io"):
        data = sysinfo.get_pressure(resource)
        name = f"PSI {resource}"
        if data is None:
            results.append(CheckResult(name, "skip", "no /proc/pressure (kernel <4.20 or psi=0)"))
            continue
        avg10 = data.get("some", {}).get("avg10", 0.0)
        msg = f"some avg10={avg10:.1f}%"
        if avg10 >= cfg.psi_fail_pct:
            results.append(CheckResult(name, "fail", msg))
        elif avg10 >= cfg.psi_warn_pct:
            results.append(CheckResult(name, "warn", msg))
        else:
            results.append(CheckResult(name, "ok", msg))
    return results


def _check_kernel_taint() -> CheckResult:
    val = sysinfo.get_kernel_taint()
    if val is None:
        return CheckResult("kernel taint", "skip", "cannot read /proc/sys/kernel/tainted")
    if val == 0:
        return CheckResult("kernel taint", "ok", "clean")
    flags = sysinfo.decode_kernel_taint(val)
    bits = ", ".join(flags) if flags else f"raw=0x{val:x}"
    msg = f"tainted: 0x{val:x} ({bits})"
    # WARN (not FAIL) because non-zero taint is informative but rarely
    # actionable in the same way as a failed unit. A SOFTLOCKUP or MACHINE_CHECK
    # bit is more serious — escalate those.
    severe_bits = {"MACHINE_CHECK", "SOFTLOCKUP", "DIE", "BAD_PAGE"}
    if any(f in severe_bits for f in flags):
        return CheckResult("kernel taint", "fail", msg)
    return CheckResult("kernel taint", "warn", msg)


def _check_cert_expiry() -> CheckResult:
    cfg = config_mod.get_config()
    certs = sysinfo.get_certificate_expirations()
    if not certs:
        return CheckResult("cert expiry", "skip", "no certs found or openssl unavailable")
    soonest = certs[0]
    detail = [f"{c['days_left']:>4}d  {c['path']}" for c in certs[:10]]
    msg = f"soonest: {soonest['path']} in {soonest['days_left']}d  ({len(certs)} cert(s) scanned)"
    if soonest["days_left"] < cfg.cert_fail_days:
        return CheckResult("cert expiry", "fail", msg, detail=detail)
    if soonest["days_left"] < cfg.cert_warn_days:
        return CheckResult("cert expiry", "warn", msg, detail=detail)
    return CheckResult("cert expiry", "ok", msg, detail=detail)


def _check_conntrack() -> CheckResult:
    cfg = config_mod.get_config()
    usage = sysinfo.get_conntrack_usage()
    if usage is None:
        return CheckResult("conntrack", "skip", "nf_conntrack not loaded / not readable")
    count, max_v = usage
    if max_v <= 0:
        return CheckResult("conntrack", "skip", "conntrack max is zero")
    pct = int(round(100 * count / max_v))
    msg = f"{count} / {max_v} entries ({pct}%)"
    if pct >= cfg.conntrack_fail_pct:
        return CheckResult("conntrack", "fail", msg)
    if pct >= cfg.conntrack_warn_pct:
        return CheckResult("conntrack", "warn", msg)
    return CheckResult("conntrack", "ok", msg)


def _check_journal_disk() -> CheckResult:
    cfg = config_mod.get_config()
    bytes_used = sysinfo.get_journal_disk_usage()
    if bytes_used is None:
        return CheckResult("journal disk", "skip", "journalctl unavailable")
    gb = bytes_used / (1024**3)
    msg = f"{sysinfo.format_bytes(bytes_used)} used by journald"
    if gb >= cfg.journal_fail_gb:
        return CheckResult("journal disk", "fail", msg + f" (tip: `journalctl --vacuum-size={int(cfg.journal_warn_gb)}G`)")
    if gb >= cfg.journal_warn_gb:
        return CheckResult("journal disk", "warn", msg)
    return CheckResult("journal disk", "ok", msg)


def _check_pid_count() -> CheckResult:
    cfg = config_mod.get_config()
    count, pid_max = sysinfo.get_pid_count()
    if pid_max <= 0:
        return CheckResult("process count", "skip", "cannot read pid_max")
    pct = int(round(100 * count / pid_max))
    msg = f"{count} / {pid_max} ({pct}%)"
    if pct >= cfg.pid_fail_pct:
        return CheckResult("process count", "fail", msg)
    if pct >= cfg.pid_warn_pct:
        return CheckResult("process count", "warn", msg)
    return CheckResult("process count", "ok", msg)


CheckFn = Callable[[], Any]

# Short, stable names for `wtf audit --check <name>` and `wtf audit --list`.
# These are intentionally kebab-friendly and easier to type than CheckResult.name.
CHECK_REGISTRY: Dict[str, CheckFn] = {
    "uptime": _check_uptime,
    "system": _check_system_running,
    "load": _check_load,
    "iowait": _check_iowait,
    "psi": _check_psi,
    "tcp-retrans": _check_tcp_retransmits,
    "memory": _check_memory,
    "swap": _check_swap,
    "disks": _check_disks,
    "inodes": _check_inodes,
    "readonly-mounts": _check_readonly_mounts,
    "failed-units": _check_failed_units,
    "enabled-inactive": _check_enabled_inactive,
    "restart-loops": _check_restart_loops,
    "network-errors": _check_network_errors,
    "conntrack": _check_conntrack,
    "journal-disk": _check_journal_disk,
    "zombies": _check_zombies,
    "d-state": _check_stuck_processes,
    "oom": _check_oom_kills,
    "kernel-errors": _check_kernel_errors,
    "fds": _check_fds,
    "pids": _check_pid_count,
    "auth": _check_failed_auth,
    "time-sync": _check_time_sync,
    "updates": _check_pending_updates,
    "reboot": _check_reboot_required,
    "kernel-taint": _check_kernel_taint,
    "cert-expiry": _check_cert_expiry,
    "cron-daemon": _check_cron_daemon,
    "crontab": _check_user_crontabs,
    "docker": _check_docker,
    "hw-temp": _check_temperatures,
    "smart": _check_smart,
    "dns": _check_dns,
    "http-probes": _check_http_probes,
    "tcp-probes": _check_tcp_probes,
    "fail2ban": _check_fail2ban,
}


def render_html(results: List[CheckResult], host: Optional[str] = None, timestamp: Optional[str] = None) -> str:
    """Self-contained HTML for the audit. Inline CSS so it survives email/ticket paste."""
    from datetime import datetime, timezone
    from html import escape as _esc

    ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    host = host or "?"
    totals = summarize(results)

    color = {"ok": "#5cb85c", "warn": "#f0ad4e", "fail": "#d9534f", "skip": "#999"}
    rows = []
    for r in results:
        c = color.get(r.status, "#999")
        detail_html = ""
        if r.detail:
            items = "".join(f"<li>{_esc(d)}</li>" for d in r.detail)
            detail_html = f"<details><summary style='cursor:pointer;color:#888'>" f"{len(r.detail)} detail line(s)</summary>" f"<ul style='margin:4px 0'>{items}</ul></details>"
        rows.append(
            "<tr style='border-bottom:1px solid #eee'>"
            f"<td style='background:{c};color:#fff;font-weight:600;"
            f"padding:4px 8px;text-align:center;width:60px'>"
            f"{_esc(r.status.upper())}</td>"
            f"<td style='padding:4px 8px;font-weight:600;white-space:nowrap'>"
            f"{_esc(r.name)}</td>"
            f"<td style='padding:4px 8px;color:#444'>"
            f"{_esc(r.message)}{detail_html}</td>"
            "</tr>"
        )

    ok_c = color["ok"]
    warn_c = color["warn"]
    fail_c = color["fail"]
    skip_c = color["skip"]
    summary_html = (
        f"<span style='color:{ok_c}'>{totals['ok']} ok</span> · "
        f"<span style='color:{warn_c}'>{totals['warn']} warn</span> · "
        f"<span style='color:{fail_c}'>{totals['fail']} fail</span> · "
        f"<span style='color:{skip_c}'>{totals['skip']} skip</span>"
    )

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>wtf audit · {_esc(host)}</title></head>"
        "<body style='font-family:system-ui,sans-serif;color:#222;"
        "max-width:900px;margin:24px auto;padding:0 16px'>"
        f"<h2 style='margin:0 0 4px 0'>wtf audit · {_esc(host)}</h2>"
        f"<div style='color:#888;font-size:13px;margin-bottom:16px'>"
        f"{_esc(ts)} · {summary_html}</div>"
        "<table style='width:100%;border-collapse:collapse;font-size:14px'>" + "".join(rows) + "</table></body></html>\n"
    )


def render_prometheus(results: List[CheckResult]) -> str:
    """Render audit results in Prometheus textfile-collector format.

    Useful with node_exporter's --collector.textfile.directory: drop the output
    into /var/lib/node_exporter/wtf.prom and you get wtf_check_status and
    wtf_summary_total metrics scraped automatically.
    """
    lines = [
        "# HELP wtf_check_status Status of wtf check (0=ok, 1=warn, 2=fail, 3=skip)",
        "# TYPE wtf_check_status gauge",
    ]
    status_to_int = {"ok": 0, "warn": 1, "fail": 2, "skip": 3}
    for r in results:
        # Escape backslashes and double-quotes for the label value.
        safe = r.name.replace("\\", "\\\\").replace('"', '\\"')
        value = status_to_int.get(r.status, 3)
        lines.append(f'wtf_check_status{{name="{safe}"}} {value}')

    lines.append("# HELP wtf_summary_total Number of results by status")
    lines.append("# TYPE wtf_summary_total gauge")
    totals = summarize(results)
    for status_name in ("ok", "warn", "fail", "skip"):
        lines.append(f'wtf_summary_total{{status="{status_name}"}} {totals.get(status_name, 0)}')
    return "\n".join(lines) + "\n"


DEFAULT_CHECKS: List[CheckFn] = list(CHECK_REGISTRY.values())


def _plugin_to_check(path: str) -> CheckFn:
    """Wrap a plugin path as a CheckFn returning CheckResult."""

    def _run() -> CheckResult:
        pr = plugins_mod.run_plugin(path)
        return CheckResult(f"plugin:{pr.name}", pr.status, pr.message, detail=list(pr.detail))

    return _run


def _all_check_callables() -> Dict[str, CheckFn]:
    """Built-in checks merged with discovered plugins as `plugin:<name>` keys."""
    combined: Dict[str, CheckFn] = dict(CHECK_REGISTRY)
    for path in plugins_mod.discover_plugins():
        name = plugins_mod._plugin_name(path)
        combined[f"plugin:{name}"] = _plugin_to_check(path)
    return combined


def list_check_names() -> List[str]:
    """Return short names of all registered checks AND discovered plugins."""
    return list(_all_check_callables().keys())


def run_audit(names: Optional[List[str]] = None, ignore: Optional[List[str]] = None) -> List[CheckResult]:
    """Run all audit checks (built-ins + plugins) or a filtered subset by name.

    `names` filters by short keys from CHECK_REGISTRY or `plugin:<name>`.
    `ignore` excludes short-names AND skips results whose `name` matches
    (lets users say `--ignore "disk /mnt/Backup"` to skip a single mount).
    The config file's `[ignore]` section is merged into both filters.
    """
    cfg = config_mod.get_config()
    ignore_keys = set(ignore or []) | set(cfg.ignored_checks)
    ignore_results = set(cfg.ignored_result_names) | (set(ignore or []) - set(_all_check_callables().keys()))

    all_checks = _all_check_callables()
    if names:
        funcs: List[CheckFn] = []
        skips: List[CheckResult] = []
        for n in names:
            if n in ignore_keys:
                continue
            fn = all_checks.get(n)
            if fn is None:
                skips.append(CheckResult(n, "skip", f"unknown check '{n}'"))
            else:
                funcs.append(fn)
        results = _run_funcs(funcs)
        return [r for r in skips + results if r.name not in ignore_results]

    funcs = [fn for k, fn in all_checks.items() if k not in ignore_keys]
    results = _run_funcs(funcs)
    return [r for r in results if r.name not in ignore_results]


def _run_funcs(funcs: List[CheckFn]) -> List[CheckResult]:
    """Execute checks in parallel (config.parallel_workers) with per-check timeout.

    Output preserves submission order. A check exceeding the timeout becomes a
    skip-result; the underlying thread is left to finish (Python cannot kill
    threads safely) but the audit run is not blocked.
    """
    cfg = config_mod.get_config()
    if cfg.parallel_workers <= 1 or len(funcs) <= 1:
        return _run_funcs_serial(funcs, cfg.check_timeout_seconds)
    return _run_funcs_parallel(funcs, cfg.parallel_workers, cfg.check_timeout_seconds)


def _run_funcs_serial(funcs: List[CheckFn], timeout: float) -> List[CheckResult]:
    """Serial fallback (used when workers<=1 or only one check). No real timeout
    enforcement here — relies on subprocess timeouts inside each check."""
    results: List[CheckResult] = []
    for fn in funcs:
        try:
            outcome = fn()
        except Exception as exc:
            logger.warning(f"audit check {fn.__name__} failed: {type(exc).__name__}: {exc}")
            results.append(CheckResult(fn.__name__.lstrip("_"), "skip", f"check error: {exc}"))
            continue
        if isinstance(outcome, list):
            results.extend(outcome)
        else:
            results.append(outcome)
    return results


def _run_funcs_parallel(funcs: List[CheckFn], workers: int, timeout: float) -> List[CheckResult]:
    """Parallel execution preserving submission order, with per-check timeout."""
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FuturesTimeoutError

    results: List[CheckResult] = []
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        futures = [(fn, pool.submit(fn)) for fn in funcs]
        for fn, fut in futures:
            try:
                outcome = fut.result(timeout=timeout)
            except FuturesTimeoutError:
                logger.warning(f"audit check {fn.__name__} timed out after {timeout}s")
                results.append(CheckResult(fn.__name__.lstrip("_"), "skip", f"timeout (>{timeout:.0f}s)"))
                continue
            except Exception as exc:
                logger.warning(f"audit check {fn.__name__} failed: {type(exc).__name__}: {exc}")
                results.append(CheckResult(fn.__name__.lstrip("_"), "skip", f"check error: {exc}"))
                continue
            if isinstance(outcome, list):
                results.extend(outcome)
            else:
                results.append(outcome)
    return results


def filter_by_status(results: List[CheckResult], statuses: List[str]) -> List[CheckResult]:
    """Keep only results whose status is in `statuses`."""
    want = set(statuses)
    return [r for r in results if r.status in want]


def summarize(results: List[CheckResult]) -> Dict[str, int]:
    totals = {"ok": 0, "warn": 0, "fail": 0, "skip": 0}
    for r in results:
        totals[r.status] = totals.get(r.status, 0) + 1
    return totals
