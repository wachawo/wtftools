#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configuration loading for wtftools.

Reads INI files (no extra deps; stdlib `configparser`). Discovery order:
    /etc/wtftools/config.ini
    /etc/wtf/config.ini
    $XDG_CONFIG_HOME/wtftools/config.ini   (or ~/.config/wtftools/config.ini)

Later files override earlier ones. Example:

    [thresholds]
    disk_warn = 85
    disk_fail = 95
    swap_warn = 50
    swap_fail = 90

    [ignore]
    checks = swap, updates
    # disk results carry a result-name like "disk /mnt/Backup" — you can
    # ignore individual mountpoints by listing them in `result_names`.
    result_names =
        disk /mnt/Backup
        disk /mnt/Video
"""

import configparser
import logging
import os
import traceback
from dataclasses import dataclass, field
from typing import List, Optional, Set

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATHS = (
    "/etc/wtftools/config.ini",
    "/etc/wtf/config.ini",
    os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
        "wtftools", "config.ini",
    ),
)


@dataclass
class Config:
    """All runtime knobs in one place. Defaults match the hardcoded values."""
    disk_warn_pct: int = 85
    disk_fail_pct: int = 95
    mem_warn_pct: int = 85
    mem_fail_pct: int = 95
    swap_warn_pct: int = 30
    swap_fail_pct: int = 70
    load_warn_ratio: float = 1.0
    load_fail_ratio: float = 2.0
    iowait_warn_pct: float = 10.0
    iowait_fail_pct: float = 30.0
    fd_warn_pct: int = 60
    fd_fail_pct: int = 80
    pid_warn_pct: int = 50
    pid_fail_pct: int = 80
    tcp_retrans_warn_pct: float = 1.0
    tcp_retrans_fail_pct: float = 5.0
    auth_warn_count: int = 50
    restart_warn_threshold: int = 3
    restart_fail_threshold: int = 10
    psi_warn_pct: float = 10.0
    psi_fail_pct: float = 30.0
    cert_warn_days: int = 30
    cert_fail_days: int = 7
    conntrack_warn_pct: int = 70
    conntrack_fail_pct: int = 90
    journal_warn_gb: float = 4.0
    journal_fail_gb: float = 16.0
    temp_warn_c: float = 75.0
    temp_fail_c: float = 90.0
    dns_probe_hosts: str = "google.com,cloudflare.com"
    dns_probe_timeout: float = 2.0
    http_probes: str = ""
    tcp_probes: str = ""
    probe_timeout: float = 3.0
    probe_slow_ms: float = 1000.0
    fleet_hosts: str = ""
    check_timeout_seconds: float = 10.0
    parallel_workers: int = 8
    ignored_checks: Set[str] = field(default_factory=set)
    ignored_result_names: Set[str] = field(default_factory=set)


_CURRENT: Config = Config()


def get_config() -> Config:
    """Return the active Config singleton."""
    return _CURRENT


def set_config(cfg: Config) -> None:
    """Replace the active Config (called from CLI / tests)."""
    global _CURRENT
    _CURRENT = cfg


def _split_list(value: str) -> List[str]:
    return [s.strip() for s in value.replace("\n", ",").split(",") if s.strip()]


def _coerce(parser: configparser.ConfigParser, section: str, option: str,
            current_value, cfg_attr: str, cfg: Config) -> None:
    """Read one config option and assign with the right numeric type."""
    if not parser.has_option(section, option):
        return
    raw = parser.get(section, option)
    try:
        if isinstance(current_value, bool):
            new_value = raw.strip().lower() in ("1", "true", "yes", "on")
        elif isinstance(current_value, int):
            new_value = int(float(raw))
        elif isinstance(current_value, float):
            new_value = float(raw)
        else:
            new_value = raw
        setattr(cfg, cfg_attr, new_value)
    except (ValueError, TypeError):
        logger.warning(f"config: ignoring invalid value for {section}.{option}: {raw!r}")


def load_config(paths: Optional[List[str]] = None) -> Config:
    """Read config files and return a Config with defaults overlaid by user values."""
    if paths is None:
        paths = list(DEFAULT_CONFIG_PATHS)
    cfg = Config()
    existing = [p for p in paths if os.path.exists(p)]
    if not existing:
        return cfg
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(existing, encoding="utf-8")
    except (configparser.Error, OSError) as exc:
        logger.warning(f"config: cannot read {existing}: {type(exc).__name__}: {exc}\n"
                       f"{traceback.format_exc()}")
        return cfg

    threshold_map = [
        ("disk_warn", "disk_warn_pct"),
        ("disk_fail", "disk_fail_pct"),
        ("mem_warn", "mem_warn_pct"),
        ("mem_fail", "mem_fail_pct"),
        ("swap_warn", "swap_warn_pct"),
        ("swap_fail", "swap_fail_pct"),
        ("load_warn", "load_warn_ratio"),
        ("load_fail", "load_fail_ratio"),
        ("iowait_warn", "iowait_warn_pct"),
        ("iowait_fail", "iowait_fail_pct"),
        ("fd_warn", "fd_warn_pct"),
        ("fd_fail", "fd_fail_pct"),
        ("pid_warn", "pid_warn_pct"),
        ("pid_fail", "pid_fail_pct"),
        ("tcp_retrans_warn", "tcp_retrans_warn_pct"),
        ("tcp_retrans_fail", "tcp_retrans_fail_pct"),
        ("auth_warn", "auth_warn_count"),
        ("restart_warn", "restart_warn_threshold"),
        ("restart_fail", "restart_fail_threshold"),
        ("psi_warn", "psi_warn_pct"),
        ("psi_fail", "psi_fail_pct"),
        ("cert_warn_days", "cert_warn_days"),
        ("cert_fail_days", "cert_fail_days"),
        ("conntrack_warn", "conntrack_warn_pct"),
        ("conntrack_fail", "conntrack_fail_pct"),
        ("journal_warn_gb", "journal_warn_gb"),
        ("journal_fail_gb", "journal_fail_gb"),
        ("temp_warn_c", "temp_warn_c"),
        ("temp_fail_c", "temp_fail_c"),
        ("dns_probe_hosts", "dns_probe_hosts"),
        ("dns_probe_timeout", "dns_probe_timeout"),
        ("http_probes", "http_probes"),
        ("tcp_probes", "tcp_probes"),
        ("probe_timeout", "probe_timeout"),
        ("probe_slow_ms", "probe_slow_ms"),
        ("fleet_hosts", "fleet_hosts"),
        ("check_timeout", "check_timeout_seconds"),
        ("parallel_workers", "parallel_workers"),
    ]
    if parser.has_section("thresholds"):
        for opt, attr in threshold_map:
            _coerce(parser, "thresholds", opt, getattr(cfg, attr), attr, cfg)

    if parser.has_section("ignore"):
        if parser.has_option("ignore", "checks"):
            cfg.ignored_checks = set(_split_list(parser.get("ignore", "checks")))
        if parser.has_option("ignore", "result_names"):
            cfg.ignored_result_names = set(_split_list(parser.get("ignore", "result_names")))
    return cfg


def example_config() -> str:
    """Return an example config file body — used by `wtf config --example`."""
    return """# wtftools example config — drop at /etc/wtftools/config.ini
# or ~/.config/wtftools/config.ini

[thresholds]
# Disk usage % thresholds (warn at >= warn, fail at >= fail).
disk_warn = 85
disk_fail = 95

# Memory %
mem_warn = 85
mem_fail = 95

# Swap % (a server that uses swap heavily is doing something wrong)
swap_warn = 30
swap_fail = 70

# Load avg ratio relative to CPU count
load_warn = 1.0
load_fail = 2.0

# CPU iowait %
iowait_warn = 10
iowait_fail = 30

# Open file descriptors % of fs.file-max
fd_warn = 60
fd_fail = 80

# Process count % of pid_max
pid_warn = 50
pid_fail = 80

# TCP retransmit % (sampled over 1 second)
tcp_retrans_warn = 1.0
tcp_retrans_fail = 5.0

# Failed auth attempts in the look-back window
auth_warn = 50

# Service NRestarts thresholds
restart_warn = 3
restart_fail = 10

[ignore]
# Skip these check short-names entirely (comma- or newline-separated).
# Run `wtf audit --list-checks` to see all names.
checks =

# Skip specific result names (useful for disks: "disk /mnt/Backup")
result_names =
"""
