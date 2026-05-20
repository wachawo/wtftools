#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for wtftools.info — render the system snapshot."""


from wtftools import info


def test_bar_clamped_low_and_high():
    bar_low = info._bar(0)
    bar_high = info._bar(150)
    assert "0%" in bar_low
    assert "100%" in bar_high


def test_bar_thresholds():
    # Below 75 → green branch; 75-89 → yellow; >=90 → red
    # We just verify the bar renders at all three percentages without crashing.
    for pct in (10, 80, 95):
        assert "%" in info._bar(pct)


def test_render_info_contains_sections(monkeypatch):
    monkeypatch.setattr(info.sysinfo, "get_os_release", lambda: {"PRETTY_NAME": "Test OS"})
    monkeypatch.setattr(info.sysinfo, "get_kernel", lambda: "5.0.0-test")
    monkeypatch.setattr(info.sysinfo, "get_hostname", lambda: "host1")
    monkeypatch.setattr(info.sysinfo, "get_uptime_seconds", lambda: 12345)
    monkeypatch.setattr(info.sysinfo, "get_cpu_model", lambda: "Test CPU")
    monkeypatch.setattr(info.sysinfo, "get_cpu_count", lambda: 4)
    monkeypatch.setattr(info.sysinfo, "get_loadavg", lambda: (0.1, 0.2, 0.3))
    monkeypatch.setattr(info.sysinfo, "get_memory_summary", lambda: {"used": 100, "total": 1000, "percent": 10, "swap_total": 200, "swap_used": 50, "swap_percent": 25})
    monkeypatch.setattr(
        info.sysinfo,
        "get_disks",
        lambda: [
            {"target": "/", "used": 50, "total": 100, "percent": 50, "fstype": "ext4"},
        ],
    )
    monkeypatch.setattr(
        info.sysinfo,
        "get_top_processes",
        lambda by, limit: [
            {"pid": 1, "name": "a", "user": "u", "cpu_percent": 50.0, "rss": 1024},
            {"pid": 2, "name": "b", "user": "u", "cpu_percent": 10.0, "rss": 2048},
        ],
    )
    monkeypatch.setattr(
        info.sysinfo,
        "get_network_interfaces",
        lambda: [
            {"name": "eth0", "ipv4": ["10.0.0.1"], "ipv6": [], "up": True},
            {"name": "eth1", "ipv4": [], "ipv6": [], "up": False},
        ],
    )
    monkeypatch.setattr(
        info.sysinfo,
        "get_listening_ports",
        lambda: [
            {"port": 22, "addr": "0.0.0.0", "pid": 1},
            {"port": 80, "addr": "0.0.0.0", "pid": 2},
        ],
    )
    out = info.render_info()
    for s in ("SYSTEM", "MEMORY", "DISK", "TOP BY CPU", "TOP BY RAM", "NETWORK", "host1", "Test CPU"):
        assert s in out


def test_render_info_no_swap_no_disks_no_net(monkeypatch):
    monkeypatch.setattr(info.sysinfo, "get_os_release", lambda: {})
    monkeypatch.setattr(info.sysinfo, "get_kernel", lambda: "k")
    monkeypatch.setattr(info.sysinfo, "get_hostname", lambda: "h")
    monkeypatch.setattr(info.sysinfo, "get_uptime_seconds", lambda: 0)
    monkeypatch.setattr(info.sysinfo, "get_cpu_model", lambda: "cpu")
    monkeypatch.setattr(info.sysinfo, "get_cpu_count", lambda: 1)
    monkeypatch.setattr(info.sysinfo, "get_loadavg", lambda: (0.0, 0.0, 0.0))
    monkeypatch.setattr(info.sysinfo, "get_memory_summary", lambda: {"used": 0, "total": 1, "percent": 0, "swap_total": 0, "swap_used": 0, "swap_percent": 0})
    monkeypatch.setattr(info.sysinfo, "get_disks", lambda: [])
    monkeypatch.setattr(info.sysinfo, "get_top_processes", lambda by, limit: [])
    monkeypatch.setattr(info.sysinfo, "get_network_interfaces", lambda: [])
    monkeypatch.setattr(info.sysinfo, "get_listening_ports", lambda: [])
    out = info.render_info()
    assert "no mounts found" in out
    assert "not configured" in out


def test_render_info_many_ports(monkeypatch):
    monkeypatch.setattr(info.sysinfo, "get_os_release", lambda: {})
    monkeypatch.setattr(info.sysinfo, "get_kernel", lambda: "k")
    monkeypatch.setattr(info.sysinfo, "get_hostname", lambda: "h")
    monkeypatch.setattr(info.sysinfo, "get_uptime_seconds", lambda: 0)
    monkeypatch.setattr(info.sysinfo, "get_cpu_model", lambda: "cpu")
    monkeypatch.setattr(info.sysinfo, "get_cpu_count", lambda: 1)
    monkeypatch.setattr(info.sysinfo, "get_loadavg", lambda: (0.0, 0.0, 0.0))
    monkeypatch.setattr(info.sysinfo, "get_memory_summary", lambda: {"used": 0, "total": 1, "percent": 0, "swap_total": 0, "swap_used": 0, "swap_percent": 0})
    monkeypatch.setattr(info.sysinfo, "get_disks", lambda: [])
    monkeypatch.setattr(info.sysinfo, "get_top_processes", lambda by, limit: [])
    monkeypatch.setattr(info.sysinfo, "get_network_interfaces", lambda: [])
    monkeypatch.setattr(info.sysinfo, "get_listening_ports", lambda: [{"port": p, "addr": "0.0.0.0", "pid": p} for p in range(1, 30)])
    out = info.render_info()
    assert "more" in out  # "+N more" hint appears when >20 unique ports
