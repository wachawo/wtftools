#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI entrypoint for `wtf` / `wtftools`."""

import argparse
import json
import logging
import os
import platform
import re
import shutil
import sys
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple

from wtftools import (
    __description__,
    __url__,
    __version__,
    colors,
    cron,
    sysinfo,
)
from wtftools import (
    audit as audit_mod,
)
from wtftools import (
    completion as completion_mod,
)
from wtftools import (
    config as config_mod,
)
from wtftools import (
    events as events_mod,
)
from wtftools import (
    explain as explain_mod,
)
from wtftools import (
    info as info_mod,
)
from wtftools import (
    llm as llm_mod,
)
from wtftools import (
    sections as sections_mod,
)
from wtftools import (
    snapshot as snapshot_mod,
)

logger = logging.getLogger(__name__)

LOGGING = {
    "format": "%(asctime)s.%(msecs)03d [%(levelname)s]: (%(name)s) %(message)s",
    "level": logging.WARNING,
    "datefmt": "%Y-%m-%d %H:%M:%S",
}
logging.basicConfig(**LOGGING)


STATUS_FILTERS = {
    "fail": ["fail"],
    "warn": ["warn", "fail"],  # "warn" implies "everything not-OK"
    "problems": ["warn", "fail"],
    "problem": ["warn", "fail"],  # singular alias for plural form
    "skip": ["skip"],
    "ok": ["ok"],
    "all": ["ok", "warn", "fail", "skip"],
}


def emit_section(args: argparse.Namespace, data: dict, render_text, render_plain, section: str = "") -> int:
    """Print one resource section in the requested format."""
    if args.format == "json":
        print(json.dumps(data, indent=2, default=str))
    elif args.format == "plain":
        print(render_plain(data))
    else:
        print(render_text(data))
        if section and getattr(args, "show_commands", False):
            print(sections_mod.render_equivalents(section))
    return 0


def cmd_completion(args: argparse.Namespace) -> int:
    """Print a shell-completion script (bash/zsh) or setup instructions."""
    shell = getattr(args, "shell", None)
    if shell == "bash":
        print(completion_mod.bash())
    elif shell == "zsh":
        print(completion_mod.zsh())
    else:
        print(completion_mod.instructions())
    return 0


def cmd_disk(args: argparse.Namespace) -> int:
    """Mount overview, or a folder usage breakdown of a path."""
    path = getattr(args, "path", None)
    tree = getattr(args, "tree", 0) or 0

    # No path and no expansion → the per-mount overview ("is there space?").
    if path is None and tree == 0:
        data = sections_mod.collect_disk()
        return emit_section(args, data, sections_mod.render_disk_text, sections_mod.render_disk_plain, section="disk")

    # Usage breakdown of a path (or the fullest mount when no path is given).
    root = path if path is not None else sections_mod.pick_fullest_mount()
    if not os.path.isdir(root):
        msg = f"not a directory: {root}"
        if getattr(args, "format", "text") == "json":
            print(json.dumps({"error": msg}))
        else:
            print(colors.red(msg))
        return 2
    data = sections_mod.collect_disk_usage(root, tree=tree, depth=args.depth, top=args.top)
    return emit_section(args, data, sections_mod.render_disk_usage_text, sections_mod.render_disk_usage_plain, section="disk")


def cmd_cpu(args: argparse.Namespace) -> int:
    """CPU model, load, iowait, PSI and top consumers."""
    data = sections_mod.collect_cpu()
    return emit_section(args, data, sections_mod.render_cpu_text, sections_mod.render_cpu_plain, section="cpu")


def cmd_mem(args: argparse.Namespace) -> int:
    """RAM/swap usage, PSI, OOM kills and top consumers."""
    data = sections_mod.collect_mem(since_hours=args.since)
    return emit_section(args, data, sections_mod.render_mem_text, sections_mod.render_mem_plain, section="mem")


def cmd_net(args: argparse.Namespace) -> int:
    """Interfaces, gateway, DNS, errors and listening ports."""
    data = sections_mod.collect_net()
    return emit_section(args, data, sections_mod.render_net_text, sections_mod.render_net_plain, section="net")


def cmd_io(args: argparse.Namespace) -> int:
    """Disk IO pressure, per-device rates and stuck processes."""
    data = sections_mod.collect_io()
    return emit_section(args, data, sections_mod.render_io_text, sections_mod.render_io_plain, section="io")


def cmd_who(args: argparse.Namespace) -> int:
    """Logged-in users, recent logins and failed auth count."""
    data = sections_mod.collect_who(since_hours=args.since)
    return emit_section(args, data, sections_mod.render_who_text, sections_mod.render_who_plain, section="who")


def cmd_temp(args: argparse.Namespace) -> int:
    """Hardware temperatures from /sys/class/hwmon sensors."""
    temps = sysinfo.get_temperatures()
    cfg = config_mod.get_config()

    if args.format == "json":
        payload = {
            "schema_version": 1,
            "warn_c": cfg.temp_warn_c,
            "fail_c": cfg.temp_fail_c,
            "sensors": temps,
        }
        print(json.dumps(payload, indent=2, default=str))
        return 0
    if args.format == "plain":
        for t in temps:
            print(f"{t['celsius']}\t{t['sensor']}\t{t['label']}")
        return 0

    if not temps:
        print(colors.dim("no /sys/class/hwmon sensors found (common inside VMs/containers)"))
        return 0

    print(colors.section("TEMP"))
    for t in sorted(temps, key=lambda t: t["celsius"], reverse=True):
        c = t["celsius"]
        cell = f"{c:5.1f}°C"
        if c >= cfg.temp_fail_c:
            cell = colors.red(cell)
        elif c >= cfg.temp_warn_c:
            cell = colors.yellow(cell)
        else:
            cell = colors.green(cell)
        print(f"  {cell}  {t['sensor']}/{t['label']}")
    hottest = max(temps, key=lambda t: t["celsius"])
    print(colors.dim(f"  hottest {hottest['celsius']:.1f}°C · warn >={cfg.temp_warn_c:.0f}°C · fail >={cfg.temp_fail_c:.0f}°C · {len(temps)} sensor(s)"))
    return 0


def cmd_top(args: argparse.Namespace) -> int:
    """Focused live top — by CPU or RSS, optionally filtered by user/name."""
    by = args.sort
    procs = sysinfo.get_top_processes(by=by, limit=args.limit * 4)
    if args.user:
        procs = [p for p in procs if str(p.get("user") or "").startswith(args.user)]
    if args.name:
        pattern = args.name.lower()
        procs = [p for p in procs if pattern in str(p.get("name") or "").lower()]
    procs = procs[: args.limit]

    if args.format == "plain":
        for p in procs:
            print(f"{p['pid']}\t{p.get('user') or ''}\t{p.get('cpu_percent', 0.0)}\t{p.get('rss', 0)}\t{p.get('name', '')}")
        return 0
    if args.format == "json":
        print(json.dumps(procs, indent=2, default=str))
        return 0

    if not procs:
        print(colors.dim("(no matching processes)"))
        return 0

    title = f"TOP {args.limit} BY {by.upper()}"
    if args.user:
        title += f" · user={args.user}"
    if args.name:
        title += f" · name~{args.name}"
    print(colors.section(title))
    print(f"  {'PID':>7}  {'USER':<12} {'CPU%':>5}  {'RSS':>8}  COMMAND")
    for p in procs:
        rss = sysinfo.format_bytes(p.get("rss", 0))
        cpu = p.get("cpu_percent", 0.0)
        user = str(p.get("user") or "")[:12]
        print(f"  {p['pid']:>7}  {user:<12} {cpu:5.1f}  {rss:>8}  {p.get('name', '')}")
    return 0


def cmd_ports(args: argparse.Namespace) -> int:
    """Listening sockets with owning process info.

    With a positional port number (`wtf port 5060`) it drills into that one
    port instead: PID, user, the exact executable file and working directory.
    """
    if getattr(args, "port", None) is not None:
        return _cmd_port_detail(args)
    try:
        import psutil  # type: ignore
    except ImportError:
        return _cmd_ports_fallback(args)

    import socket as _socket

    rows: List[dict] = []
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.status != psutil.CONN_LISTEN and conn.type != _socket.SOCK_DGRAM:
                continue
            if conn.type == _socket.SOCK_DGRAM and conn.status != "NONE":
                continue
            if not conn.laddr:
                continue
            proto = "udp" if conn.type == _socket.SOCK_DGRAM else "tcp"
            if args.proto != "all" and args.proto != proto:
                continue
            addr = conn.laddr.ip
            if args.public_only and (addr in ("127.0.0.1", "::1", "0.0.0.0", "::") or addr.startswith("127.")):
                # public_only means: exclude loopback specifically. We keep wildcard.
                if addr.startswith("127."):
                    continue
            pid = conn.pid
            name = ""
            user = ""
            if pid:
                try:
                    proc = psutil.Process(pid)
                    name = proc.name()
                    user = proc.username()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            rows.append(
                {
                    "port": conn.laddr.port,
                    "proto": proto,
                    "addr": addr,
                    "pid": pid,
                    "user": user,
                    "command": name,
                }
            )
    except Exception as exc:
        msg = f"failed to enumerate sockets: {type(exc).__name__}: {exc}"
        if args.format == "json":
            print(json.dumps({"error": msg}))
        else:
            print(colors.red(msg))
        return 1

    rows.sort(key=lambda r: (r["proto"], r["port"]))

    if args.format == "plain":
        for r in rows:
            print(f"{r['port']}\t{r['proto']}\t{r['addr']}\t{r['pid'] or '-'}\t{r['user'] or '-'}\t{r['command'] or '-'}")
        return 0
    if args.format == "json":
        print(json.dumps(rows, indent=2, default=str))
        return 0

    print(colors.section("LISTENING PORTS"))
    if not rows:
        print(colors.dim("  (none)"))
        return 0
    print(f"  {'PORT':>5}  {'PROTO':<5} {'ADDR':<20} {'PID':>7}  {'USER':<14} COMMAND")
    for r in rows:
        addr = r["addr"] or "*"
        pid_s = str(r["pid"]) if r["pid"] else "-"
        print(f"  {r['port']:>5}  {r['proto']:<5} {addr:<20} {pid_s:>7}  {(r['user'] or '-')[:14]:<14} {r['command']}")
    return 0


def _cmd_ports_fallback(args: argparse.Namespace) -> int:
    """Listening TCP ports via `ss` when psutil is unavailable (no PID/user info)."""
    if args.proto == "udp":
        msg = "udp listing requires psutil (install via `pip install wtftools[full]`)"
        if args.format == "json":
            print(json.dumps({"error": msg}))
        else:
            print(colors.red(msg))
        return 2
    rows = []
    for p in sysinfo.get_listening_ports():
        addr = p.get("addr") or "*"
        if args.public_only and addr.startswith("127."):
            continue
        rows.append({"port": p["port"], "proto": "tcp", "addr": addr, "pid": p.get("pid"), "user": "", "command": ""})
    rows.sort(key=lambda r: r["port"])
    if args.format == "plain":
        for r in rows:
            print(f"{r['port']}\t{r['proto']}\t{r['addr']}\t-\t-\t-")
        return 0
    if args.format == "json":
        print(json.dumps(rows, indent=2, default=str))
        return 0
    print(colors.section("LISTENING PORTS"))
    if not rows:
        print(colors.dim("  (none)"))
        return 0
    print(colors.dim("  (psutil missing — no PID/user info; `pip install wtftools[full]` for more)"))
    print(f"  {'PORT':>5}  {'PROTO':<5} {'ADDR':<20}")
    for r in rows:
        print(f"  {r['port']:>5}  {r['proto']:<5} {r['addr']:<20}")
    return 0


def _cmd_port_detail(args: argparse.Namespace) -> int:
    """Drill into a single port: which process holds it and which file it is."""
    port = args.port
    entries = sysinfo.get_port_processes(port)

    if args.format == "json":
        print(json.dumps({"schema_version": 1, "port": port, "processes": entries}, indent=2, default=str))
        return 0 if entries else 1
    if args.format == "plain":
        for e in entries:
            print(
                f"{e.get('proto', '')}\t{e.get('addr', '')}\t{e.get('state', '')}\t"
                f"{e.get('pid') or '-'}\t{e.get('user') or '-'}\t{e.get('command') or '-'}\t"
                f"{e.get('exe') or '-'}\t{e.get('cwd') or '-'}"
            )
        return 0 if entries else 1

    print(colors.section(f"PORT {port}"))
    if not entries:
        print(colors.dim("  (nothing is using this port)"))
        print(colors.dim("  note: run with sudo to see processes owned by other users"))
        return 1
    unreadable = colors.dim("(unreadable — try sudo)")
    for e in entries:
        head = f"{e.get('proto', '?')} {e.get('addr', '')}"
        if e.get("state"):
            head += f" ({e['state']})"
        print(f"  {colors.bold(head)}")
        print(f"    pid     : {e.get('pid') or '-'}")
        print(f"    user    : {e.get('user') or '-'}")
        print(f"    command : {e.get('command') or '-'}")
        if e.get("cmdline"):
            print(f"    cmdline : {e['cmdline']}")
        print(f"    exe     : {e.get('exe') or unreadable}")
        print(f"    cwd     : {e.get('cwd') or unreadable}")
    return 0


def cmd_docker(args: argparse.Namespace) -> int:
    """Where a container came from: compose project working dir + config files."""
    if not shutil.which("docker"):
        msg = "docker not available on this host"
        if args.format == "json":
            print(json.dumps({"error": msg}))
        else:
            print(colors.red(msg))
        return 2

    if args.name:
        info = sysinfo.get_docker_container_origin(args.name)
        if info is None:
            msg = f"container '{args.name}' not found (or docker not accessible)"
            if args.format == "json":
                print(json.dumps({"error": msg}))
            else:
                print(colors.red(msg))
            return 1
        items = [info]
    else:
        items = sysinfo.get_docker_containers()
        if items is None:
            msg = "cannot list containers (is the docker daemon running and accessible?)"
            if args.format == "json":
                print(json.dumps({"error": msg}))
            else:
                print(colors.red(msg))
            return 1

    if args.format == "json":
        print(json.dumps({"schema_version": 1, "containers": items}, indent=2, default=str))
        return 0

    def _bytes_cell(value: Optional[int]) -> str:
        return str(value) if isinstance(value, int) else "-"

    if args.format == "plain":
        for c in items:
            print(
                f"{c['name']}\t{c.get('status', '')}\t{c.get('image', '')}\t"
                f"{c.get('compose_project') or '-'}\t{c.get('compose_service') or '-'}\t"
                f"{c.get('working_dir') or '-'}\t{c.get('config_files') or '-'}\t"
                f"{_bytes_cell(c.get('image_bytes'))}\t{_bytes_cell(c.get('container_bytes'))}\t"
                f"{_bytes_cell(c.get('logs_bytes'))}"
            )
        return 0

    # Sizes are formatted with decimal units so they line up with `docker`.
    def _bytes_human(value: Optional[int]) -> str:
        return sysinfo.format_bytes_si(value) if isinstance(value, int) else "?"

    if args.name:
        c = items[0]
        print(colors.section(c["name"]))
        print(f"  image        : {c.get('image', '')}")
        print(f"  status       : {c.get('status', '')}")
        if c.get("working_dir"):
            project = c.get("compose_project") or "?"
            service = c.get("compose_service") or "?"
            print(f"  compose      : {project} / {service}")
            print(f"  working dir  : {colors.bold(c['working_dir'])}")
            if c.get("config_files"):
                print(f"  config files : {c['config_files']}")
        else:
            print(colors.dim("  not a compose container — no host working dir recorded"))
        print(f"  image size   : {_bytes_human(c.get('image_bytes'))}")
        print(f"  container    : {_bytes_human(c.get('container_bytes'))} (writable layer)")
        logs = c.get("logs_bytes")
        if isinstance(logs, int):
            print(f"  logs         : {_bytes_human(logs)}")
        else:
            print(colors.dim("  logs         : ? (run with sudo to read the log file)"))
        return 0

    print(colors.section("DOCKER"))
    if not items:
        print(colors.dim("  (no running containers)"))
        return 0
    name_width = max((len(c["name"]) for c in items), default=12)
    header = f"  {'NAME'.ljust(name_width)}  {'STATUS':<9} {'IMAGE':>8} {'CONTNR':>8} {'LOGS':>8}  WORKING DIR"
    print(colors.bold(header))
    # Same image used by many containers is counted once (dedupe by image id).
    unique_images: Dict[str, int] = {}
    tot_cnt = 0
    cnt_known = False
    tot_log = 0
    log_known = False
    for c in items:
        wd = c.get("working_dir") or colors.dim("(not compose)")
        img, cnt, log = c.get("image_bytes"), c.get("container_bytes"), c.get("logs_bytes")
        if isinstance(img, int):
            unique_images[c.get("image_id") or c.get("image") or c["name"]] = img
        if isinstance(cnt, int):
            tot_cnt += cnt
            cnt_known = True
        if isinstance(log, int):
            tot_log += log
            log_known = True
        print(f"  {c['name'].ljust(name_width)}  {c.get('status', ''):<9} {_bytes_human(img):>8} {_bytes_human(cnt):>8} {_bytes_human(log):>8}  {wd}")
    if len(items) > 1:
        # Image total dedupes by id so one image is not counted per container.
        # Different images can still share base layers on disk, so this is the
        # logical unique-images total, not exact disk — `docker system df`
        # reports the real layer-deduplicated figure. Container writable layers
        # and logs are per-container, so those totals are exact.
        img_cell = sysinfo.format_bytes_si(sum(unique_images.values())) if unique_images else "?"
        cnt_cell = sysinfo.format_bytes_si(tot_cnt) if cnt_known else "?"
        log_cell = sysinfo.format_bytes_si(tot_log) if log_known else "?"
        print(colors.bold(f"  {'TOTAL'.ljust(name_width)}  {'':<9} {img_cell:>8} {cnt_cell:>8} {log_cell:>8}"))
        # The image total dedupes by id, but different images still share base
        # layers on disk, so it overstates real usage. Surface the true
        # layer-deduplicated figure from `docker system df`.
        df = sysinfo.get_docker_disk_usage()
        images_row = next((r for r in df if r.get("type", "").lower().startswith("image")), None) if df else None
        if images_row:
            notes = [f"IMAGE total is logical (images share layers); real disk {images_row['size']}, {images_row['reclaimable']} reclaimable — docker system df"]
        else:
            notes = ["IMAGE total is logical (images share base layers); `docker system df` for real disk"]
        if log_known:
            notes.append("logs cap with max-size")
        else:
            notes.append("logs need sudo")
        notes.append("decimal units, like docker")
        print(colors.dim("  note: " + "; ".join(notes)))
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    """Standalone diff: compare a stored snapshot against the latest live audit.

    Without arguments → latest-saved vs current. With --snapshot N → Nth-most-
    recent vs current. With --against PATH1 PATH2 → two snapshot files.
    """
    if args.against:
        if len(args.against) != 2:
            print(colors.red("--against takes exactly 2 paths"))
            return 2
        old_path, new_path = args.against
        old = snapshot_mod.load_snapshot(old_path)
        new_data = snapshot_mod.load_snapshot(new_path)
        if old is None or new_data is None:
            print(colors.red("cannot read one or both snapshot files"))
            return 1
        # rebuild CheckResult list from new snapshot
        new_results = [
            audit_mod.CheckResult(name=r["name"], status=r["status"], message=r.get("message", ""), detail=r.get("detail", []) or []) for r in new_data.get("results", [])
        ]
        return _render_diff(args, old, new_results, old_path=old_path, new_path=new_path)

    # Pick the snapshot to diff against: latest by default, or N back.
    paths = snapshot_mod.list_snapshots()
    if not paths:
        if args.format == "json":
            print(json.dumps({"diff": [], "reason": "no snapshots"}, indent=2))
        else:
            print(colors.dim("no snapshots yet — run `wtf audit --save` to create one"))
        return 0
    idx = max(0, len(paths) - 1 - args.snapshot)
    chosen = paths[idx]
    old = snapshot_mod.load_snapshot(chosen)
    if old is None:
        print(colors.red(f"cannot read {chosen}"))
        return 1
    # Run a fresh audit to get the "new" side
    args.check = None
    args.ignore = []
    args.since = 24
    args.serial = False
    args.check_timeout = None
    args.only = None
    results, _ = _run_audit_once(args)
    return _render_diff(args, old, results, old_path=chosen)


def _render_diff(args: argparse.Namespace, old: dict, new_results: List[audit_mod.CheckResult], old_path: Optional[str] = None, new_path: Optional[str] = None) -> int:
    events = snapshot_mod.diff_snapshots(old, new_results)
    if args.format == "json":
        print(
            json.dumps(
                {
                    "old": old_path,
                    "new": new_path,
                    "old_timestamp": old.get("timestamp"),
                    "changes": events,
                },
                indent=2,
                default=str,
            )
        )
        return 0
    label = old.get("timestamp", "previous") if old_path else "previous"
    if old_path:
        label += f"  ({os.path.basename(old_path)})"
    print(colors.section(f"DIFF vs {label}"))
    if not events:
        print(colors.green("  (nothing changed)"))
        return 0
    kind_marker = {
        "regression": colors.red("REG ", bold=True),
        "worsened": colors.yellow("WRSE", bold=True),
        "new": colors.cyan("NEW ", bold=True),
        "improved": colors.green("IMP ", bold=True),
        "recovery": colors.green("FIX ", bold=True),
        "removed": colors.dim("GONE"),
    }
    name_width = max((len(e["name"]) for e in events), default=20)
    for ev in events:
        marker = kind_marker.get(ev["kind"], ev["kind"])
        if ev["kind"] == "new":
            transition = colors.dim(f"        ↘ {ev['new_status']}")
        elif ev["kind"] == "removed":
            transition = colors.dim(f"{ev['old_status']} ↗")
        else:
            transition = f"{ev['old_status']:>4} → {ev['new_status']:<4}"
        msg = ev.get("new_message") or ev.get("old_message") or ""
        print(f"  {marker} {ev['name'].ljust(name_width)}  {transition}   {colors.dim(msg)}")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    """List stored audit snapshots with summaries."""
    paths = snapshot_mod.list_snapshots()
    if args.format == "json":
        payload = []
        for p in paths:
            data = snapshot_mod.load_snapshot(p) or {}
            results = data.get("results", []) or []
            counts = {"ok": 0, "warn": 0, "fail": 0, "skip": 0}
            for r in results:
                counts[r.get("status", "skip")] = counts.get(r.get("status", "skip"), 0) + 1
            payload.append(
                {
                    "path": p,
                    "timestamp": data.get("timestamp"),
                    "host": data.get("host"),
                    "totals": counts,
                }
            )
        print(json.dumps(payload, indent=2, default=str))
        return 0
    if not paths:
        print(colors.dim("no snapshots yet — run `wtf audit --save` to create one"))
        print(colors.dim(f"snapshot dir: {snapshot_mod.default_snapshot_dir()}"))
        return 0
    print(colors.section("HISTORY"))
    print(colors.dim(f"  snapshot dir: {snapshot_mod.default_snapshot_dir()}"))
    print(colors.dim(f"  {len(paths)} snapshot(s) — newest first\n"))
    for path in reversed(paths[-args.limit :]):
        data = snapshot_mod.load_snapshot(path)
        if data is None:
            print(f"  {colors.red('(corrupt)')} {path}")
            continue
        results = data.get("results", []) or []
        ok = sum(1 for r in results if r.get("status") == "ok")
        warn = sum(1 for r in results if r.get("status") == "warn")
        fail = sum(1 for r in results if r.get("status") == "fail")
        skip = sum(1 for r in results if r.get("status") == "skip")
        ts = data.get("timestamp", "?")
        summary = f"{colors.green(f'{ok} ok')} · {colors.yellow(f'{warn} warn')} · {colors.red(f'{fail} fail')} · {colors.dim(f'{skip} skip')}"
        print(f"  {colors.cyan(ts):<35} {summary}  {colors.dim(os.path.basename(path))}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    if args.format == "plain":
        print(info_mod.render_info_plain())
        return 0
    if args.format == "json":
        from wtftools import sysinfo

        payload = {
            "schema_version": 1,
            "hostname": sysinfo.get_hostname(),
            "os": sysinfo.get_os_release(),
            "kernel": sysinfo.get_kernel(),
            "uptime_seconds": sysinfo.get_uptime_seconds(),
            "cpu_model": sysinfo.get_cpu_model(),
            "cpu_count": sysinfo.get_cpu_count(),
            "loadavg": sysinfo.get_loadavg(),
            "memory": sysinfo.get_memory_summary(),
            "disks": sysinfo.get_disks(),
            "top_cpu": sysinfo.get_top_processes(by="cpu", limit=5),
            "top_rss": sysinfo.get_top_processes(by="rss", limit=5),
            "network": sysinfo.get_network_interfaces(),
            "listening_ports": sysinfo.get_listening_ports(),
        }
        print(json.dumps(payload, indent=2, default=str))
        return 0

    print(info_mod.render_info())
    return 0


def _print_audit_results(results: List[audit_mod.CheckResult], verbose: bool) -> None:
    name_width = max((len(r.name) for r in results), default=20)
    for result in results:
        marker = colors.status_marker(result.status)
        print(f"{marker} {result.name.ljust(name_width)}  {result.message}")
        if verbose and result.detail:
            for line in result.detail:
                print(f"        {colors.dim('└')} {line}")


def _run_audit_once(args: argparse.Namespace) -> Tuple[List[audit_mod.CheckResult], int]:
    """Run audit once based on parsed args. Returns (results, exit_code)."""
    if getattr(args, "since", None):
        audit_mod.set_since_hours(args.since)
    # CLI overrides for parallel/timeout knobs live on the active Config.
    cfg = config_mod.get_config()
    if getattr(args, "serial", False):
        cfg.parallel_workers = 1
    if getattr(args, "check_timeout", None) is not None:
        cfg.check_timeout_seconds = float(args.check_timeout)
    names = args.check or None
    ignore = args.ignore or None
    results = audit_mod.run_audit(names=names, ignore=ignore)
    only = getattr(args, "only", None)
    if only:
        statuses = STATUS_FILTERS.get(only, [only])
        results = audit_mod.filter_by_status(results, statuses)
    return results, 0


def cmd_audit(args: argparse.Namespace) -> int:
    if getattr(args, "list_checks", False):
        for name in audit_mod.list_check_names():
            print(name)
        return 0

    results, _ = _run_audit_once(args)
    if getattr(args, "alert", None):
        _maybe_fire_alert(args, results)
    if getattr(args, "save", False):
        path = snapshot_mod.save_snapshot(results, host=sysinfo.get_hostname())
        if path and args.format == "text":
            print(colors.dim(f"snapshot saved: {path}"))
    if getattr(args, "brief", False):
        return _emit_brief(results)
    if not results:
        if args.format == "json":
            print(json.dumps({"results": [], "summary": audit_mod.summarize([])}, indent=2, default=str))
        else:
            print(colors.section("AUDIT"))
            print(colors.dim("  (no checks matched the filter)"))
        return 0
    return _emit_audit(args, results)


def _emit_audit(args: argparse.Namespace, results: List[audit_mod.CheckResult]) -> int:
    output_path = getattr(args, "output", None)
    sink = _OutputSink(output_path)
    try:
        with sink:
            return _emit_audit_to(args, results, sink)
    except OSError as exc:
        print(colors.red(f"cannot write {output_path}: {exc}"))
        return 1


def _emit_audit_to(args, results, sink) -> int:
    """Render audit results into `sink`. Sink is a file-like wrapper."""
    if args.format == "prometheus":
        sink.write(audit_mod.render_prometheus(results))
        return _audit_exit_code(args, results)
    if args.format == "html":
        sink.write(audit_mod.render_html(results, host=sysinfo.get_hostname()))
        return _audit_exit_code(args, results)
    if args.format == "csv":
        import csv

        writer = csv.writer(sink.stream)
        writer.writerow(["name", "status", "message", "detail"])
        for r in results:
            writer.writerow([r.name, r.status, r.message, " | ".join(r.detail)])
        return _audit_exit_code(args, results)
    if args.format == "plain":
        # Tab-separated, no headers/colors/summary — best for shell pipelines:
        #   wtf audit --format plain | awk '$1=="fail"'
        for r in results:
            sink.writeln(f"{r.status}\t{r.name}\t{r.message}")
        return _audit_exit_code(args, results)
    if args.format == "json":
        payload = {
            "results": [asdict(r) for r in results],
            "summary": audit_mod.summarize(results),
        }
        sink.write(json.dumps(payload, indent=2, default=str) + "\n")
    else:
        sink.writeln(colors.section("AUDIT"))
        for line in _audit_text_lines(results, verbose=args.verbose):
            sink.writeln(line)
        totals = audit_mod.summarize(results)
        sink.writeln("")
        summary_parts = [
            colors.green(f"{totals['ok']} ok", bold=True),
            colors.yellow(f"{totals['warn']} warn", bold=True),
            colors.red(f"{totals['fail']} fail", bold=True),
            colors.dim(f"{totals['skip']} skip"),
        ]
        sink.writeln(f"  Summary: {' · '.join(summary_parts)}")
    return _audit_exit_code(args, results)


class _OutputSink:
    """File-or-stdout writer used by `--output FILE`. Context-managed."""

    def __init__(self, path: Optional[str]):
        self.path = path
        self.stream = sys.stdout
        self._opened = False

    def __enter__(self):
        if self.path:
            # When writing to a file, drop ANSI escapes for sanity.
            colors.init_colors(force_no_color=True)
            self.stream = open(self.path, "w", encoding="utf-8", newline="")
            self._opened = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._opened:
            self.stream.close()
        return False

    def write(self, text: str) -> None:
        self.stream.write(text)

    def writeln(self, text: str = "") -> None:
        self.stream.write(text + "\n")


def _audit_text_lines(results, verbose: bool):
    """Yield rendered audit lines (the same content `_print_audit_results` prints)."""
    name_width = max((len(r.name) for r in results), default=20)
    for result in results:
        marker = colors.status_marker(result.status)
        yield f"{marker} {result.name.ljust(name_width)}  {result.message}"
        if verbose and result.detail:
            for line in result.detail:
                yield f"        {colors.dim('└')} {line}"


def _audit_exit_code(args: argparse.Namespace, results: List[audit_mod.CheckResult]) -> int:
    failed = sum(1 for r in results if r.status == "fail")
    warns = sum(1 for r in results if r.status == "warn")
    if getattr(args, "exit_zero", False):
        return 0
    if failed:
        return 2
    if getattr(args, "strict", False) and warns:
        return 1
    return 0


def _maybe_fire_alert(args: argparse.Namespace, results: List[audit_mod.CheckResult]) -> None:
    """Run the user's alert command when audit severity passes the threshold.

    The audit summary (text or JSON depending on --format) is piped into the
    command's stdin. Useful for cron-driven monitoring without bundling a
    notification client.
    """
    import subprocess

    totals = audit_mod.summarize(results)
    fail = totals.get("fail", 0)
    warn = totals.get("warn", 0)
    threshold = getattr(args, "alert_on", "fail")
    should_fire = (threshold == "fail" and fail > 0) or (threshold == "warn" and (fail > 0 or warn > 0)) or (threshold == "any" and (fail + warn > 0))
    if not should_fire:
        return

    summary_lines = []
    for r in results:
        if r.status in ("fail", "warn"):
            summary_lines.append(f"[{r.status.upper()}] {r.name}: {r.message}")
    body = "\n".join(summary_lines) + "\n" if summary_lines else ""

    env = dict(os.environ)
    env["WTF_FAIL_COUNT"] = str(fail)
    env["WTF_WARN_COUNT"] = str(warn)
    env["WTF_HOST"] = sysinfo.get_hostname()
    try:
        subprocess.run(args.alert, shell=True, input=body, text=True, timeout=30, env=env, check=False)
    except subprocess.TimeoutExpired:
        logger.warning("alert command timed out")
    except Exception as exc:
        logger.warning(f"alert command failed: {type(exc).__name__}: {exc}")


def _emit_brief(results: List[audit_mod.CheckResult]) -> int:
    """One-line summary for MOTDs / ssh-login banners."""
    totals = audit_mod.summarize(results)
    problems = [r for r in results if r.status in ("fail", "warn")]
    if not problems:
        print(colors.green(f"wtf: all good · {totals['ok']} ok · {totals['skip']} skip", bold=True))
        return 0

    def _short(text: str, limit: int = 40) -> str:
        text = text.replace("\n", " ").strip()
        return text if len(text) <= limit else text[: limit - 1] + "…"

    parts = [f"{r.name}: {_short(r.message)}" for r in problems[:3]]
    if len(problems) > 3:
        parts.append(f"+{len(problems) - 3} more")
    head = f"wtf: {totals['fail']} fail, {totals['warn']} warn"
    line = f"{head} — {' · '.join(parts)}"
    if totals["fail"]:
        print(colors.red(line, bold=True))
        return 2
    print(colors.yellow(line, bold=True))
    return 1


def cmd_explain(args: argparse.Namespace) -> int:
    """Turn audit findings into per-check actionable suggestions or an LLM prompt."""
    # Reuse the audit pipeline so --check/--ignore/--since all work for free.
    results, _ = _run_audit_once(args)

    if getattr(args, "llm", None):
        return _explain_via_llm(args, results)

    if args.prompt:
        host = sysinfo.get_hostname()
        print(explain_mod.render_prompt(results, host=host))
        return 0

    deep = getattr(args, "deep", False)
    suggestions = explain_mod.explain_results(results, include_ok=args.all, deep=deep)
    if args.format == "json":
        payload = [{"name": s.name, "status": s.status, "message": s.message, "advice": s.advice, "investigation": s.investigation} for s in suggestions]
        print(json.dumps(payload, indent=2, default=str))
        return 0

    if not suggestions:
        print(colors.green("wtf explain: nothing to explain — no WARN/FAIL findings."))
        return 0

    print(colors.section("EXPLAIN"))
    for s in suggestions:
        marker = colors.status_marker(s.status)
        print(f"{marker} {colors.bold(s.name)}  {colors.dim(s.message)}")
        # Wrap advice loosely; keep it readable on 80-col terminals.
        for paragraph in s.advice.split("\n"):
            print(f"      {paragraph}")
        if s.investigation:
            print(f"      {colors.dim('# investigation')}")
            for line in s.investigation:
                print(f"      {line}")
        print("")
    return 0


def _explain_via_llm(args: argparse.Namespace, results: List[audit_mod.CheckResult]) -> int:
    """Render the structured prompt, ship it through the chosen LLM backend."""
    host = sysinfo.get_hostname()
    prompt = explain_mod.render_prompt(results, host=host)
    text, info = llm_mod.call_llm(args.llm, prompt, model=args.llm_model, timeout=args.llm_timeout)
    if text is None:
        msg = f"LLM call failed: {info}"
        if args.format == "json":
            print(json.dumps({"error": msg, "backend": args.llm}))
        else:
            print(colors.red(msg))
        return 2
    if args.format == "json":
        print(json.dumps({"backend": args.llm, "via": info, "advice": text}, indent=2))
        return 0
    print(colors.section(f"EXPLAIN · {args.llm}"))
    if info:
        print(colors.dim(f"  {info}"))
    print("")
    print(text.rstrip())
    return 0


def cmd_events(args: argparse.Namespace) -> int:
    """Chronological timeline of significant host events."""
    kinds = args.kind or None
    events = events_mod.collect_events(hours=args.since, kinds=kinds)
    if args.limit:
        events = events[: args.limit]

    if args.format == "plain":
        for e in events:
            print(f"{e.iso()}\t{e.kind}\t{e.message}")
        return 0
    if args.format == "json":
        payload = {
            "schema_version": 1,
            "since_hours": args.since,
            "kinds": list(kinds) if kinds else list(events_mod.EVENT_KINDS),
            "events": [{"timestamp": e.timestamp, "iso": e.iso(), "kind": e.kind, "message": e.message, "detail": e.detail} for e in events],
        }
        print(json.dumps(payload, indent=2, default=str))
        return 0

    _print_events_text(events, args.since)
    return 0


def _print_events_text(events: list, since_hours: int) -> None:
    """Render the events timeline (shared by `wtf events` and `wtf daily`)."""
    print(colors.section(f"EVENTS · last {since_hours}h"))
    if not events:
        print(colors.dim("  (no events in this window)"))
        return

    kind_icon = {
        "reboot": colors.cyan("⟲ ", bold=True),
        "oom": colors.red("✗ ", bold=True),
        "failed-unit": colors.red("✗ ", bold=True),
        "kernel-err": colors.yellow("⚠ ", bold=True),
        "auth-fail": colors.yellow("⚠ ", bold=True),
        "login": colors.dim("ⓘ "),
    }
    kind_width = max((len(e.kind) for e in events), default=10)
    for e in events:
        icon = kind_icon.get(e.kind, "• ")
        msg = e.message
        if len(msg) > 110:
            msg = msg[:109] + "…"
        print(f"  {colors.dim(e.iso())}  {icon}{e.kind.ljust(kind_width)}  {msg}")


def cmd_logs(args: argparse.Namespace) -> int:
    """Recent ERROR-level (and worse) journal entries grouped by service."""
    import collections

    if not shutil.which("journalctl"):
        msg = "journalctl not available on this host"
        if args.format == "json":
            print(json.dumps({"error": msg}))
        else:
            print(colors.red(msg))
        return 2
    rc, out, _ = sysinfo.run(
        ["journalctl", "-p", args.priority, "--since", args.since, "-o", "json", "--no-pager", "-q"],
        timeout=20,
    )
    if rc != 0:
        msg = f"journalctl failed (rc={rc})"
        if args.format == "json":
            print(json.dumps({"error": msg}))
        else:
            print(colors.red(msg))
        return 1

    by_unit: Dict[str, List[str]] = collections.defaultdict(list)
    for line in out.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        unit = entry.get("_SYSTEMD_UNIT") or entry.get("SYSLOG_IDENTIFIER") or entry.get("_COMM") or "(unknown)"
        message = entry.get("MESSAGE", "")
        if isinstance(message, list):
            try:
                message = bytes(message).decode("utf-8", errors="replace")
            except Exception:
                message = str(message)
        by_unit[unit].append(str(message).strip())

    if args.format == "plain":
        for unit, msgs in sorted(by_unit.items(), key=lambda kv: -len(kv[1])):
            unit_short = unit.replace(".service", "")
            for m in msgs:
                print(f"{unit_short}\t{m}")
        return 0
    if args.format == "json":
        payload = {"schema_version": 1, "since": args.since, "priority": args.priority, "by_unit": dict(by_unit)}
        print(json.dumps(payload, indent=2))
        return 0

    print(colors.section(f"LOGS — last {args.since}, priority {args.priority}+"))
    if not by_unit:
        print(colors.green("  (none)"))
        return 0
    sorted_units = sorted(by_unit.items(), key=lambda kv: -len(kv[1]))
    total = sum(len(v) for v in by_unit.values())
    print(colors.bold(f"  {total} entries across {len(by_unit)} unit(s):"))
    for unit, msgs in sorted_units[: args.units]:
        unit_short = unit.replace(".service", "")
        print(f"  {colors.cyan(unit_short)}  {colors.dim(f'({len(msgs)} msg)')}")
        for m in msgs[: args.lines]:
            print(f"    {colors.dim('│')} {m}")
        if len(msgs) > args.lines:
            print(colors.dim(f"    ... +{len(msgs) - args.lines} more"))
    if len(sorted_units) > args.units:
        print(colors.dim(f"  ... +{len(sorted_units) - args.units} more unit(s)"))
    return 0


def cmd_services(args: argparse.Namespace) -> int:
    """Drilldown for a single systemd service: state + recent journal lines."""
    if not shutil.which("systemctl"):
        msg = "systemctl not available on this host"
        if args.format == "json":
            print(json.dumps({"error": msg}))
        else:
            print(colors.red(msg))
        return 2
    details = sysinfo.get_service_details(args.name)
    if details is None:
        msg = f"service '{args.name}' not found"
        if args.format == "json":
            print(json.dumps({"error": msg}))
        else:
            print(colors.red(msg))
        return 1
    journal = sysinfo.get_service_journal(args.name, lines=args.lines)
    listening = _ports_for_pid(details.get("MainPID", "0"))

    active_state = details.get("ActiveState", "?")
    service_rc = 0 if active_state in ("active", "activating", "reloading") else 1

    if args.format == "plain":
        lines = [
            f"id\t{details.get('Id', args.name)}",
            f"state\t{active_state}\t{details.get('SubState', '?')}\t{details.get('Result', '?')}",
        ]
        if details.get("UnitFileState"):
            lines.append(f"enabled\t{details['UnitFileState']}")
        if details.get("MainPID") and details["MainPID"] != "0":
            lines.append(f"pid\t{details['MainPID']}")
        if details.get("NRestarts"):
            lines.append(f"restarts\t{details['NRestarts']}")
        mem_current = details.get("MemoryCurrent", "0")
        if mem_current.isdigit() and int(mem_current) > 0:
            lines.append(f"memory_bytes\t{mem_current}")
        for p in listening:
            lines.append(f"port\t{p['port']}\t{p['addr']}")
        for line in journal:
            lines.append(f"journal\t{line}")
        print("\n".join(lines))
        return service_rc

    if args.format == "json":
        payload = {"schema_version": 1, "details": details, "listening_ports": listening, "journal": journal}
        print(json.dumps(payload, indent=2, default=str))
        return service_rc

    print(colors.section(details.get("Id", args.name).upper()))
    active = details.get("ActiveState", "?")
    sub = details.get("SubState", "?")
    result = details.get("Result", "?")
    color_fn = colors.green if active == "active" else (colors.red if active in ("failed",) else colors.yellow)
    print(f"  state    : {color_fn(f'{active} ({sub})', bold=True)}  {colors.dim(f'· result={result}')}")
    if details.get("Description"):
        print(f"  desc     : {details['Description']}")
    if details.get("UnitFileState"):
        print(f"  enabled  : {details['UnitFileState']}")
    if details.get("FragmentPath"):
        print(f"  unit file: {colors.dim(details['FragmentPath'])}")
    pid = details.get("MainPID")
    if pid and pid != "0":
        print(f"  main pid : {pid}")
    nrestarts = details.get("NRestarts")
    if nrestarts and nrestarts != "0":
        marker = colors.yellow if int(nrestarts) < 10 else colors.red
        print(f"  restarts : {marker(nrestarts, bold=True)}")
    try:
        mem_bytes = int(details.get("MemoryCurrent", "0"))
        if mem_bytes > 0:
            print(f"  memory   : {sysinfo.format_bytes(mem_bytes)}")
    except ValueError:
        pass
    if details.get("TasksCurrent") and details["TasksCurrent"] != "[not set]":
        print(f"  tasks    : {details['TasksCurrent']}")
    if listening:
        ports = ", ".join(f"{p['port']}" for p in listening)
        print(f"  ports    : {ports}")

    if journal:
        print("")
        print(colors.bold(f"  recent journal (last {len(journal)} lines):"))
        for line in journal:
            print(f"    {colors.dim('│')} {line}")
    return 0 if active in ("active", "activating", "reloading") else 1


def _ports_for_pid(pid_str: str) -> List[dict]:
    """Return listening ports owned by the given PID (best-effort, via psutil)."""
    if not pid_str or pid_str == "0":
        return []
    try:
        pid = int(pid_str)
    except ValueError:
        return []
    if not sysinfo.HAS_PSUTIL:
        return []
    try:
        import psutil  # type: ignore

        result = []
        for conn in psutil.net_connections(kind="inet"):
            if conn.pid != pid:
                continue
            if conn.status != psutil.CONN_LISTEN:
                continue
            if not conn.laddr:
                continue
            result.append({"port": conn.laddr.port, "addr": conn.laddr.ip})
        return result
    except Exception:
        return []


def cmd_config(args: argparse.Namespace) -> int:
    """Show effective config, the example template, or where files are searched."""
    if args.example:
        print(config_mod.example_config())
        return 0
    if args.format == "json":
        cfg = config_mod.get_config()
        payload = {
            "search_paths": list(config_mod.DEFAULT_CONFIG_PATHS),
            "effective": {k: (list(v) if isinstance(v, set) else v) for k, v in cfg.__dict__.items()},
        }
        print(json.dumps(payload, indent=2, default=str))
        return 0
    cfg = config_mod.get_config()
    print(colors.section("CONFIG"))
    print("  search paths:")
    for p in config_mod.DEFAULT_CONFIG_PATHS:
        marker = colors.green("●") if os.path.exists(p) else colors.dim("○")
        print(f"    {marker} {p}")
    print("")
    print(colors.bold("  effective values:"))
    for key, value in cfg.__dict__.items():
        if isinstance(value, set):
            value = ", ".join(sorted(value)) if value else "(none)"
        print(f"    {key:<26} {value}")
    print("")
    print(colors.dim("  tip: `wtf config --example > /etc/wtftools/config.ini`"))
    return 0


def cmd_problems(args: argparse.Namespace) -> int:
    """Alias for `wtf audit --only problems` — show WARN+FAIL results only.

    This is the most common audit invocation during an incident, surfaced as
    its own subcommand for typing comfort.
    """
    args.only = "problems"
    return cmd_audit(args)


def cmd_daily(args: argparse.Namespace) -> int:
    """Morning routine: audit + diff vs the last snapshot + recent events.

    Saves a snapshot at the end, so tomorrow's run diffs against today.
    """
    args.check = None
    args.serial = False
    args.check_timeout = None
    args.only = None
    results, _ = _run_audit_once(args)

    paths = snapshot_mod.list_snapshots()
    old = snapshot_mod.load_snapshot(paths[-1]) if paths else None
    changes = snapshot_mod.diff_snapshots(old, results) if old else []
    events = events_mod.collect_events(hours=args.since)
    saved = snapshot_mod.save_snapshot(results, host=sysinfo.get_hostname())

    if args.format == "json":
        payload = {
            "schema_version": 1,
            "summary": audit_mod.summarize(results),
            "results": [asdict(r) for r in results],
            "changes": changes,
            "events": [{"timestamp": e.timestamp, "iso": e.iso(), "kind": e.kind, "message": e.message} for e in events],
            "snapshot": saved,
        }
        print(json.dumps(payload, indent=2, default=str))
        return _audit_exit_code(args, results)

    _emit_brief(results)
    print("")
    if old is not None:
        _render_diff(args, old, results, old_path=paths[-1])
    else:
        print(colors.section("DIFF"))
        print(colors.dim("  (first run — snapshot saved, the diff appears tomorrow)"))
    print("")
    _print_events_text(events, args.since)
    print("")
    exit_code = _emit_audit(args, results)
    if saved:
        print(colors.dim(f"snapshot saved: {saved}"))
    return exit_code


def cmd_doctor(args: argparse.Namespace) -> int:
    """Self-diagnostic: which capabilities are available on this host."""
    report = _gather_doctor_report(check_updates=getattr(args, "check_updates", False))
    if args.format == "json":
        print(json.dumps(report, indent=2, default=str))
        return 0
    print(colors.section("DOCTOR"))
    name_width = max((len(item["name"]) for item in report["checks"]), default=20)
    for item in report["checks"]:
        marker = colors.status_marker(item["status"])
        print(f"  {marker} {item['name'].ljust(name_width)}  {item['detail']}")
    return 0


def _fetch_pypi_version(package: str = "wtftools", timeout: float = 3.0) -> Optional[str]:
    """Query PyPI for the latest published version. Returns None on failure."""
    import urllib.request

    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{package}/json", timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        return data.get("info", {}).get("version")
    except Exception:
        return None


def _version_tuple(v: str) -> tuple:
    """Cheap semver-ish parse — for ordering only. Non-numeric chunks → 0."""
    parts = []
    for chunk in v.split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _gather_doctor_report(check_updates: bool = False) -> dict:
    """Probe the environment for tools wtf relies on and return a report dict."""
    items = []

    def add(name, present, detail, status_when_ok="ok", status_when_missing="warn"):
        items.append(
            {
                "name": name,
                "status": status_when_ok if present else status_when_missing,
                "present": bool(present),
                "detail": detail,
            }
        )

    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    items.append({"name": "python", "status": "ok", "present": True, "detail": py})

    add("psutil", sysinfo.HAS_PSUTIL, "available — richer top/sockets data" if sysinfo.HAS_PSUTIL else "missing — install `python3-psutil` or `pip install wtftools[full]`")

    for bin_name, hint in (
        ("systemctl", "systemd-based distro recommended; failed-units/enabled checks degrade without it"),
        ("journalctl", "OOM/kernel/auth checks fall back to /var/log when missing"),
        ("crontab", "needed for `wtf crontab -u <user>`"),
        ("apt", "pending updates check is skipped without it"),
        ("timedatectl", "time-sync check needs it"),
        ("ss", "fallback for listening-ports check when psutil is missing"),
        ("ps", "fallback for top processes"),
        ("ip", "fallback for network interface listing"),
        ("last", "recent logins (info)"),
        ("dmesg", "fallback OOM source"),
    ):
        path = shutil.which(bin_name)
        items.append(
            {
                "name": bin_name,
                "status": "ok" if path else "warn",
                "present": bool(path),
                "detail": path or f"missing — {hint}",
            }
        )

    for path, label in (("/etc/os-release", "OS metadata"), ("/proc/meminfo", "memory data"), ("/proc/loadavg", "load average"), ("/proc/stat", "iowait sampling")):
        present = os.path.exists(path)
        items.append(
            {
                "name": path,
                "status": "ok" if present else "fail",
                "present": present,
                "detail": label if present else f"{label} not readable",
            }
        )

    if check_updates:
        latest = _fetch_pypi_version()
        if latest is None:
            items.append(
                {
                    "name": "pypi update check",
                    "status": "skip",
                    "present": False,
                    "detail": "could not reach PyPI",
                }
            )
        else:
            try:
                outdated = _version_tuple(latest) > _version_tuple(__version__)
            except Exception:
                outdated = False
            items.append(
                {
                    "name": "pypi update check",
                    "status": "warn" if outdated else "ok",
                    "present": True,
                    "detail": (f"installed {__version__}, PyPI has {latest}" if outdated else f"up to date ({__version__})"),
                }
            )

    return {"version": __version__, "platform": platform.platform(), "checks": items}


def _collect_crontab_targets(args: argparse.Namespace) -> Tuple[List[Tuple[str, bool]], List[str]]:
    targets: List[Tuple[str, bool]] = []
    temp_files: List[str] = []

    if args.system:
        for path in args.system:
            targets.append((path, True))
    if args.user_file:
        for path in args.user_file:
            targets.append((path, False))
    if args.username:
        for name in args.username:
            path = cron.find_user_crontab(name)
            if path:
                temp_files.append(path)
                targets.append((path, False))
            else:
                logger.warning(f"crontab for user '{name}' not found")

    for arg in args.targets:
        if os.path.isfile(arg):
            full = os.path.abspath(arg)
            is_system = full == "/etc/crontab" or full.startswith("/etc/cron.d")
            targets.append((full, is_system))
        elif os.path.isdir(arg):
            for name in sorted(os.listdir(arg)):
                path = os.path.join(arg, name)
                if os.path.isfile(path) and not cron.check_filename(name):
                    full = os.path.abspath(path)
                    is_system = full.startswith("/etc/cron.d") or full == "/etc/crontab"
                    targets.append((full, is_system))
        elif re.match(r"^[a-zA-Z][a-zA-Z0-9_-]{0,31}$", arg):
            path = cron.find_user_crontab(arg)
            if path:
                temp_files.append(path)
                targets.append((path, False))
            else:
                logger.warning(f"'{arg}' is not a file and has no crontab")
        else:
            logger.warning(f"'{arg}' not found, skipping")

    if not targets:
        targets = cron.discover_default_targets()

    seen = set()
    unique: List[Tuple[str, bool]] = []
    for path, is_sys in targets:
        if path in seen:
            continue
        seen.add(path)
        unique.append((path, is_sys))
    return unique, temp_files


def cmd_crontab(args: argparse.Namespace) -> int:
    targets, temp_files = _collect_crontab_targets(args)

    total_rows = 0
    total_errors = 0
    total_warnings = 0
    file_reports: List[dict] = []

    if platform.system().lower() == "linux" and not os.getenv("GITHUB_ACTIONS"):
        for warning in cron.check_daemon():
            if args.format != "json":
                print(colors.yellow(f"warning: {warning}"))

    if not targets:
        if args.format == "json":
            print(json.dumps({"success": True, "files": [], "total_errors": 0}, indent=2))
        else:
            print(colors.dim("no crontab files visible"))
        return 0

    for path, is_system in targets:
        rows = 0
        errors: List[str] = []
        warnings: List[str] = []
        if not os.path.exists(path):
            errors.append(f"{path}: does not exist")
        else:
            if is_system and platform.system().lower() == "linux":
                errors.extend(cron.check_owner_and_permissions(path))
            r, e, w = cron.check_file(path, is_system_crontab=is_system)
            rows = r
            errors.extend(e)
            warnings.extend(w)
        file_reports.append(
            {
                "file": path,
                "is_system_crontab": is_system,
                "rows": rows,
                "errors": errors,
                "warnings": warnings,
            }
        )
        total_rows += rows
        total_errors += len(errors)
        total_warnings += len(warnings)

    if args.format == "json":
        payload = {
            "success": total_errors == 0,
            "total_files": len(file_reports),
            "total_rows": total_rows,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "files": file_reports,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(colors.section("CRONTAB"))
        for report in file_reports:
            tag = colors.cyan("[system]" if report["is_system_crontab"] else "[user]  ")
            rows_label = colors.dim(f"({report['rows']} lines)")
            if not report["errors"] and not report["warnings"]:
                print(f"  {colors.status_marker('OK')} {tag} {report['file']}  {rows_label}")
            else:
                marker = "FAIL" if report["errors"] else "WARN"
                print(f"  {colors.status_marker(marker)} {tag} {report['file']}  {rows_label}")
                for error in report["errors"]:
                    print(f"      {colors.red('✗')} {error}")
                for warning in report["warnings"]:
                    print(f"      {colors.yellow('⚠')} {warning}")
        print("")
        summary = [
            colors.bold(f"{len(file_reports)} files"),
            colors.bold(f"{total_rows} lines"),
            colors.red(f"{total_errors} errors") if total_errors else colors.green("0 errors"),
            colors.yellow(f"{total_warnings} warnings") if total_warnings else colors.dim("0 warnings"),
        ]
        print(f"  Summary: {' · '.join(summary)}")

    for path in temp_files:
        try:
            os.unlink(path)
        except Exception:
            pass

    if args.exit_zero:
        return 0
    if total_errors:
        return 1
    if args.strict and total_warnings:
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wtf",
        description=__description__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Project: {__url__}\n"
        "Examples:\n"
        "  wtf                       # default: short audit summary\n"
        "  wtf disk /var             # what folders eat space under /var\n"
        "  wtf disk / --tree         # drill into the biggest folders of /\n"
        "  wtf info                  # detailed system snapshot\n"
        "  wtf audit -v              # audit with extra detail per check\n"
        "  wtf crontab               # check standard crontab locations\n"
        "  wtf crontab -u myuser     # check a specific user's crontab\n"
        "  wtf audit --format json   # machine-readable output\n",
    )
    parser.add_argument("-V", "--version", action="version", version=f"wtftools {__version__}")
    parser.add_argument(
        "-f",
        "--format",
        choices=["text", "plain", "json", "csv", "html", "prometheus"],
        default="text",
        help="Output format; works before the subcommand too (`wtf -f json disk`). All commands support text/plain/json; csv/html/prometheus are audit-only.",
    )
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show extra detail")
    parser.add_argument("-q", "--quiet", action="store_true", help="Reduce logging output")
    parser.add_argument("--config", metavar="PATH", help="Path to an extra wtftools config file (INI). Stacks on top of the default discovery paths.")

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    info = subparsers.add_parser("info", help="Show summary of system state")
    info.add_argument("--format", choices=["text", "plain", "json"], default=argparse.SUPPRESS)
    info.set_defaults(func=cmd_info)

    disk = subparsers.add_parser("disk", help="Mounts overview, or folder usage of a PATH (`wtf disk /home`)")
    disk.add_argument("path", nargs="?", default=None, help="Directory to break down by folder size (omit for the mount overview)")
    disk.add_argument(
        "--tree",
        nargs="?",
        type=int,
        const=1,
        default=0,
        metavar="N",
        help="Expand the N largest folders at each level (bare --tree = 1; omit = flat, no expansion)",
    )
    disk.add_argument("--depth", type=int, default=3, metavar="N", help="Levels to show when expanding with --tree (default: 3)")
    disk.add_argument("--top", type=int, default=0, metavar="N", help="Cap children shown per level (default: 0 = all)")
    disk.add_argument("--format", choices=["text", "plain", "json"], default=argparse.SUPPRESS)
    disk.add_argument("--show-commands", action="store_true", help="Also print the classic commands this view replaces")
    disk.set_defaults(func=cmd_disk)

    cpu = subparsers.add_parser("cpu", help="CPU load, iowait, pressure, top consumers")
    cpu.add_argument("--format", choices=["text", "plain", "json"], default=argparse.SUPPRESS)
    cpu.add_argument("--show-commands", action="store_true", help="Also print the classic commands this view replaces")
    cpu.set_defaults(func=cmd_cpu)

    mem = subparsers.add_parser("mem", help="Memory/swap usage, OOM kills, top consumers")
    mem.add_argument("--since", type=int, default=24, metavar="HOURS", help="Look-back window for OOM kills (default: 24)")
    mem.add_argument("--format", choices=["text", "plain", "json"], default=argparse.SUPPRESS)
    mem.add_argument("--show-commands", action="store_true", help="Also print the classic commands this view replaces")
    mem.set_defaults(func=cmd_mem)

    net = subparsers.add_parser("net", help="Interfaces, gateway, DNS, errors, listening ports")
    net.add_argument("--format", choices=["text", "plain", "json"], default=argparse.SUPPRESS)
    net.add_argument("--show-commands", action="store_true", help="Also print the classic commands this view replaces")
    net.set_defaults(func=cmd_net)

    io = subparsers.add_parser("io", help="Disk IO rates, pressure, stuck processes")
    io.add_argument("--format", choices=["text", "plain", "json"], default=argparse.SUPPRESS)
    io.add_argument("--show-commands", action="store_true", help="Also print the classic commands this view replaces")
    io.set_defaults(func=cmd_io)

    who = subparsers.add_parser("who", help="Logged-in users, recent logins, failed auth")
    who.add_argument("--since", type=int, default=24, metavar="HOURS", help="Look-back window for failed auth (default: 24)")
    who.add_argument("--format", choices=["text", "plain", "json"], default=argparse.SUPPRESS)
    who.add_argument("--show-commands", action="store_true", help="Also print the classic commands this view replaces")
    who.set_defaults(func=cmd_who)

    temp = subparsers.add_parser("temp", aliases=["temps", "temperature"], help="Hardware temperatures from /sys/class/hwmon sensors")
    temp.add_argument("--format", choices=["text", "plain", "json"], default=argparse.SUPPRESS)
    temp.set_defaults(func=cmd_temp)

    audit = subparsers.add_parser("audit", help="Run health audit and show OK/WARN/FAIL")
    audit.add_argument("--format", choices=["text", "json", "prometheus", "csv", "plain", "html"], default=argparse.SUPPRESS)
    audit.add_argument("--output", "-o", metavar="FILE", help="Write the audit to FILE instead of stdout (drops ANSI colors)")
    audit.add_argument("--strict", action="store_true", help="Exit non-zero on warnings too")
    audit.add_argument("--exit-zero", action="store_true", help="Always exit with code 0")
    audit.add_argument("--check", action="append", metavar="NAME", help="Run only the named check (repeatable). See `--list-checks`.")
    audit.add_argument("--only", choices=list(STATUS_FILTERS.keys()), help="Show only results with the given status (fail/warn/problems/skip/ok/all)")
    audit.add_argument("--since", type=int, metavar="HOURS", default=24, help="Look-back window in hours for OOM/auth/kernel checks (default: 24)")
    audit.add_argument("--list-checks", action="store_true", dest="list_checks", help="List all check short-names and exit")
    audit.add_argument("--brief", "-b", action="store_true", help="One-line summary suitable for MOTD / SSH banners")
    audit.add_argument(
        "--ignore",
        action="append",
        metavar="NAME",
        default=[],
        help="Skip a check (short-name) or result-name (repeatable). e.g. --ignore swap  or  --ignore 'disk /mnt/Backup'",
    )
    audit.add_argument("--serial", action="store_true", help="Run checks sequentially (for debugging; default is parallel)")
    audit.add_argument("--check-timeout", type=float, metavar="SECONDS", help="Per-check timeout in seconds (default: 10, overrides config)")
    audit.add_argument(
        "--alert", metavar="CMD", help="Shell command to invoke when FAIL results exist. Audit text is piped to stdin. Env: WTF_FAIL_COUNT, WTF_WARN_COUNT, WTF_HOST."
    )
    audit.add_argument("--alert-on", choices=["fail", "warn", "any"], default="fail", help="When to fire --alert (default: only on FAIL)")
    audit.add_argument("--save", action="store_true", help="Persist the audit result as a snapshot for history/diff")
    audit.set_defaults(func=cmd_audit)

    top = subparsers.add_parser("top", help="Top processes (focused live snapshot)")
    top.add_argument("--sort", choices=["cpu", "rss"], default="cpu", help="Sort key (default: cpu)")
    top.add_argument("--limit", type=int, default=10, help="Number to show (default: 10)")
    top.add_argument("--user", metavar="PREFIX", help="Filter by username prefix")
    top.add_argument("--name", metavar="PATTERN", help="Filter by command-name substring (case-insensitive)")
    top.add_argument("--format", choices=["text", "plain", "json"], default=argparse.SUPPRESS)
    top.set_defaults(func=cmd_top)

    ports = subparsers.add_parser("ports", aliases=["port"], help="Listening ports; pass a PORT to drill into one (PID, exe file, cwd)")
    ports.add_argument("port", nargs="?", type=int, help="Drill into one port: which process holds it, its exe file and cwd")
    ports.add_argument("--proto", choices=["tcp", "udp", "all"], default="tcp", help="Protocol filter for the listing (default: tcp)")
    ports.add_argument("--public-only", action="store_true", help="Skip loopback addresses (127.x)")
    ports.add_argument("--format", choices=["text", "plain", "json"], default=argparse.SUPPRESS)
    ports.set_defaults(func=cmd_ports)

    docker = subparsers.add_parser("docker", help="Where a container came from: compose working dir by name")
    docker.add_argument("name", nargs="?", help="Container name; omit to list running containers")
    docker.add_argument("--format", choices=["text", "plain", "json"], default=argparse.SUPPRESS)
    docker.set_defaults(func=cmd_docker)

    problems = subparsers.add_parser("problems", help="Show only WARN+FAIL results (alias: audit --only problem)")
    problems.add_argument("--check", action="append", metavar="NAME", help="Run only the named check (repeatable). See `--list-checks`.")
    problems.add_argument("--ignore", action="append", metavar="NAME", default=[], help="Skip a check (short-name) or result-name")
    problems.add_argument("--since", type=int, metavar="HOURS", default=24, help="Look-back window for OOM/auth/kernel checks")
    problems.add_argument("--format", choices=["text", "json", "prometheus", "csv", "plain", "html"], default=argparse.SUPPRESS)
    problems.add_argument("--output", "-o", metavar="FILE", help="Write to FILE instead of stdout")
    problems.add_argument("--strict", action="store_true", help="Exit non-zero on warnings too")
    problems.add_argument("--exit-zero", action="store_true", help="Always exit with code 0")
    problems.add_argument("--serial", action="store_true", help="Run checks sequentially")
    problems.add_argument("--check-timeout", type=float, metavar="SECONDS", help="Per-check timeout in seconds")
    problems.add_argument("--verbose", "-v", action="store_true", help="Show extra detail")
    problems.set_defaults(func=cmd_problems, list_checks=False, brief=False, save=False, alert=None, alert_on="fail")

    diff = subparsers.add_parser("diff", help="Compare current audit (or a snapshot) against a stored snapshot")
    diff.add_argument("--snapshot", type=int, default=0, metavar="N", help="Compare against the Nth-most-recent snapshot (0=latest, 1=one before, …). Default: 0.")
    diff.add_argument("--against", nargs=2, metavar=("OLD", "NEW"), help="Diff two snapshot files directly, no live audit")
    diff.add_argument("--format", choices=["text", "json"], default=argparse.SUPPRESS)
    diff.set_defaults(func=cmd_diff)

    history = subparsers.add_parser("history", help="List saved audit snapshots")
    history.add_argument("--limit", type=int, default=20, help="Number of most-recent snapshots to show (default: 20)")
    history.add_argument("--format", choices=["text", "json"], default=argparse.SUPPRESS)
    history.set_defaults(func=cmd_history)

    explain = subparsers.add_parser("explain", help="Suggest actions for current audit findings")
    explain.add_argument("--check", action="append", metavar="NAME", help="Limit to specific checks")
    explain.add_argument("--ignore", action="append", metavar="NAME", default=[], help="Skip a check or result-name")
    explain.add_argument("--since", type=int, default=24, metavar="HOURS", help="Look-back window for time-bounded checks (default: 24)")
    explain.add_argument("--all", action="store_true", help="Also explain OK results (default: only WARN/FAIL)")
    explain.add_argument(
        "--deep", action="store_true", help="Run dynamic investigation per finding (du -d1 on the filling mount, docker system df, container/log sizes). Slower; opt-in."
    )
    explain.add_argument(
        "--prompt", action="store_true", help="Print an LLM-ready prompt instead of built-in advice. Pipe it: `wtf explain --prompt | claude` or `| ollama run llama3`."
    )
    explain.add_argument(
        "--llm",
        choices=["ollama", "claude", "openai", "auto"],
        help="Call an LLM directly with the structured prompt and print its response. ollama needs the binary; claude/openai need the matching Python SDK + API key env.",
    )
    explain.add_argument("--llm-model", metavar="MODEL", help="Override default model name for --llm")
    explain.add_argument("--llm-timeout", type=int, default=60, metavar="SECONDS", help="LLM call timeout (default: 60s)")
    explain.add_argument("--format", choices=["text", "json"], default=argparse.SUPPRESS)
    explain.add_argument("--serial", action="store_true", help="Run audit sequentially (passes through to underlying audit)")
    explain.add_argument("--check-timeout", type=float, metavar="SECONDS", help="Per-check timeout in seconds (passes through to audit)")
    explain.set_defaults(func=cmd_explain, only=None)

    daily = subparsers.add_parser("daily", help="Morning check: audit + what changed since the last run + events")
    daily.add_argument("--since", type=int, default=24, metavar="HOURS", help="Look-back window in hours (default: 24)")
    daily.add_argument("--ignore", action="append", metavar="NAME", default=[], help="Skip a check (short-name) or result-name (repeatable)")
    daily.add_argument("--strict", action="store_true", help="Exit non-zero on warnings too")
    daily.add_argument("--exit-zero", action="store_true", help="Always exit with code 0")
    daily.add_argument("--format", choices=["text", "json"], default=argparse.SUPPRESS)
    daily.set_defaults(func=cmd_daily, output=None)

    doctor = subparsers.add_parser("doctor", help="Self-diagnostic: which tools/files wtf can use")
    doctor.add_argument("--format", choices=["text", "json"], default=argparse.SUPPRESS)
    doctor.add_argument("--check-updates", action="store_true", help="Query PyPI for a newer wtftools version (network call)")
    doctor.set_defaults(func=cmd_doctor)

    events = subparsers.add_parser("events", help="Chronological timeline: reboots, OOM kills, failed units, kernel errors")
    events.add_argument("--since", type=int, default=24, metavar="HOURS", help="Look-back window in hours (default: 24)")
    events.add_argument(
        "--kind", action="append", metavar="KIND", choices=list(events_mod.EVENT_KINDS), help="Filter to one kind (repeatable). Choices: " + ", ".join(events_mod.EVENT_KINDS)
    )
    events.add_argument("--limit", type=int, default=0, help="Max events to show (0 = unlimited)")
    events.add_argument("--format", choices=["text", "plain", "json"], default=argparse.SUPPRESS)
    events.set_defaults(func=cmd_events)

    logs = subparsers.add_parser("logs", help="Recent ERROR-level journal entries grouped by service")
    logs.add_argument("--since", default="1 hour ago", help="journalctl --since value (default: '1 hour ago')")
    logs.add_argument("--priority", "-p", default="err", help="journalctl priority filter (default: 'err' = err+crit+alert+emerg)")
    logs.add_argument("--units", type=int, default=10, help="Number of top units to show (default: 10)")
    logs.add_argument("--lines", "-n", type=int, default=5, help="Lines per unit (default: 5)")
    logs.add_argument("--format", choices=["text", "plain", "json"], default=argparse.SUPPRESS)
    logs.set_defaults(func=cmd_logs)

    services = subparsers.add_parser("services", aliases=["service"], help="Drilldown for one systemd service")
    services.add_argument("name", help="Service unit name (e.g. nginx or nginx.service)")
    services.add_argument("-n", "--lines", type=int, default=20, help="Recent journal lines to show (default: 20)")
    services.add_argument("--format", choices=["text", "plain", "json"], default=argparse.SUPPRESS)
    services.set_defaults(func=cmd_services)

    cfg = subparsers.add_parser("config", help="Show or generate the wtftools config")
    cfg.add_argument("--example", action="store_true", help="Print a fully-commented example config and exit")
    cfg.add_argument("--format", choices=["text", "json"], default=argparse.SUPPRESS)
    cfg.set_defaults(func=cmd_config)

    comp = subparsers.add_parser("completion", help="Print a bash/zsh completion script to enable <Tab> completion")
    comp.add_argument("shell", nargs="?", choices=["bash", "zsh"], help="Shell to emit a script for; omit for setup instructions")
    comp.set_defaults(func=cmd_completion)

    crontab = subparsers.add_parser("crontab", help="Validate crontab files (system + user)")
    crontab.add_argument("targets", nargs="*", help="Files, directories, or usernames")
    crontab.add_argument("-S", "--system", action="append", metavar="FILE", help="System crontab file")
    crontab.add_argument("-U", "--user-file", action="append", metavar="FILE", help="User crontab file")
    crontab.add_argument("-u", "--username", action="append", metavar="USER", help="Username")
    crontab.add_argument("--format", choices=["text", "json"], default=argparse.SUPPRESS)
    crontab.add_argument("--strict", action="store_true", help="Exit non-zero on warnings too")
    crontab.add_argument("--exit-zero", action="store_true", help="Always exit with code 0")
    crontab.set_defaults(func=cmd_crontab)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    colors.init_colors(force_no_color=args.no_color)

    # Resolve config. CLI --config stacks on top of default paths.
    paths = list(config_mod.DEFAULT_CONFIG_PATHS)
    if args.config:
        paths.append(args.config)
    config_mod.set_config(config_mod.load_config(paths))

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    elif args.quiet:
        logging.getLogger().setLevel(logging.ERROR)

    if not args.command:
        # default action: short audit summary (args.format comes from the
        # top-level -f/--format default)
        args.command = "audit"
        args.strict = False
        args.exit_zero = False
        args.check = None
        args.only = None
        args.since = 24
        args.list_checks = False
        args.brief = False
        args.ignore = []
        args.serial = False
        args.check_timeout = None
        args.alert = None
        args.alert_on = "fail"
        args.save = False
        args.output = None
        args.func = cmd_audit

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\ninterrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
