#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rendering of `wtf info` — quick summary of the server state."""

from typing import List

from wtftools import colors, sysinfo


def _bar(percent: int, width: int = 20) -> str:
    """Render an ASCII progress bar."""
    percent = max(0, min(100, percent))
    filled = int(round(width * percent / 100))
    empty = width - filled
    bar = "█" * filled + "·" * empty
    if percent >= 90:
        bar = colors.red(bar)
    elif percent >= 75:
        bar = colors.yellow(bar)
    else:
        bar = colors.green(bar)
    return f"[{bar}] {percent:3d}%"


def render_info_plain() -> str:
    """Tab-separated snapshot for shell pipelines (no colors, no headers)."""
    out: List[str] = []
    os_release = sysinfo.get_os_release()
    out.append(f"host\t{sysinfo.get_hostname()}")
    out.append(f"os\t{os_release.get('PRETTY_NAME') or os_release.get('NAME') or 'Linux'}")
    out.append(f"kernel\t{sysinfo.get_kernel()}")
    out.append(f"uptime_seconds\t{int(sysinfo.get_uptime_seconds())}")
    out.append(f"cpu\t{sysinfo.get_cpu_model()}\t{sysinfo.get_cpu_count()}")
    load1, load5, load15 = sysinfo.get_loadavg()
    out.append(f"load\t{load1}\t{load5}\t{load15}")
    mem = sysinfo.get_memory_summary()
    out.append(f"ram\t{mem['used']}\t{mem['total']}\t{mem['percent']}")
    out.append(f"swap\t{mem['swap_used']}\t{mem['swap_total']}\t{mem['swap_percent']}")
    for disk in sysinfo.get_disks():
        out.append(f"mount\t{disk['target']}\t{disk['used']}\t{disk['total']}\t{disk['percent']}\t{disk['fstype']}")
    for proc in sysinfo.get_top_processes(by="cpu", limit=5):
        out.append(f"top_cpu\t{proc['pid']}\t{proc.get('user') or ''}\t{proc.get('cpu_percent', 0.0)}\t{proc['name']}")
    for proc in sysinfo.get_top_processes(by="rss", limit=5):
        out.append(f"top_rss\t{proc['pid']}\t{proc.get('user') or ''}\t{proc.get('rss', 0)}\t{proc['name']}")
    for iface in sysinfo.get_network_interfaces():
        state = "up" if iface.get("up") else "down"
        ipv4 = ",".join(iface.get("ipv4") or []) or "-"
        out.append(f"iface\t{iface['name']}\t{state}\t{ipv4}")
    for port in sorted({p["port"] for p in sysinfo.get_listening_ports()}):
        out.append(f"listen\t{port}")
    return "\n".join(out)


def render_info() -> str:
    """Return a multi-line string with the system summary."""
    out: List[str] = []

    os_release = sysinfo.get_os_release()
    name = os_release.get("PRETTY_NAME") or os_release.get("NAME") or "Linux"
    kernel = sysinfo.get_kernel()
    hostname = sysinfo.get_hostname()
    uptime = sysinfo.format_duration(sysinfo.get_uptime_seconds())

    out.append(colors.section("SYSTEM"))
    out.append(f"  host    : {colors.bold(hostname)}")
    out.append(f"  os      : {name}")
    out.append(f"  kernel  : {kernel}")
    out.append(f"  uptime  : {uptime}")
    out.append(f"  cpu     : {sysinfo.get_cpu_model()}  (x{sysinfo.get_cpu_count()})")

    load1, load5, load15 = sysinfo.get_loadavg()
    cpus = sysinfo.get_cpu_count() or 1
    out.append(f"  load    : {load1:.2f} {load5:.2f} {load15:.2f}  (per-cpu {load1 / cpus:.2f})")

    out.append("")
    out.append(colors.section("MEMORY"))
    mem = sysinfo.get_memory_summary()
    out.append(f"  ram     : {_bar(mem['percent'])}  {sysinfo.format_bytes(mem['used'])} / {sysinfo.format_bytes(mem['total'])}")
    if mem["swap_total"]:
        out.append(f"  swap    : {_bar(mem['swap_percent'])}  {sysinfo.format_bytes(mem['swap_used'])} / {sysinfo.format_bytes(mem['swap_total'])}")
    else:
        out.append(f"  swap    : {colors.dim('not configured')}")

    out.append("")
    out.append(colors.section("DISK"))
    disks = sysinfo.get_disks()
    if not disks:
        out.append(colors.dim("  no mounts found"))
    else:
        for disk in disks:
            target = disk["target"]
            label = target if len(target) <= 16 else "…" + target[-15:]
            out.append(f"  {label:<16} {_bar(disk['percent'])}  {sysinfo.format_bytes(disk['used'])} / {sysinfo.format_bytes(disk['total'])}  {colors.dim(disk['fstype'])}")

    out.append("")
    out.append(colors.section("TOP BY CPU"))
    for proc in sysinfo.get_top_processes(by="cpu", limit=5):
        out.append(f"  {proc['cpu_percent']:5.1f}%  {str(proc.get('user', ''))[:12]:<12} {proc['pid']:>7}  {proc['name']}")

    out.append("")
    out.append(colors.section("TOP BY RAM"))
    for proc in sysinfo.get_top_processes(by="rss", limit=5):
        out.append(f"  {sysinfo.format_bytes(proc.get('rss', 0)):>8}  {str(proc.get('user', ''))[:12]:<12} {proc['pid']:>7}  {proc['name']}")

    out.append("")
    out.append(colors.section("NETWORK"))
    for iface in sysinfo.get_network_interfaces():
        state = colors.green("up") if iface.get("up") else colors.red("down")
        ipv4 = ", ".join(iface.get("ipv4") or []) or colors.dim("(no ipv4)")
        out.append(f"  {iface['name']:<10} {state:<6} {ipv4}")

    ports = sysinfo.get_listening_ports()
    if ports:
        unique_ports = sorted({p["port"] for p in ports})
        out.append(
            f"  {colors.dim('listening tcp:')} {', '.join(str(p) for p in unique_ports[:20])}"
            + (colors.dim(f"  (+{len(unique_ports) - 20} more)") if len(unique_ports) > 20 else "")
        )

    return "\n".join(out)
