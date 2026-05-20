#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for wtftools.checks.sysinfo — system information gathering."""

import socket
from collections import namedtuple
from unittest import mock

import pytest

from wtftools.checks import sysinfo


def test_format_bytes_units():
    assert sysinfo.format_bytes(0) == "0.0B"
    assert sysinfo.format_bytes(1023) == "1023.0B"
    assert sysinfo.format_bytes(1024) == "1.0KB"
    assert sysinfo.format_bytes(1024 * 1024) == "1.0MB"
    assert sysinfo.format_bytes(1024 ** 3) == "1.0GB"
    assert sysinfo.format_bytes(1024 ** 4) == "1.0TB"
    assert sysinfo.format_bytes(1024 ** 6) == "1.0EB"


def test_format_duration_variants():
    assert sysinfo.format_duration(0) == "0s"
    assert sysinfo.format_duration(45) == "45s"
    assert sysinfo.format_duration(60) == "1m"
    assert "h" in sysinfo.format_duration(3700)
    assert "d" in sysinfo.format_duration(86400 * 2 + 5)


def test_run_success():
    rc, out, err = sysinfo.run(["sh", "-c", "echo hello && echo bad 1>&2"], timeout=5)
    assert rc == 0
    assert "hello" in out
    assert "bad" in err


def test_run_not_found():
    rc, out, err = sysinfo.run(["this_command_definitely_does_not_exist_xyz_123"])
    assert rc == 127
    assert "not found" in err


def test_run_timeout():
    rc, out, err = sysinfo.run(["sleep", "10"], timeout=1)
    assert rc == 124
    assert err == "timeout"


def test_read_file_existing(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hello\nworld")
    assert sysinfo.read_file(str(f)) == "hello\nworld"


def test_read_file_missing():
    assert sysinfo.read_file("/non/existent/path/xyz") == ""


def test_get_hostname():
    assert sysinfo.get_hostname() == socket.gethostname()


def test_get_os_release_parse():
    sample = 'NAME="Ubuntu"\nVERSION_ID="22.04"\n# comment line\nPRETTY_NAME="Ubuntu 22.04"\n'
    with mock.patch.object(sysinfo, "read_file", return_value=sample):
        data = sysinfo.get_os_release()
    assert data["NAME"] == "Ubuntu"
    assert data["VERSION_ID"] == "22.04"
    assert data["PRETTY_NAME"] == "Ubuntu 22.04"


def test_get_kernel():
    assert sysinfo.get_kernel()


def test_get_uptime_seconds_valid():
    with mock.patch.object(sysinfo, "read_file", return_value="1234.56 999.99\n"):
        assert sysinfo.get_uptime_seconds() == pytest.approx(1234.56)


def test_get_uptime_seconds_bad_data():
    with mock.patch.object(sysinfo, "read_file", return_value="garbage"):
        assert sysinfo.get_uptime_seconds() == 0.0
    with mock.patch.object(sysinfo, "read_file", return_value=""):
        assert sysinfo.get_uptime_seconds() == 0.0


def test_get_loadavg_valid():
    with mock.patch.object(sysinfo, "read_file", return_value="0.10 0.20 0.30 1/200 12345"):
        load = sysinfo.get_loadavg()
    assert load == (0.10, 0.20, 0.30)


def test_get_loadavg_invalid():
    with mock.patch.object(sysinfo, "read_file", return_value=""):
        assert sysinfo.get_loadavg() == (0.0, 0.0, 0.0)
    with mock.patch.object(sysinfo, "read_file", return_value="x y z"):
        assert sysinfo.get_loadavg() == (0.0, 0.0, 0.0)


def test_get_cpu_count():
    assert sysinfo.get_cpu_count() >= 1


def test_get_cpu_model_from_proc():
    sample = "processor\t: 0\nvendor_id\t: GenuineIntel\nmodel name\t: Test CPU @ 1GHz\n"
    with mock.patch.object(sysinfo, "read_file", return_value=sample):
        assert sysinfo.get_cpu_model() == "Test CPU @ 1GHz"


def test_get_cpu_model_fallback():
    with mock.patch.object(sysinfo, "read_file", return_value=""):
        out = sysinfo.get_cpu_model()
    assert isinstance(out, str)


def test_get_meminfo():
    sample = "MemTotal:       16384 kB\nMemFree:         2048 kB\nMemAvailable:    4096 kB\n"
    with mock.patch.object(sysinfo, "read_file", return_value=sample):
        info = sysinfo.get_meminfo()
    assert info["MemTotal"] == 16384 * 1024
    assert info["MemAvailable"] == 4096 * 1024


def test_get_memory_summary_stdlib_path(monkeypatch):
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", False)
    sample = ("MemTotal:       1000 kB\nMemAvailable:   200 kB\nMemFree:        100 kB\n"
              "SwapTotal:      500 kB\nSwapFree:       250 kB\n")
    with mock.patch.object(sysinfo, "read_file", return_value=sample):
        mem = sysinfo.get_memory_summary()
    assert mem["total"] == 1000 * 1024
    assert mem["available"] == 200 * 1024
    assert mem["percent"] == 80
    assert mem["swap_total"] == 500 * 1024
    assert mem["swap_percent"] == 50


def test_get_memory_summary_no_swap(monkeypatch):
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", False)
    with mock.patch.object(sysinfo, "read_file", return_value="MemTotal: 0 kB\nMemFree: 0 kB\n"):
        mem = sysinfo.get_memory_summary()
    assert mem["swap_percent"] == 0
    assert mem["percent"] == 0


def test_get_memory_summary_psutil(monkeypatch):
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", True)
    fake_vm = mock.Mock(total=100, available=40, used=60, free=30, percent=60.0)
    fake_sw = mock.Mock(total=20, used=4, percent=20.0)
    fake_psutil = mock.Mock(virtual_memory=lambda: fake_vm, swap_memory=lambda: fake_sw)
    monkeypatch.setattr(sysinfo, "psutil", fake_psutil)
    mem = sysinfo.get_memory_summary()
    assert mem["total"] == 100
    assert mem["percent"] == 60
    assert mem["swap_total"] == 20


def test_get_mounts_filters_virtual():
    sample = (
        "proc /proc proc rw 0 0\n"
        "/dev/sda1 / ext4 rw 0 0\n"
        "tmpfs /tmp tmpfs rw 0 0\n"
        "/dev/sda1 / ext4 rw 0 0\n"  # duplicate target → skip
        "overlay /var/lib/docker/overlay2/x overlay rw 0 0\n"
        "/dev/sdb /data ext4 rw 0 0\n"
    )
    with mock.patch.object(sysinfo, "read_file", return_value=sample):
        mounts = sysinfo.get_mounts()
    targets = [m["target"] for m in mounts]
    assert "/" in targets
    assert "/data" in targets
    assert "/proc" not in targets
    assert "/tmp" not in targets


def test_get_disk_usage_returns_none_on_oserror():
    with mock.patch("wtftools.checks.sysinfo.shutil.disk_usage", side_effect=OSError):
        assert sysinfo.get_disk_usage("/nonexistent/path") is None


def test_get_disk_usage_ok(tmp_path):
    usage = sysinfo.get_disk_usage(str(tmp_path))
    assert usage is not None
    assert usage["total"] > 0
    assert 0 <= usage["percent"] <= 100


def test_get_disks_returns_list():
    fake_mounts = [{"target": "/x", "source": "/dev/sdx", "fstype": "ext4"}]
    fake_usage = {"total": 100, "used": 50, "free": 50, "percent": 50}
    with mock.patch.object(sysinfo, "get_mounts", return_value=fake_mounts), \
         mock.patch.object(sysinfo, "get_disk_usage", return_value=fake_usage):
        disks = sysinfo.get_disks()
    assert len(disks) == 1
    assert disks[0]["target"] == "/x"
    assert disks[0]["percent"] == 50


def test_get_disks_skips_none_usage():
    with mock.patch.object(sysinfo, "get_mounts",
                           return_value=[{"target": "/x", "source": "s", "fstype": "ext4"}]), \
         mock.patch.object(sysinfo, "get_disk_usage", return_value=None):
        disks = sysinfo.get_disks()
    assert disks == []


def test_count_zombie_processes_psutil(monkeypatch):
    fake_psutil = mock.Mock(STATUS_ZOMBIE="zombie")
    zombies = [mock.Mock(info={"status": "zombie"}), mock.Mock(info={"status": "running"})]
    fake_psutil.process_iter = lambda *_: zombies
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", True)
    monkeypatch.setattr(sysinfo, "psutil", fake_psutil)
    assert sysinfo.count_zombie_processes() == 1


def test_count_zombie_processes_fallback(monkeypatch):
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", False)
    with mock.patch.object(sysinfo, "run", return_value=(0, "Z\nS\nZ\nR\n", "")):
        assert sysinfo.count_zombie_processes() == 2


def test_count_zombie_processes_run_error(monkeypatch):
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", False)
    with mock.patch.object(sysinfo, "run", return_value=(1, "", "err")):
        assert sysinfo.count_zombie_processes() == 0


def test_get_failed_units_parse():
    out = "myunit.service loaded failed failed\n"
    with mock.patch.object(sysinfo, "run", return_value=(0, out, "")):
        units = sysinfo.get_failed_units()
    assert units == ["myunit.service"]


def test_get_failed_units_none():
    with mock.patch.object(sysinfo, "run", return_value=(0, "", "")):
        assert sysinfo.get_failed_units() == []


def test_get_failed_units_error():
    with mock.patch.object(sysinfo, "run", return_value=(127, "", "missing")):
        assert sysinfo.get_failed_units() == []


def test_get_oom_events_from_journal():
    out = "Oct 02 oom-killer: out of memory killed process 1234\n"
    with mock.patch.object(sysinfo, "run", return_value=(0, out, "")):
        events = sysinfo.get_oom_events()
    assert len(events) == 1


def test_get_oom_events_dmesg_fallback():
    def side_effect(cmd, **_):
        if cmd[0] == "journalctl":
            return (1, "", "fail")
        return (0, "oom-killer triggered\n", "")
    with mock.patch.object(sysinfo, "run", side_effect=side_effect):
        events = sysinfo.get_oom_events()
    assert len(events) == 1


def test_get_oom_events_none():
    with mock.patch.object(sysinfo, "run", return_value=(0, "regular log line\n", "")):
        assert sysinfo.get_oom_events() == []


def test_get_recent_kernel_errors_some():
    out = "line1\nline2\nline3\nline4\nline5\nline6\n"
    with mock.patch.object(sysinfo, "run", return_value=(0, out, "")):
        result = sysinfo.get_recent_kernel_errors(limit=3)
    assert result == ["line4", "line5", "line6"]


def test_get_recent_kernel_errors_empty():
    with mock.patch.object(sysinfo, "run", return_value=(0, "", "")):
        assert sysinfo.get_recent_kernel_errors() == []
    with mock.patch.object(sysinfo, "run", return_value=(1, "", "err")):
        assert sysinfo.get_recent_kernel_errors() == []


def test_get_listening_ports_psutil(monkeypatch):
    Conn = namedtuple("Conn", ["status", "type", "laddr", "pid"])
    Addr = namedtuple("Addr", ["ip", "port"])
    conns = [
        Conn("LISTEN", socket.SOCK_STREAM, Addr("0.0.0.0", 80), 1),
        Conn("LISTEN", socket.SOCK_DGRAM, Addr("0.0.0.0", 53), 2),  # filtered (udp)
        Conn("ESTABLISHED", socket.SOCK_STREAM, Addr("1.1.1.1", 443), 3),  # filtered
    ]
    fake = mock.Mock(CONN_LISTEN="LISTEN", net_connections=lambda kind: conns)
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", True)
    monkeypatch.setattr(sysinfo, "psutil", fake)
    ports = sysinfo.get_listening_ports()
    assert len(ports) == 1
    assert ports[0]["port"] == 80


def test_get_listening_ports_fallback(monkeypatch):
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", False)
    ss_out = "LISTEN 0 128 0.0.0.0:22 0.0.0.0:* \nLISTEN 0 128 [::]:80 [::]:* \n"
    with mock.patch.object(sysinfo, "run", return_value=(0, ss_out, "")):
        ports = sysinfo.get_listening_ports()
    assert {p["port"] for p in ports} == {22, 80}


def test_get_listening_ports_fallback_error(monkeypatch):
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", False)
    with mock.patch.object(sysinfo, "run", return_value=(1, "", "")):
        assert sysinfo.get_listening_ports() == []


def test_get_pending_updates_no_apt():
    with mock.patch("wtftools.checks.sysinfo.shutil.which", return_value=None):
        assert sysinfo.get_pending_updates() == -1


def test_get_pending_updates_with_apt():
    out = "Listing... Done\nfoo/jammy 1.2.3 amd64 [upgradable]\nbar/jammy 0.1 amd64 [upgradable]\n"
    with mock.patch("wtftools.checks.sysinfo.shutil.which", return_value="/usr/bin/apt"), \
         mock.patch.object(sysinfo, "run", return_value=(0, out, "")):
        assert sysinfo.get_pending_updates() == 2


def test_get_pending_updates_failure():
    with mock.patch("wtftools.checks.sysinfo.shutil.which", return_value="/usr/bin/apt"), \
         mock.patch.object(sysinfo, "run", return_value=(1, "", "")):
        assert sysinfo.get_pending_updates() == -1


def test_get_last_logins():
    with mock.patch.object(sysinfo, "run", return_value=(0, "alice tty 1\nbob tty 2\n", "")):
        out = sysinfo.get_last_logins(limit=2)
    assert len(out) == 2


def test_get_last_logins_error():
    with mock.patch.object(sysinfo, "run", return_value=(127, "", "")):
        assert sysinfo.get_last_logins() == []


def test_get_failed_auth_count_journal():
    sample = "Failed password for invalid user\nauthentication failure detected\nrandom line\n"
    with mock.patch.object(sysinfo, "run", return_value=(0, sample, "")):
        assert sysinfo.get_failed_auth_count() == 2


def test_get_failed_auth_count_authlog_fallback():
    sample = "Failed password for foo\nFailed password for bar\nFailed password for baz\n"
    with mock.patch.object(sysinfo, "run", return_value=(1, "", "")), mock.patch.object(sysinfo, "read_file", return_value=sample):
        assert sysinfo.get_failed_auth_count() == 3


def test_get_failed_auth_count_no_data():
    with mock.patch.object(sysinfo, "run", return_value=(1, "", "")), mock.patch.object(sysinfo, "read_file", return_value=""):
        assert sysinfo.get_failed_auth_count() == 0


def test_get_open_fds_valid():
    def mocked_read(path):
        if path.endswith("file-nr"):
            return "1024 0 99999\n"
        if path.endswith("file-max"):
            return "99999\n"
        return ""
    with mock.patch.object(sysinfo, "read_file", side_effect=mocked_read):
        used, total = sysinfo.get_open_fds()
    assert used == 1024
    assert total == 99999


def test_get_open_fds_invalid():
    with mock.patch.object(sysinfo, "read_file", return_value="garbage"):
        assert sysinfo.get_open_fds() is None


def test_get_network_interfaces_filters_virtual(monkeypatch):
    Addr = namedtuple("Addr", ["family", "address"])
    Stats = namedtuple("Stats", ["isup"])
    addrs = {
        "lo": [Addr(socket.AF_INET, "127.0.0.1")],
        "eth0": [Addr(socket.AF_INET, "10.0.0.1")],
        "veth123": [Addr(socket.AF_INET, "172.17.0.1")],
        "docker0": [Addr(socket.AF_INET, "172.17.0.1")],
    }
    stats = {"eth0": Stats(True), "veth123": Stats(True), "docker0": Stats(True)}
    fake = mock.Mock(net_if_addrs=lambda: addrs, net_if_stats=lambda: stats)
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", True)
    monkeypatch.setattr(sysinfo, "psutil", fake)
    result = sysinfo.get_network_interfaces()
    names = [r["name"] for r in result]
    assert names == ["eth0"]


def test_get_network_interfaces_include_virtual(monkeypatch):
    Addr = namedtuple("Addr", ["family", "address"])
    Stats = namedtuple("Stats", ["isup"])
    addrs = {"eth0": [Addr(socket.AF_INET, "10.0.0.1")], "veth": [Addr(socket.AF_INET, "1.1.1.1")]}
    stats = {"eth0": Stats(True), "veth": Stats(True)}
    fake = mock.Mock(net_if_addrs=lambda: addrs, net_if_stats=lambda: stats)
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", True)
    monkeypatch.setattr(sysinfo, "psutil", fake)
    result = sysinfo.get_network_interfaces(include_virtual=True)
    assert {r["name"] for r in result} == {"eth0", "veth"}


def test_get_network_interfaces_fallback(monkeypatch):
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", False)
    ip_out = "1: lo    inet 127.0.0.1/8 scope host lo\n2: eth0    inet 10.0.0.1/24 scope global eth0\n"
    with mock.patch.object(sysinfo, "run", return_value=(0, ip_out, "")):
        result = sysinfo.get_network_interfaces()
    assert any(r["name"] == "eth0" for r in result)


def test_get_network_interfaces_fallback_error(monkeypatch):
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", False)
    with mock.patch.object(sysinfo, "run", return_value=(1, "", "")):
        assert sysinfo.get_network_interfaces() == []


def test_top_processes_psutil(monkeypatch):
    fake_psutil = mock.Mock()
    fake_psutil.process_iter = mock.Mock(side_effect=[
        [],  # first call (warmup)
        [mock.Mock(info={"pid": 1, "name": "a", "username": "u",
                         "cpu_percent": 5.0, "memory_info": mock.Mock(rss=1024)}),
         mock.Mock(info={"pid": 2, "name": "b", "username": "u",
                         "cpu_percent": 50.0, "memory_info": mock.Mock(rss=2048)})],
    ])
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", True)
    monkeypatch.setattr(sysinfo, "psutil", fake_psutil)
    procs = sysinfo.get_top_processes(by="cpu", limit=2)
    assert procs[0]["cpu_percent"] == 50.0


def test_top_processes_fallback(monkeypatch):
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", False)
    out = "1 root 50.0 systemd\n2 alice 10.0 bash\n"
    with mock.patch.object(sysinfo, "run", return_value=(0, out, "")):
        procs = sysinfo.get_top_processes(by="cpu", limit=2)
    assert procs[0]["pid"] == 1
    assert procs[0]["cpu_percent"] == 50.0


def test_top_processes_fallback_rss(monkeypatch):
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", False)
    out = "1 root 1024 systemd\n2 alice 2048 bash\n"
    with mock.patch.object(sysinfo, "run", return_value=(0, out, "")):
        procs = sysinfo.get_top_processes(by="rss", limit=2)
    assert procs[0]["rss"] == 1024 * 1024  # ps gives kB


def test_top_processes_run_error(monkeypatch):
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", False)
    with mock.patch.object(sysinfo, "run", return_value=(1, "", "")):
        assert sysinfo.get_top_processes() == []


def test_get_system_running_state():
    with mock.patch.object(sysinfo, "run", return_value=(0, "running\n", "")):
        assert sysinfo.get_system_running_state() == "running"
    with mock.patch.object(sysinfo, "run", return_value=(127, "", "")):
        assert sysinfo.get_system_running_state() is None


def test_get_enabled_inactive_units_filters_oneshot():
    list_out = "unit_a.service enabled\nunit_b.service enabled\n"
    show_out = (
        "Id=unit_a.service\nActiveState=active\nSubState=running\nType=simple\nResult=success\n\n"
        "Id=unit_b.service\nActiveState=inactive\nSubState=dead\nType=oneshot\nResult=success\n"
    )

    def side_effect(cmd, **_):
        if "list-unit-files" in cmd:
            return (0, list_out, "")
        return (0, show_out, "")

    with mock.patch.object(sysinfo, "run", side_effect=side_effect):
        units = sysinfo.get_enabled_inactive_units()
    # b is oneshot → skipped; a is active → skipped
    assert units == []


def test_get_enabled_inactive_units_surface_failed():
    list_out = "ssh.service enabled\n"
    show_out = "Id=ssh.service\nActiveState=failed\nSubState=failed\nType=simple\nResult=exit-code\n"

    def side_effect(cmd, **_):
        if "list-unit-files" in cmd:
            return (0, list_out, "")
        return (0, show_out, "")

    with mock.patch.object(sysinfo, "run", side_effect=side_effect):
        units = sysinfo.get_enabled_inactive_units()
    assert len(units) == 1
    assert units[0]["state"] == "failed"


def test_get_enabled_inactive_units_no_systemctl():
    with mock.patch.object(sysinfo, "run", return_value=(127, "", "")):
        assert sysinfo.get_enabled_inactive_units() == []


def test_get_enabled_inactive_units_empty_list():
    with mock.patch.object(sysinfo, "run", return_value=(0, "", "")):
        assert sysinfo.get_enabled_inactive_units() == []


def test_get_reboot_required_present(monkeypatch, tmp_path):
    marker = tmp_path / "reboot-required"
    pkgs = tmp_path / "reboot-required.pkgs"
    marker.write_text("")
    pkgs.write_text("linux-image-6.8\nlibc6\n")

    def fake_exists(path):
        return path == str(marker)

    def fake_read(path):
        if path == str(pkgs):
            return pkgs.read_text()
        return ""

    monkeypatch.setattr(sysinfo.os.path, "exists", lambda p: p == "/var/run/reboot-required")
    with mock.patch.object(sysinfo, "read_file", return_value="linux-image-6.8\nlibc6\n"):
        msg = sysinfo.get_reboot_required()
    assert msg is not None
    assert "linux-image-6.8" in msg


def test_get_reboot_required_absent(monkeypatch):
    monkeypatch.setattr(sysinfo.os.path, "exists", lambda p: False)
    assert sysinfo.get_reboot_required() is None


def test_get_reboot_required_no_pkg_file(monkeypatch):
    monkeypatch.setattr(sysinfo.os.path, "exists", lambda p: p == "/var/run/reboot-required")
    with mock.patch.object(sysinfo, "read_file", return_value=""):
        msg = sysinfo.get_reboot_required()
    assert msg == "reboot required"


def test_get_time_sync_synced():
    out = "NTPSynchronized=yes\nNTP=yes\nCanNTP=yes\n"
    with mock.patch.object(sysinfo, "run", return_value=(0, out, "")):
        s = sysinfo.get_time_sync_status()
    assert s["synchronized"] is True
    assert s["ntp_active"] is True


def test_get_time_sync_missing():
    with mock.patch.object(sysinfo, "run", return_value=(127, "", "")):
        s = sysinfo.get_time_sync_status()
    assert s["synchronized"] is None
    assert "unavailable" in s["source"]


def test_get_time_sync_error():
    with mock.patch.object(sysinfo, "run", return_value=(1, "", "err")):
        s = sysinfo.get_time_sync_status()
    assert s["synchronized"] is None


def test_get_readonly_mounts_none():
    sample = "/dev/sda1 / ext4 rw,relatime 0 0\n"
    with mock.patch.object(sysinfo, "read_file", return_value=sample):
        assert sysinfo.get_readonly_mounts() == []


def test_get_readonly_mounts_detected():
    sample = (
        "/dev/sda1 / ext4 rw,relatime 0 0\n"
        "/dev/sdb1 /mnt/data ext4 ro,relatime 0 0\n"
        "/dev/loop1 /snap/foo squashfs ro 0 0\n"   # expected_ro → ignored
        "/dev/loop2 /mnt/cd iso9660 ro 0 0\n"      # expected_ro → ignored
    )
    with mock.patch.object(sysinfo, "read_file", return_value=sample):
        result = sysinfo.get_readonly_mounts()
    assert result == ["/mnt/data (ext4)"]


def test_get_stuck_processes_psutil(monkeypatch):
    fake_psutil = mock.Mock(STATUS_DISK_SLEEP="disk-sleep")
    procs = [
        mock.Mock(info={"pid": 1, "name": "io1", "status": "disk-sleep"}),
        mock.Mock(info={"pid": 2, "name": "ok", "status": "running"}),
    ]
    fake_psutil.process_iter = lambda *_: procs
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", True)
    monkeypatch.setattr(sysinfo, "psutil", fake_psutil)
    stuck = sysinfo.get_stuck_processes()
    assert len(stuck) == 1
    assert stuck[0]["pid"] == 1


def test_get_stuck_processes_fallback(monkeypatch):
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", False)
    out = "10 D mydaemon\n20 S other\n30 D+ readproc\n"
    with mock.patch.object(sysinfo, "run", return_value=(0, out, "")):
        stuck = sysinfo.get_stuck_processes()
    assert {p["pid"] for p in stuck} == {10, 30}


def test_get_stuck_processes_run_error(monkeypatch):
    monkeypatch.setattr(sysinfo, "HAS_PSUTIL", False)
    with mock.patch.object(sysinfo, "run", return_value=(1, "", "")):
        assert sysinfo.get_stuck_processes() == []


def test_get_iowait_percent_returns_float(monkeypatch):
    # Two snapshots: iowait grows from 100 to 200, total grows by 1000
    first = "cpu  100 0 100 800 100 0 0 0 0 0\n"
    second = "cpu  150 0 150 1300 200 0 0 0 0 0\n"
    state = {"calls": 0}

    def fake_read(path):
        if path == sysinfo.PROC_STAT:
            state["calls"] += 1
            return first if state["calls"] == 1 else second
        return ""

    monkeypatch.setattr(sysinfo, "read_file", fake_read)
    monkeypatch.setattr(sysinfo.time, "sleep", lambda _: None)
    iowait = sysinfo.get_iowait_percent()
    assert iowait is not None
    # delta iowait = 100, total delta = 50+50+500+100 = 700  → 14.29%
    assert 13.0 < iowait < 16.0


def test_get_iowait_percent_none_on_empty(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: "")
    monkeypatch.setattr(sysinfo.time, "sleep", lambda _: None)
    assert sysinfo.get_iowait_percent() is None


def test_get_iowait_percent_zero(monkeypatch):
    same = "cpu  100 0 100 800 100 0 0 0 0 0\n"
    monkeypatch.setattr(sysinfo, "read_file", lambda _: same)
    monkeypatch.setattr(sysinfo.time, "sleep", lambda _: None)
    assert sysinfo.get_iowait_percent() == 0.0


def test_get_pid_count(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: "32768\n")
    fake_entries = ["1", "2", "100", "self", "kmsg"]
    monkeypatch.setattr(sysinfo.os, "listdir", lambda _: fake_entries)
    count, pid_max = sysinfo.get_pid_count()
    assert count == 3
    assert pid_max == 32768


def test_get_pid_count_listdir_error(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: "")
    def boom(_):
        raise OSError("denied")
    monkeypatch.setattr(sysinfo.os, "listdir", boom)
    count, pid_max = sysinfo.get_pid_count()
    assert count == 0
    assert pid_max == 0
