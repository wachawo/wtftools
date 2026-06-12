#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Per-resource sections: `wtf disk|cpu|mem|net|io|who`.

Each section has a collect_* function returning a JSON-able dict (with
schema_version) and a pair of renderers: *_text (human view) and *_plain
(tab-separated, no headers — for grep/awk pipelines).
"""

import os
from typing import Any, Dict, List, Optional

from wtftools import colors, sysinfo

SCHEMA_VERSION = 1

# Classic commands each section is roughly equivalent to. Shown by
# `--show-commands` so users can learn (and verify) the traditional way.
EQUIVALENT_COMMANDS = {
    "disk": ["df -h", "df -i", "du -x -d2 --block-size=1 PATH | sort -rn | head"],
    "cpu": ["uptime", "top -bn1 | head", "ps aux --sort=-%cpu | head"],
    "mem": ["free -h", "ps aux --sort=-rss | head", "dmesg | grep -i 'out of memory'"],
    "net": ["ip -br addr", "ip route show default", "cat /etc/resolv.conf", "ss -tlnp"],
    "io": ["iostat -x 1 2", "cat /proc/pressure/io", "ps -eo pid,stat,comm | awk '$2 ~ /^D/'"],
    "who": ["who", "last -n 10", "journalctl -u ssh --since '24 hours ago' | grep -ci failed"],
}


def render_equivalents(section: str) -> str:
    """Dim footer listing the classic commands behind one section."""
    commands = EQUIVALENT_COMMANDS.get(section, [])
    lines = ["", colors.dim("  equivalent commands:")]
    lines.extend(colors.dim(f"    $ {command}") for command in commands)
    return "\n".join(lines)


def render_bar(percent: int, width: int = 20) -> str:
    """ASCII usage bar colored by severity."""
    percent = max(0, min(100, percent))
    filled = int(round(width * percent / 100))
    bar = "█" * filled + "·" * (width - filled)
    if percent >= 90:
        bar = colors.red(bar)
    elif percent >= 75:
        bar = colors.yellow(bar)
    else:
        bar = colors.green(bar)
    return f"[{bar}] {percent:3d}%"


def get_inode_percent(target: str) -> Optional[int]:
    """Percent of inodes used on the filesystem holding `target`."""
    try:
        stat = os.statvfs(target)
    except OSError:
        return None
    if stat.f_files == 0:
        return None
    used = stat.f_files - stat.f_ffree
    return int(round(100 * used / stat.f_files))


def pick_fullest_mount() -> str:
    """Mount point with the highest usage percent (default tree root)."""
    disks = sysinfo.get_disks()
    if not disks:
        return "/"
    fullest = max(disks, key=lambda d: d.get("percent", 0))
    return fullest["target"]


# Disk


def collect_disk(tree_root: Optional[str] = None, depth: int = 2, top: int = 15) -> Dict[str, Any]:
    readonly = set(sysinfo.get_readonly_mounts())
    mounts: List[Dict[str, Any]] = []
    for disk in sysinfo.get_disks():
        mounts.append(
            {
                "target": disk["target"],
                "used": disk["used"],
                "total": disk["total"],
                "percent": disk["percent"],
                "fstype": disk["fstype"],
                "readonly": disk["target"] in readonly,
                "inode_percent": get_inode_percent(disk["target"]),
            }
        )
    data: Dict[str, Any] = {"schema_version": SCHEMA_VERSION, "mounts": mounts}
    if tree_root is not None:
        data["tree"] = {
            "root": tree_root,
            "depth": depth,
            "entries": sysinfo.get_du_tree(tree_root, depth=depth, limit=top),
        }
    return data


def render_disk_text(data: Dict[str, Any]) -> str:
    out = [colors.section("DISK")]
    if not data["mounts"]:
        out.append(colors.dim("  no mounts found"))
    for m in data["mounts"]:
        label = m["target"] if len(m["target"]) <= 16 else "…" + m["target"][-15:]
        flags = []
        if m["readonly"]:
            flags.append(colors.red("READ-ONLY", bold=True))
        if m["inode_percent"] is not None and m["inode_percent"] >= 85:
            flags.append(colors.yellow(f"inodes {m['inode_percent']}%"))
        suffix = ("  " + " ".join(flags)) if flags else ""
        out.append(f"  {label:<16} {render_bar(m['percent'])}  {sysinfo.format_bytes(m['used'])} / {sysinfo.format_bytes(m['total'])}  {colors.dim(m['fstype'])}{suffix}")
    tree = data.get("tree")
    if tree is not None:
        out.append("")
        out.append(colors.section(f"LARGEST UNDER {tree['root']}"))
        if not tree["entries"]:
            out.append(colors.dim("  (nothing readable — try with sudo)"))
        for entry in tree["entries"]:
            out.append(f"  {sysinfo.format_bytes(entry['bytes']):>10}  {entry['path']}")
    return "\n".join(out)


def render_disk_plain(data: Dict[str, Any]) -> str:
    lines = []
    for m in data["mounts"]:
        inode = m["inode_percent"] if m["inode_percent"] is not None else "-"
        ro = "ro" if m["readonly"] else "rw"
        lines.append(f"mount\t{m['target']}\t{m['used']}\t{m['total']}\t{m['percent']}\t{m['fstype']}\t{ro}\t{inode}")
    tree = data.get("tree")
    if tree is not None:
        for entry in tree["entries"]:
            lines.append(f"tree\t{entry['bytes']}\t{entry['path']}")
    return "\n".join(lines)


# CPU


def collect_cpu() -> Dict[str, Any]:
    load1, load5, load15 = sysinfo.get_loadavg()
    cpus = sysinfo.get_cpu_count() or 1
    psi = sysinfo.get_pressure("cpu")
    return {
        "schema_version": SCHEMA_VERSION,
        "model": sysinfo.get_cpu_model(),
        "count": cpus,
        "loadavg": [load1, load5, load15],
        "load_per_cpu": round(load1 / cpus, 2),
        "iowait_percent": sysinfo.get_iowait_percent(),
        "psi_some_avg10": psi.get("some", {}).get("avg10") if psi else None,
        "top": sysinfo.get_top_processes(by="cpu", limit=5),
    }


def render_cpu_text(data: Dict[str, Any]) -> str:
    out = [colors.section("CPU")]
    out.append(f"  model   : {data['model']}  (x{data['count']})")
    load1, load5, load15 = data["loadavg"]
    out.append(f"  load    : {load1:.2f} {load5:.2f} {load15:.2f}  (per-cpu {data['load_per_cpu']:.2f})")
    if data["iowait_percent"] is not None:
        out.append(f"  iowait  : {data['iowait_percent']:.1f}%")
    if data["psi_some_avg10"] is not None:
        out.append(f"  psi     : some avg10={data['psi_some_avg10']:.1f}%")
    out.append("")
    out.append(colors.section("TOP BY CPU"))
    for proc in data["top"]:
        out.append(f"  {proc['cpu_percent']:5.1f}%  {str(proc.get('user', ''))[:12]:<12} {proc['pid']:>7}  {proc['name']}")
    return "\n".join(out)


def render_cpu_plain(data: Dict[str, Any]) -> str:
    load1, load5, load15 = data["loadavg"]
    lines = [
        f"model\t{data['model']}",
        f"cores\t{data['count']}",
        f"load\t{load1}\t{load5}\t{load15}",
        f"load_per_cpu\t{data['load_per_cpu']}",
    ]
    if data["iowait_percent"] is not None:
        lines.append(f"iowait\t{data['iowait_percent']:.1f}")
    if data["psi_some_avg10"] is not None:
        lines.append(f"psi_cpu\t{data['psi_some_avg10']}")
    for proc in data["top"]:
        lines.append(f"top\t{proc['pid']}\t{proc.get('user', '')}\t{proc['cpu_percent']}\t{proc['name']}")
    return "\n".join(lines)


# Memory


def collect_mem(since_hours: int = 24) -> Dict[str, Any]:
    mem = sysinfo.get_memory_summary()
    psi = sysinfo.get_pressure("memory")
    return {
        "schema_version": SCHEMA_VERSION,
        "memory": mem,
        "psi_some_avg10": psi.get("some", {}).get("avg10") if psi else None,
        "oom_kills": len(sysinfo.get_oom_events(hours=since_hours)),
        "oom_window_hours": since_hours,
        "top": sysinfo.get_top_processes(by="rss", limit=5),
    }


def render_mem_text(data: Dict[str, Any]) -> str:
    mem = data["memory"]
    out = [colors.section("MEMORY")]
    out.append(f"  ram     : {render_bar(mem['percent'])}  {sysinfo.format_bytes(mem['used'])} / {sysinfo.format_bytes(mem['total'])}")
    if mem["swap_total"]:
        out.append(f"  swap    : {render_bar(mem['swap_percent'])}  {sysinfo.format_bytes(mem['swap_used'])} / {sysinfo.format_bytes(mem['swap_total'])}")
    else:
        out.append(f"  swap    : {colors.dim('not configured')}")
    if data["psi_some_avg10"] is not None:
        out.append(f"  psi     : some avg10={data['psi_some_avg10']:.1f}%")
    oom = data["oom_kills"]
    oom_str = colors.red(str(oom), bold=True) if oom else colors.green("0")
    out.append(f"  oom     : {oom_str} kill(s) in last {data['oom_window_hours']}h")
    out.append("")
    out.append(colors.section("TOP BY RAM"))
    for proc in data["top"]:
        out.append(f"  {sysinfo.format_bytes(proc.get('rss', 0)):>8}  {str(proc.get('user', ''))[:12]:<12} {proc['pid']:>7}  {proc['name']}")
    return "\n".join(out)


def render_mem_plain(data: Dict[str, Any]) -> str:
    mem = data["memory"]
    lines = [
        f"ram\t{mem['used']}\t{mem['total']}\t{mem['percent']}",
        f"swap\t{mem['swap_used']}\t{mem['swap_total']}\t{mem['swap_percent']}",
    ]
    if data["psi_some_avg10"] is not None:
        lines.append(f"psi_memory\t{data['psi_some_avg10']}")
    lines.append(f"oom_kills\t{data['oom_kills']}")
    for proc in data["top"]:
        lines.append(f"top\t{proc['pid']}\t{proc.get('user', '')}\t{proc.get('rss', 0)}\t{proc['name']}")
    return "\n".join(lines)


# Network


def collect_net() -> Dict[str, Any]:
    ports = sysinfo.get_listening_ports()
    return {
        "schema_version": SCHEMA_VERSION,
        "interfaces": sysinfo.get_network_interfaces(),
        "gateway": sysinfo.get_default_gateway(),
        "dns": sysinfo.get_dns_servers(),
        "errors": sysinfo.get_network_errors(),
        "listening_tcp": sorted({p["port"] for p in ports}),
    }


def render_net_text(data: Dict[str, Any]) -> str:
    out = [colors.section("NETWORK")]
    for iface in data["interfaces"]:
        state = colors.green("up") if iface.get("up") else colors.red("down")
        ipv4 = ", ".join(iface.get("ipv4") or []) or colors.dim("(no ipv4)")
        out.append(f"  {iface['name']:<10} {state:<6} {ipv4}")
    gw = data["gateway"]
    out.append(f"  gateway : {gw['gateway']} via {gw['iface']}" if gw else f"  gateway : {colors.dim('(none)')}")
    dns = ", ".join(data["dns"]) or colors.dim("(none)")
    out.append(f"  dns     : {dns}")
    if data["errors"]:
        out.append("")
        out.append(colors.section("INTERFACE ERRORS"))
        for err in data["errors"]:
            out.append(f"  {err['iface']:<10} rx_err={err['rx_errors']} tx_err={err['tx_errors']} rx_drop={err['rx_dropped']} tx_drop={err['tx_dropped']}")
    if data["listening_tcp"]:
        shown = data["listening_tcp"][:20]
        more = len(data["listening_tcp"]) - len(shown)
        suffix = colors.dim(f"  (+{more} more)") if more > 0 else ""
        out.append(f"  {colors.dim('listening tcp:')} {', '.join(str(p) for p in shown)}{suffix}")
    return "\n".join(out)


def render_net_plain(data: Dict[str, Any]) -> str:
    lines = []
    for iface in data["interfaces"]:
        state = "up" if iface.get("up") else "down"
        ipv4 = ",".join(iface.get("ipv4") or []) or "-"
        lines.append(f"iface\t{iface['name']}\t{state}\t{ipv4}")
    gw = data["gateway"]
    if gw:
        lines.append(f"gateway\t{gw['gateway']}\t{gw['iface']}")
    for server in data["dns"]:
        lines.append(f"dns\t{server}")
    for err in data["errors"]:
        lines.append(f"errors\t{err['iface']}\t{err['rx_errors']}\t{err['tx_errors']}\t{err['rx_dropped']}\t{err['tx_dropped']}")
    for port in data["listening_tcp"]:
        lines.append(f"listen\t{port}")
    return "\n".join(lines)


# IO


def collect_io() -> Dict[str, Any]:
    psi = sysinfo.get_pressure("io")
    return {
        "schema_version": SCHEMA_VERSION,
        "psi_some_avg10": psi.get("some", {}).get("avg10") if psi else None,
        "iowait_percent": sysinfo.get_iowait_percent(),
        "devices": sysinfo.get_disk_io_per_device(),
        "stuck_processes": sysinfo.get_stuck_processes(),
    }


def render_io_text(data: Dict[str, Any]) -> str:
    out = [colors.section("IO")]
    if data["psi_some_avg10"] is not None:
        out.append(f"  psi     : some avg10={data['psi_some_avg10']:.1f}%")
    if data["iowait_percent"] is not None:
        out.append(f"  iowait  : {data['iowait_percent']:.1f}%")
    for dev in data["devices"]:
        out.append(f"  {dev['device']:<10} read {sysinfo.format_bytes(dev['read_bps']):>9}/s  write {sysinfo.format_bytes(dev['write_bps']):>9}/s  util {dev['util_percent']}%")
    if data["stuck_processes"]:
        out.append("")
        out.append(colors.section("D-STATE (IO-STUCK) PROCESSES"))
        for proc in data["stuck_processes"]:
            out.append(f"  {proc['pid']:>7}  {proc['name']}")
    return "\n".join(out)


def render_io_plain(data: Dict[str, Any]) -> str:
    lines = []
    if data["psi_some_avg10"] is not None:
        lines.append(f"psi_io\t{data['psi_some_avg10']}")
    if data["iowait_percent"] is not None:
        lines.append(f"iowait\t{data['iowait_percent']:.1f}")
    for dev in data["devices"]:
        lines.append(f"device\t{dev['device']}\t{dev['read_bps']}\t{dev['write_bps']}\t{dev['util_percent']}")
    for proc in data["stuck_processes"]:
        lines.append(f"dstate\t{proc['pid']}\t{proc['name']}")
    return "\n".join(lines)


# Who


def collect_who(since_hours: int = 24) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "logged_in": sysinfo.get_logged_in_users(),
        "last_logins": sysinfo.get_last_logins(limit=10),
        "failed_auth": sysinfo.get_failed_auth_count(hours=since_hours),
        "failed_auth_window_hours": since_hours,
    }


def render_who_text(data: Dict[str, Any]) -> str:
    out = [colors.section("WHO")]
    if not data["logged_in"]:
        out.append(colors.dim("  (nobody logged in)"))
    for user in data["logged_in"]:
        out.append(f"  {user['user']:<14} {user['tty']:<10} {user['host']:<20} since {user['since']}")
    failed = data["failed_auth"]
    failed_str = colors.yellow(str(failed), bold=True) if failed else colors.green("0")
    out.append(f"  failed auth: {failed_str} in last {data['failed_auth_window_hours']}h")
    if data["last_logins"]:
        out.append("")
        out.append(colors.section("RECENT LOGINS"))
        for line in data["last_logins"]:
            out.append(f"  {line}")
    return "\n".join(out)


def render_who_plain(data: Dict[str, Any]) -> str:
    lines = []
    for user in data["logged_in"]:
        lines.append(f"user\t{user['user']}\t{user['tty']}\t{user['host']}\t{user['since']}")
    lines.append(f"failed_auth\t{data['failed_auth']}")
    for line in data["last_logins"]:
        lines.append(f"last\t{line}")
    return "\n".join(lines)
