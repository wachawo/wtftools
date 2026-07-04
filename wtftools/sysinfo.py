#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""System information gathering for wtftools.

Pure stdlib first, optional psutil for richer data.
"""

import json
import logging
import os
import platform
import re
import shutil
import socket
import subprocess
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import psutil  # type: ignore

    HAS_PSUTIL = True
except Exception:
    HAS_PSUTIL = False


PROC_MEMINFO = "/proc/meminfo"
PROC_UPTIME = "/proc/uptime"
PROC_LOADAVG = "/proc/loadavg"
PROC_STAT = "/proc/stat"
PROC_CPUINFO = "/proc/cpuinfo"
PROC_MOUNTS = "/proc/mounts"
PROC_MDSTAT = "/proc/mdstat"
ETC_OS_RELEASE = "/etc/os-release"


def run(cmd: List[str], timeout: int = 5) -> Tuple[int, str, str]:
    """Safely run a subprocess. Returns (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except FileNotFoundError:
        return 127, "", "not found"
    except Exception as exc:
        logger.debug(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
        return 1, "", str(exc)


def read_file(path: str) -> str:
    """Read a file, return empty string on error."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def get_hostname() -> str:
    return socket.gethostname()


def get_os_release() -> Dict[str, str]:
    """Parse /etc/os-release into a dict."""
    data: Dict[str, str] = {}
    content = read_file(ETC_OS_RELEASE)
    for line in content.splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def get_kernel() -> str:
    return platform.release()


def get_uptime_seconds() -> float:
    content = read_file(PROC_UPTIME)
    if not content:
        return 0.0
    try:
        return float(content.split()[0])
    except (ValueError, IndexError):
        return 0.0


def format_duration(seconds: float) -> str:
    """Render seconds as a compact human duration."""
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def format_bytes(num_bytes: float) -> str:
    """Render bytes as KB/MB/GB/TB (binary, 1024-based)."""
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f}{unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f}EB"


def format_bytes_si(num_bytes: float) -> str:
    """Render bytes with decimal (1000-based) units, matching `docker` output.

    Docker formats sizes with SI units (1GB = 1000MB), so `wtf docker` uses
    this to line up with `docker ps -s` / `docker container ls --size`.
    """
    value = float(num_bytes)
    for unit in ("B", "kB", "MB", "GB", "TB", "PB"):
        if abs(value) < 1000.0:
            if unit == "B":
                return f"{int(value)}B"
            return f"{value:.3g}{unit}"
        value /= 1000.0
    return f"{value:.3g}EB"


def get_loadavg() -> Tuple[float, float, float]:
    content = read_file(PROC_LOADAVG)
    if not content:
        return (0.0, 0.0, 0.0)
    parts = content.split()
    try:
        return (float(parts[0]), float(parts[1]), float(parts[2]))
    except (ValueError, IndexError):
        return (0.0, 0.0, 0.0)


def get_cpu_count() -> int:
    try:
        return os.cpu_count() or 1
    except Exception:
        return 1


def get_cpu_model() -> str:
    content = read_file(PROC_CPUINFO)
    for line in content.splitlines():
        if line.lower().startswith("model name"):
            _, _, value = line.partition(":")
            return value.strip()
    return platform.processor() or "unknown"


def get_meminfo() -> Dict[str, int]:
    """Read /proc/meminfo, return dict of kB values."""
    data: Dict[str, int] = {}
    content = read_file(PROC_MEMINFO)
    for line in content.splitlines():
        match = re.match(r"^(\S+):\s+(\d+)\s*kB", line)
        if match:
            data[match.group(1)] = int(match.group(2)) * 1024
    return data


def get_memory_summary() -> Dict[str, int]:
    """Return total/used/free/available memory in bytes."""
    if HAS_PSUTIL:
        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        return {
            "total": vm.total,
            "available": vm.available,
            "used": vm.used,
            "free": vm.free,
            "percent": int(vm.percent),
            "swap_total": sw.total,
            "swap_used": sw.used,
            "swap_percent": int(sw.percent),
        }
    info = get_meminfo()
    total = info.get("MemTotal", 0)
    free = info.get("MemFree", 0)
    available = info.get("MemAvailable", free)
    used = total - available
    percent = int(round(100 * used / total)) if total else 0
    swap_total = info.get("SwapTotal", 0)
    swap_free = info.get("SwapFree", 0)
    swap_used = swap_total - swap_free
    swap_percent = int(round(100 * swap_used / swap_total)) if swap_total else 0
    return {
        "total": total,
        "available": available,
        "used": used,
        "free": free,
        "percent": percent,
        "swap_total": swap_total,
        "swap_used": swap_used,
        "swap_percent": swap_percent,
    }


def get_mounts() -> List[Dict[str, str]]:
    """Read /proc/mounts. Filter out virtual / pseudo filesystems."""
    skip_fs = {
        "proc",
        "sysfs",
        "devtmpfs",
        "devpts",
        "tmpfs",
        "cgroup",
        "cgroup2",
        "pstore",
        "bpf",
        "tracefs",
        "debugfs",
        "fusectl",
        "configfs",
        "hugetlbfs",
        "mqueue",
        "rpc_pipefs",
        "binfmt_misc",
        "autofs",
        "securityfs",
        "selinuxfs",
        "fuse.gvfsd-fuse",
        "fuse.portal",
        "fuse.snapfuse",
        "nsfs",
        "ramfs",
        "fuse.lxcfs",
        "overlay",
        "squashfs",
    }
    content = read_file(PROC_MOUNTS)
    mounts: List[Dict[str, str]] = []
    seen_targets: set = set()
    for line in content.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        source, target, fs_type = parts[0], parts[1], parts[2]
        if fs_type in skip_fs:
            continue
        if target.startswith(("/snap", "/var/lib/docker/", "/var/lib/snapd/")):
            continue
        if target in seen_targets:
            continue
        seen_targets.add(target)
        mounts.append({"source": source, "target": target, "fstype": fs_type})
    return mounts


def get_disk_usage(target: str) -> Optional[Dict[str, int]]:
    """Return total/used/free bytes for a mount path."""
    try:
        usage = shutil.disk_usage(target)
    except OSError:
        return None
    percent = int(round(100 * usage.used / usage.total)) if usage.total else 0
    return {
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
        "percent": percent,
    }


def get_disks() -> List[Dict[str, Any]]:
    """Return a list of mount points with usage data."""
    result: List[Dict[str, Any]] = []
    for mount in get_mounts():
        usage = get_disk_usage(mount["target"])
        if usage is None:
            continue
        result.append(
            {
                "target": mount["target"],
                "source": mount["source"],
                "fstype": mount["fstype"],
                **usage,
            }
        )
    return result


def get_top_processes(by: str = "cpu", limit: int = 5) -> List[Dict[str, Any]]:
    """Return top processes by cpu or rss. Requires psutil or falls back to ps."""
    if HAS_PSUTIL:
        try:
            procs = []
            for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_info"]):
                procs.append(proc.info)
            time.sleep(0.1)
            procs = []
            for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_info"]):
                info = proc.info
                rss = info["memory_info"].rss if info.get("memory_info") else 0
                procs.append(
                    {
                        "pid": info.get("pid"),
                        "name": (info.get("name") or "")[:32],
                        "user": (info.get("username") or "")[:16],
                        "cpu_percent": info.get("cpu_percent") or 0.0,
                        "rss": rss,
                    }
                )
            key = "cpu_percent" if by == "cpu" else "rss"
            procs.sort(key=lambda p: p[key], reverse=True)
            return procs[:limit]
        except Exception as exc:
            logger.debug(f"psutil top failed: {exc}")
    # Fallback: ps
    sort = "%cpu" if by == "cpu" else "rss"
    rc, out, _ = run(["ps", "-eo", f"pid,user,{sort},comm", "--sort=-" + sort, "--no-headers"], timeout=5)
    if rc != 0 or not out:
        return []
    result: List[Dict[str, Any]] = []
    for line in out.splitlines()[:limit]:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, user, metric, comm = parts
        try:
            value = float(metric)
        except ValueError:
            value = 0.0
        item = {"pid": int(pid), "user": user, "name": comm}
        if by == "cpu":
            item["cpu_percent"] = value
            item["rss"] = 0
        else:
            item["rss"] = int(value) * 1024  # ps rss is in kB
            item["cpu_percent"] = 0.0
        result.append(item)
    return result


def count_zombie_processes() -> int:
    """Return number of zombie processes."""
    if HAS_PSUTIL:
        try:
            return sum(1 for p in psutil.process_iter(["status"]) if p.info.get("status") == psutil.STATUS_ZOMBIE)
        except Exception:
            pass
    rc, out, _ = run(["ps", "-eo", "stat", "--no-headers"], timeout=5)
    if rc != 0:
        return 0
    return sum(1 for line in out.splitlines() if line.strip().startswith("Z"))


def get_failed_units() -> List[str]:
    """List of failed systemd units."""
    rc, out, _ = run(["systemctl", "--failed", "--no-legend", "--plain", "--no-pager"], timeout=5)
    if rc != 0:
        return []
    units: List[str] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        unit = line.split()[0]
        if unit and unit != "0":
            units.append(unit)
    return units


def get_system_running_state() -> Optional[str]:
    """`systemctl is-system-running` — running / degraded / maintenance / etc."""
    rc, out, _ = run(["systemctl", "is-system-running"], timeout=5)
    if rc < 0 or rc == 127 or rc == 124:
        return None
    state = out.strip()
    return state or None


def get_enabled_inactive_units(limit: int = 200) -> List[Dict[str, str]]:
    """Enabled .service units whose ActiveState is not active and Type is not oneshot.

    Returns a list of dicts {name, state, sub, result}. Empty list when systemctl
    is unavailable or all enabled services are running fine.
    """
    rc, out, _ = run(
        ["systemctl", "list-unit-files", "--type=service", "--state=enabled", "--no-legend", "--no-pager"],
        timeout=8,
    )
    if rc != 0 or not out:
        return []
    enabled: List[str] = []
    for line in out.splitlines():
        parts = line.split()
        if parts:
            enabled.append(parts[0])
    enabled = enabled[:limit]
    if not enabled:
        return []

    rc, out, _ = run(
        ["systemctl", "show", "--property=Id,ActiveState,SubState,Type,Result"] + enabled,
        timeout=10,
    )
    if rc != 0 or not out:
        return []

    inactive: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    for line in out.splitlines():
        if not line.strip():
            if current:
                _maybe_collect_inactive(current, inactive)
            current = {}
            continue
        key, _, value = line.partition("=")
        current[key.strip()] = value.strip()
    if current:
        _maybe_collect_inactive(current, inactive)
    return inactive


def _maybe_collect_inactive(unit: Dict[str, str], out: List[Dict[str, str]]) -> None:
    """Append unit to `out` if it is enabled-but-not-running."""
    if unit.get("Type") in ("oneshot",):
        return
    state = unit.get("ActiveState")
    if state in ("active", "activating", "reloading"):
        return
    name = unit.get("Id")
    if not name:
        return
    out.append(
        {
            "name": name,
            "state": state or "unknown",
            "sub": unit.get("SubState", ""),
            "result": unit.get("Result", ""),
        }
    )


def get_reboot_required() -> Optional[str]:
    """Return reboot-required reason on Debian/Ubuntu, or None."""
    marker = "/var/run/reboot-required"
    if not os.path.exists(marker):
        return None
    pkgs = read_file("/var/run/reboot-required.pkgs").strip()
    if pkgs:
        first = pkgs.splitlines()[:3]
        return "reboot required ({} pkg(s)): {}".format(len(pkgs.splitlines()), ", ".join(first))
    return "reboot required"


def get_time_sync_status() -> Dict[str, Any]:
    """Return time sync info: {synchronized, ntp_active, source}."""
    rc, out, _ = run(
        ["timedatectl", "show", "-p", "NTPSynchronized", "-p", "NTP", "-p", "CanNTP"],
        timeout=5,
    )
    if rc == 127:
        return {"synchronized": None, "ntp_active": None, "source": "timedatectl unavailable"}
    if rc != 0 or not out:
        return {"synchronized": None, "ntp_active": None, "source": "timedatectl error"}
    fields: Dict[str, str] = {}
    for line in out.splitlines():
        key, _, value = line.partition("=")
        fields[key.strip()] = value.strip()
    return {
        "synchronized": fields.get("NTPSynchronized") == "yes",
        "ntp_active": fields.get("NTP") == "yes",
        "source": "timedatectl",
    }


def get_readonly_mounts() -> List[str]:
    """Return mounts that are read-only and where ro is unexpected (excludes squashfs, iso9660, cd, etc.)."""
    expected_ro = {"squashfs", "iso9660", "udf"}
    content = read_file(PROC_MOUNTS)
    result: List[str] = []
    skip_targets = ("/snap", "/proc", "/sys", "/dev", "/run", "/var/lib/docker", "/var/lib/snapd")
    for line in content.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        target, fs_type, opts = parts[1], parts[2], parts[3]
        if fs_type in expected_ro:
            continue
        if any(target.startswith(p) for p in skip_targets):
            continue
        flags = opts.split(",")
        if "ro" in flags:
            result.append(f"{target} ({fs_type})")
    return result


def _proc_comm(pid: str) -> str:
    """Process command name from /proc/<pid>/comm, '?' when unreadable."""
    return read_file(f"/proc/{pid}/comm").strip() or "?"


def get_md_arrays() -> Optional[List[Dict[str, Any]]]:
    """Software-RAID arrays from /proc/mdstat. None when md is not present."""
    content = read_file(PROC_MDSTAT)
    if not content:
        return None
    arrays: List[Dict[str, Any]] = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(md\d+)\s*:\s*(\S+)\s+(\S+)\s+", line)
        if not m:
            continue
        name, active, level = m.group(1), m.group(2), m.group(3)
        status, recovery = "", ""
        for nxt in lines[i + 1 : i + 4]:
            sm = re.search(r"\[([U_]+)\]", nxt)
            if sm:
                status = sm.group(1)
            rm = re.search(r"\b(recovery|resync|check|reshape)\s*=\s*([\d.]+%)", nxt)
            if rm:
                recovery = f"{rm.group(1)} {rm.group(2)}"
        arrays.append({"name": name, "active": active, "level": level, "status": status, "degraded": "_" in status, "recovery": recovery})
    return arrays


def get_deleted_open_files(min_bytes: int = 1024 * 1024) -> Optional[List[Dict[str, Any]]]:
    """Open fds pointing at deleted files that still hold >= min_bytes of disk.

    Returns [{pid, fd, name, path, bytes}] sorted biggest-first, or None if
    /proc is unreadable. Non-root callers only see their own processes.
    """
    if not os.path.isdir("/proc"):
        return None
    found: List[Dict[str, Any]] = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        fd_dir = f"/proc/{pid}/fd"
        try:
            fds = os.listdir(fd_dir)
        except OSError:
            continue
        for fd in fds:
            fd_path = os.path.join(fd_dir, fd)
            try:
                target = os.readlink(fd_path)
            except OSError:
                continue
            if not target.endswith(" (deleted)"):
                continue
            real = target[: -len(" (deleted)")]
            if real.startswith(("/dev/", "/memfd:", "anon_inode:", "/[")):
                continue
            try:
                st = os.stat(fd_path)
            except OSError:
                continue
            # st_blocks matches what df reports; st_size lies for sparse files.
            blocks = getattr(st, "st_blocks", None)
            size = blocks * 512 if blocks is not None else st.st_size
            if size < min_bytes:
                continue
            found.append({"pid": int(pid), "fd": int(fd), "name": _proc_comm(pid), "path": real, "bytes": size})
    found.sort(key=lambda f: f["bytes"], reverse=True)
    return found


def get_stale_lib_processes() -> Optional[List[Dict[str, Any]]]:
    """Processes with deleted shared libraries mapped in memory (they keep
    running old code until restarted, e.g. after `apt upgrade openssl`).

    Returns [{pid, name, libs}], or None if /proc is unreadable. Non-root
    callers only see their own processes.
    """
    if not os.path.isdir("/proc"):
        return None
    result: List[Dict[str, Any]] = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        maps = read_file(f"/proc/{pid}/maps")
        if not maps:
            continue
        stale = set()
        for line in maps.splitlines():
            if not line.endswith(" (deleted)"):
                continue
            parts = line.split(None, 5)
            if len(parts) < 6:
                continue
            real = parts[5][: -len(" (deleted)")]
            if ".so" not in real:
                continue
            if real.startswith(("/dev/", "/memfd:", "anon_inode:", "/[")):
                continue
            stale.add(real)
        if stale:
            result.append({"pid": int(pid), "name": _proc_comm(pid), "libs": sorted(stale)})
    return result


def get_stuck_processes() -> List[Dict[str, Any]]:
    """Return processes in D state (uninterruptible sleep, often IO-stuck)."""
    if HAS_PSUTIL:
        try:
            stuck: List[Dict[str, Any]] = []
            for proc in psutil.process_iter(["pid", "name", "status"]):
                if proc.info.get("status") == psutil.STATUS_DISK_SLEEP:
                    stuck.append({"pid": proc.info["pid"], "name": proc.info.get("name") or ""})
            return stuck
        except Exception:
            pass
    rc, out, _ = run(["ps", "-eo", "pid,stat,comm", "--no-headers"], timeout=5)
    if rc != 0:
        return []
    result: List[Dict[str, Any]] = []
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid, stat_field, comm = parts
        if stat_field.startswith("D"):
            try:
                result.append({"pid": int(pid), "name": comm})
            except ValueError:
                continue
    return result


def get_iowait_percent(sample_seconds: float = 0.3) -> Optional[float]:
    """Sample /proc/stat twice and return iowait percent."""

    def _snapshot() -> Optional[List[int]]:
        line = read_file(PROC_STAT).splitlines()
        if not line:
            return None
        parts = line[0].split()
        if parts[0] != "cpu" or len(parts) < 6:
            return None
        try:
            return [int(p) for p in parts[1:11]]
        except ValueError:
            return None

    first = _snapshot()
    if first is None:
        return None
    time.sleep(sample_seconds)
    second = _snapshot()
    if second is None:
        return None
    deltas = [b - a for a, b in zip(first, second)]
    total = sum(deltas)
    if total <= 0:
        return 0.0
    iowait = deltas[4] if len(deltas) > 4 else 0
    return round(100.0 * iowait / total, 2)


def get_service_restart_counts(threshold: int = 3, limit: int = 200) -> List[Dict[str, Any]]:
    """Active .service units with NRestarts >= threshold (since boot).

    NRestarts is cumulative — a single occasional crash isn't enough; the value
    being high indicates a service that systemd has had to bring back multiple
    times. Returns name + count sorted descending.
    """
    rc, out, _ = run(
        ["systemctl", "list-units", "--type=service", "--state=active", "--no-legend", "--no-pager", "--plain"],
        timeout=8,
    )
    if rc != 0 or not out:
        return []
    units: List[str] = []
    for line in out.splitlines():
        parts = line.split()
        if parts and parts[0].endswith(".service"):
            units.append(parts[0])
    units = units[:limit]
    if not units:
        return []
    rc, out, _ = run(["systemctl", "show", "-p", "Id", "-p", "NRestarts"] + units, timeout=10)
    if rc != 0 or not out:
        return []
    result: List[Dict[str, Any]] = []
    current: Dict[str, str] = {}
    for line in out.splitlines():
        if not line.strip():
            _maybe_collect_restarts(current, threshold, result)
            current = {}
            continue
        key, _, value = line.partition("=")
        current[key.strip()] = value.strip()
    _maybe_collect_restarts(current, threshold, result)
    result.sort(key=lambda r: r["restarts"], reverse=True)
    return result


def _maybe_collect_restarts(unit: Dict[str, str], threshold: int, out: List[Dict[str, Any]]) -> None:
    try:
        n = int(unit.get("NRestarts", "0"))
    except ValueError:
        return
    name = unit.get("Id")
    if not name or n < threshold:
        return
    out.append({"name": name, "restarts": n})


def get_network_errors() -> List[Dict[str, Any]]:
    """For each non-loopback, non-virtual interface read kernel error counters.

    Returns interfaces with at least one non-zero counter (rx/tx errors or drops).
    """
    base = "/sys/class/net"
    if not os.path.isdir(base):
        return []
    try:
        ifaces = sorted(os.listdir(base))
    except OSError:
        return []
    results: List[Dict[str, Any]] = []
    for iface in ifaces:
        if iface == "lo" or _is_noisy_iface(iface):
            continue
        stats_dir = os.path.join(base, iface, "statistics")
        if not os.path.isdir(stats_dir):
            continue

        # Bind stats_dir at def-time via default-arg to avoid late-binding
        # the loop variable (caught by B023).
        def _read_int(name: str, _dir: str = stats_dir) -> int:
            try:
                return int(read_file(os.path.join(_dir, name)).strip() or "0")
            except (ValueError, OSError):
                return 0

        rx_err = _read_int("rx_errors")
        tx_err = _read_int("tx_errors")
        rx_drop = _read_int("rx_dropped")
        tx_drop = _read_int("tx_dropped")
        total = rx_err + tx_err + rx_drop + tx_drop
        if total <= 0:
            continue
        results.append(
            {
                "iface": iface,
                "rx_errors": rx_err,
                "tx_errors": tx_err,
                "rx_dropped": rx_drop,
                "tx_dropped": tx_drop,
                "total": total,
            }
        )
    return results


def probe_http(url: str, timeout: float = 3.0) -> Dict[str, Any]:
    """HEAD-probe a URL. Returns {url, status_code, latency_ms, error}.

    Uses stdlib http.client to avoid requests-as-a-dep. Treats HTTP redirects
    as success (status_code is the first response code we see).
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return {"url": url, "status_code": None, "latency_ms": None, "error": f"unsupported scheme: {parsed.scheme}"}
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path += f"?{parsed.query}"

    started = time.monotonic()
    try:
        import http.client

        if parsed.scheme == "https":
            conn = http.client.HTTPSConnection(host, port, timeout=timeout)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
        try:
            conn.request("HEAD", path)
            resp = conn.getresponse()
            latency = (time.monotonic() - started) * 1000.0
            return {"url": url, "status_code": resp.status, "latency_ms": round(latency, 1), "error": None}
        finally:
            conn.close()
    except Exception as exc:
        return {"url": url, "status_code": None, "latency_ms": None, "error": f"{type(exc).__name__}: {exc}"}


def probe_tcp(target: str, timeout: float = 3.0) -> Dict[str, Any]:
    """Open a TCP socket to host:port. Returns {target, latency_ms, error}."""
    import socket as _socket

    if ":" not in target:
        return {"target": target, "latency_ms": None, "error": "expected host:port"}
    host, _, port_s = target.rpartition(":")
    try:
        port = int(port_s)
    except ValueError:
        return {"target": target, "latency_ms": None, "error": f"invalid port: {port_s}"}
    started = time.monotonic()
    try:
        sock = _socket.create_connection((host.strip("[]"), port), timeout=timeout)
        sock.close()
        latency = (time.monotonic() - started) * 1000.0
        return {"target": target, "latency_ms": round(latency, 1), "error": None}
    except Exception as exc:
        return {"target": target, "latency_ms": None, "error": f"{type(exc).__name__}: {exc}"}


def get_block_devices() -> List[str]:
    """Return /dev paths of physical block devices (excluding partitions / loops)."""
    import shutil

    if not shutil.which("lsblk"):
        return []
    rc, out, _ = run(["lsblk", "-dn", "-o", "NAME,TYPE"], timeout=5)
    if rc != 0:
        return []
    devices = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "disk" and not parts[0].startswith("loop"):
            devices.append(f"/dev/{parts[0]}")
    return devices


def get_smart_status() -> Optional[List[Dict[str, Any]]]:
    """Per-device SMART health (`smartctl -H -j`).

    Returns None when smartctl is unavailable. Empty list means smartctl is
    present but no block devices were found / accessible.
    """
    import shutil

    if not shutil.which("smartctl"):
        return None
    devices = get_block_devices()
    if not devices:
        return []
    import json as _json

    results: List[Dict[str, Any]] = []
    for dev in devices:
        rc, out, _ = run(["smartctl", "-H", "-j", dev], timeout=8)
        # smartctl exit codes are a bitfield: 0=ok, bit 0 (1) = cmd parse fail,
        # bit 1 (2) = device open failed, bit 2 (4) = some SMART command failed.
        # We try to parse JSON even on non-zero rc — smartctl emits JSON anyway.
        try:
            data = _json.loads(out)
        except (ValueError, _json.JSONDecodeError):
            continue
        smart = data.get("smart_status") or {}
        passed = smart.get("passed")
        msgs = data.get("messages") or []
        msg_text = "; ".join(m.get("string", "") for m in msgs if m.get("string"))
        if passed is None and rc != 0:
            # device probably doesn't support SMART; skip silently
            continue
        results.append(
            {
                "device": dev,
                "passed": bool(passed) if passed is not None else None,
                "exit_code": rc,
                "message": msg_text,
            }
        )
    return results


def get_temperatures() -> List[Dict[str, Any]]:
    """Read CPU/GPU/board temperatures from `/sys/class/hwmon/*/temp*_input`.

    Each value is millidegrees Celsius. Returns a list of
    {sensor, label, celsius}. Sensors that look broken (negative, absurd)
    are filtered out.
    """
    base = "/sys/class/hwmon"
    if not os.path.isdir(base):
        return []
    try:
        hwmons = sorted(os.listdir(base))
    except OSError:
        return []
    result: List[Dict[str, Any]] = []
    for hwmon in hwmons:
        hwmon_dir = os.path.join(base, hwmon)
        sensor_name = read_file(os.path.join(hwmon_dir, "name")).strip() or hwmon
        try:
            files = os.listdir(hwmon_dir)
        except OSError:
            continue
        for f in sorted(files):
            match = re.match(r"^temp(\d+)_input$", f)
            if not match:
                continue
            idx = match.group(1)
            value_raw = read_file(os.path.join(hwmon_dir, f)).strip()
            if not value_raw:
                continue
            try:
                value_mc = int(value_raw)
            except ValueError:
                continue
            celsius = value_mc / 1000.0
            # Filter obviously-broken sensors: negative, or absurdly high (>200°C).
            if celsius < -50 or celsius > 200:
                continue
            label_path = os.path.join(hwmon_dir, f"temp{idx}_label")
            label = read_file(label_path).strip() if os.path.exists(label_path) else f"temp{idx}"
            result.append(
                {
                    "sensor": sensor_name,
                    "label": label,
                    "celsius": round(celsius, 1),
                }
            )
    return result


def resolve_hostname(host: str, timeout: float = 2.0) -> Optional[float]:
    """Resolve a hostname via the system resolver. Returns ms elapsed, or None.

    Uses socket.gethostbyname with a deadline so a broken resolver does not
    hang the audit. We deliberately do NOT use any third-party resolver — we
    want to test whatever DNS the host itself is configured to use.
    """
    import socket

    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    started = time.monotonic()
    try:
        socket.gethostbyname(host)
        return (time.monotonic() - started) * 1000.0
    except (socket.gaierror, OSError, socket.timeout):
        return None
    finally:
        socket.setdefaulttimeout(old_timeout)


def get_fail2ban_jails() -> Optional[List[Dict[str, Any]]]:
    """List of {name, banned, total} per active fail2ban jail.

    None if fail2ban-client is missing or not running. Empty list means
    fail2ban is up but has no jails configured (rare).
    """
    import shutil

    if not shutil.which("fail2ban-client"):
        return None
    rc, out, _ = run(["fail2ban-client", "status"], timeout=5)
    if rc != 0 or not out:
        return None
    jail_names: List[str] = []
    for line in out.splitlines():
        # Example line: `|- Jail list:    sshd, recidive`
        if "Jail list" in line:
            _, _, rest = line.partition(":")
            jail_names = [j.strip() for j in rest.split(",") if j.strip()]
            break
    if not jail_names:
        return []
    jails: List[Dict[str, Any]] = []
    for name in jail_names:
        rc, jout, _ = run(["fail2ban-client", "status", name], timeout=5)
        if rc != 0:
            continue
        banned = 0
        total = 0
        for line in jout.splitlines():
            # fail2ban-client decorates lines with tree prefixes like `|-` or
            # `\`-`; strip those before matching the key.
            stripped = line.lstrip(" |`-\t")
            if stripped.startswith("Currently banned:"):
                try:
                    banned = int(stripped.partition(":")[2].strip())
                except (ValueError, IndexError):
                    banned = 0
            elif stripped.startswith("Total banned:"):
                try:
                    total = int(stripped.partition(":")[2].strip())
                except (ValueError, IndexError):
                    total = 0
        jails.append({"name": name, "banned": banned, "total": total})
    return jails


def get_chrony_offset() -> Optional[float]:
    """Return |system time offset from NTP source| in seconds via `chronyc tracking`.

    None if chrony is not the active NTP daemon or chronyc is unavailable.
    """
    import shutil

    if not shutil.which("chronyc"):
        return None
    rc, out, _ = run(["chronyc", "tracking"], timeout=5)
    if rc != 0 or not out:
        return None
    # Line example:
    #   "System time     : 0.000123456 seconds slow of NTP time"
    for line in out.splitlines():
        if "System time" not in line:
            continue
        match = re.search(r"([+-]?\d+(?:\.\d+)?)\s+seconds", line)
        if match:
            try:
                return abs(float(match.group(1)))
            except ValueError:
                return None
    return None


def get_docker_problem_containers() -> Optional[List[Dict[str, Any]]]:
    """List containers that are unhealthy or restart-looping.

    Returns None when docker is unavailable / daemon unreachable. Empty list
    means docker is reachable and nothing is misbehaving.
    """
    import shutil

    if not shutil.which("docker"):
        return None
    rc, out, _ = run(
        ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}\t{{.State}}"],
        timeout=8,
    )
    if rc != 0:
        return None
    problems: List[Dict[str, Any]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        name, status, state = parts[0], parts[1], parts[2]
        low_status = status.lower()
        low_state = state.lower()
        problem: Optional[str] = None
        if "unhealthy" in low_status:
            problem = "unhealthy"
        elif low_state == "restarting":
            problem = "restarting"
        # Note: exited containers are often intentional (init/one-shot jobs).
        # We surface them only when they exited with a non-zero code AND are
        # part of a restart-policy that should keep them alive — but discerning
        # that requires `docker inspect`. Skip exited containers for now.
        if problem:
            problems.append(
                {
                    "name": name,
                    "state": state,
                    "status": status,
                    "problem": problem,
                }
            )
    return problems


def get_conntrack_usage() -> Optional[Tuple[int, int]]:
    """Return (current_entries, max_entries) for the netfilter conntrack table.

    Path varies by distro/kernel — try the two known locations.
    """
    candidates = (
        ("/proc/sys/net/netfilter/nf_conntrack_count", "/proc/sys/net/netfilter/nf_conntrack_max"),
        ("/proc/sys/net/nf_conntrack_count", "/proc/sys/net/nf_conntrack_max"),
    )
    for count_path, max_path in candidates:
        count_raw = read_file(count_path).strip()
        max_raw = read_file(max_path).strip()
        if not count_raw or not max_raw:
            continue
        try:
            return int(count_raw), int(max_raw)
        except ValueError:
            continue
    return None


def get_top_paths_in(directory: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Return top-N largest immediate subdirectories of `directory` (du -d1).

    Used by `wtf explain --deep` to surface "who's eating the disk" when a
    disk-fill warning fires. Bounded by 15s — on huge trees `du` can run long.
    """
    import shutil

    if not shutil.which("du") or not os.path.isdir(directory):
        return []
    # --block-size=1 → bytes, -d1 → only direct children.
    rc, out, _ = run(["du", "-d1", "--block-size=1", directory], timeout=15)
    if rc != 0 or not out:
        return []
    results: List[Dict[str, Any]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        try:
            size = int(parts[0])
        except ValueError:
            continue
        path = parts[1]
        if path == directory:
            continue  # skip the directory itself (du -d1 emits it)
        results.append({"path": path, "bytes": size})
    results.sort(key=lambda r: r["bytes"], reverse=True)
    return results[:limit]


def get_largest_files(directory: str, limit: int = 5, min_size_mb: int = 100) -> List[Dict[str, Any]]:
    """Find regular files under `directory` larger than min_size_mb."""
    import shutil

    if not shutil.which("find") or not os.path.isdir(directory):
        return []
    rc, out, _ = run(
        ["find", directory, "-xdev", "-type", "f", "-size", f"+{min_size_mb}M", "-printf", "%s\t%p\n"],
        timeout=20,
    )
    if rc != 0 or not out:
        return []
    results: List[Dict[str, Any]] = []
    for line in out.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        try:
            size = int(parts[0])
        except ValueError:
            continue
        results.append({"path": parts[1], "bytes": size})
    results.sort(key=lambda r: r["bytes"], reverse=True)
    return results[:limit]


def get_docker_disk_usage() -> Optional[List[Dict[str, str]]]:
    """`docker system df` parsed into rows. None if docker missing/unreachable."""
    import shutil

    if not shutil.which("docker"):
        return None
    rc, out, _ = run(
        ["docker", "system", "df", "--format", "{{.Type}}\t{{.TotalCount}}\t{{.Size}}\t{{.Reclaimable}}"],
        timeout=8,
    )
    if rc != 0 or not out:
        return None
    rows: List[Dict[str, str]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            rows.append(
                {
                    "type": parts[0],
                    "count": parts[1],
                    "size": parts[2],
                    "reclaimable": parts[3],
                }
            )
    return rows


def get_docker_container_sizes(limit: int = 10) -> Optional[List[Dict[str, str]]]:
    """Per-container size breakdown (`docker ps -as`). None if docker missing.

    The `.Size` field reports `Rw+Vsize` — read-write layer plus base image.
    """
    import shutil

    if not shutil.which("docker"):
        return None
    rc, out, _ = run(
        ["docker", "ps", "-as", "--format", "{{.Names}}\t{{.Size}}\t{{.Image}}\t{{.Status}}"],
        timeout=8,
    )
    if rc != 0 or not out:
        return None
    rows: List[Dict[str, str]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            rows.append(
                {
                    "name": parts[0],
                    "size": parts[1],
                    "image": parts[2],
                    "status": parts[3],
                }
            )
    return rows[:limit]


def get_docker_log_sizes(limit: int = 5) -> Optional[List[Dict[str, Any]]]:
    """Per-container log-file size (json-file driver). None if docker missing.

    Reads each container's LogPath via `docker inspect`, stats it on the host
    filesystem. Requires the wtf process to have read access to the path —
    typically only root or the docker group.
    """
    import shutil

    if not shutil.which("docker"):
        return None
    rc, out, _ = run(["docker", "ps", "-aq"], timeout=5)
    if rc != 0 or not out:
        return None
    ids = [i for i in out.splitlines() if i.strip()]
    if not ids:
        return []
    rc, out, _ = run(
        ["docker", "inspect", "--format", "{{.Name}}\t{{.LogPath}}"] + ids,
        timeout=10,
    )
    if rc != 0 or not out:
        return None
    results: List[Dict[str, Any]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        name = parts[0].lstrip("/")
        log_path = parts[1]
        if not log_path or log_path == "<no value>":
            continue
        try:
            size = os.path.getsize(log_path)
        except OSError:
            continue
        results.append({"name": name, "log_path": log_path, "bytes": size})
    results.sort(key=lambda r: r["bytes"], reverse=True)
    return results[:limit]


def get_journal_disk_usage() -> Optional[int]:
    """Total bytes occupied by journald archives via `journalctl --disk-usage`."""
    rc, out, _ = run(["journalctl", "--disk-usage"], timeout=5)
    if rc != 0 or not out:
        return None
    # Output examples:
    #   "Archived and active journals take up 1.2G in the file system."
    #   "Archived and active journals take up 824.0M in the file system."
    #   "Archived and active journals take up 12.0G on disk."
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([KMGT])?B?", out)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    unit = match.group(2)
    return int(value * multipliers.get(unit, 1))


def get_pressure(resource: str) -> Optional[Dict[str, Dict[str, float]]]:
    """Read /proc/pressure/<resource> (PSI: cpu, memory, io). None if absent.

    Returns {"some": {"avg10":..., "avg60":..., "avg300":..., "total":...},
             "full": {...}}  (full is absent for cpu in older kernels).
    """
    if resource not in ("cpu", "memory", "io"):
        return None
    content = read_file(f"/proc/pressure/{resource}")
    if not content:
        return None
    result: Dict[str, Dict[str, float]] = {}
    for line in content.splitlines():
        parts = line.split()
        if not parts:
            continue
        scope = parts[0]
        if scope not in ("some", "full"):
            continue
        data: Dict[str, float] = {}
        for kv in parts[1:]:
            key, _, value = kv.partition("=")
            try:
                data[key] = float(value)
            except ValueError:
                continue
        result[scope] = data
    return result if result else None


def get_kernel_taint() -> Optional[int]:
    """Read /proc/sys/kernel/tainted. 0 = clean. Non-zero = kernel saw badness."""
    raw = read_file("/proc/sys/kernel/tainted").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


KERNEL_TAINT_BITS = {
    0: "PROPRIETARY_MODULE",
    1: "FORCED_MODULE",
    2: "UNSAFE_SMP",
    3: "FORCED_RMMOD",
    4: "MACHINE_CHECK",
    5: "BAD_PAGE",
    6: "USER",
    7: "DIE",
    8: "OVERRIDDEN_ACPI_TABLE",
    9: "WARN",
    10: "CRAP",
    11: "FIRMWARE_WORKAROUND",
    12: "OOT_MODULE",
    13: "UNSIGNED_MODULE",
    14: "SOFTLOCKUP",
    15: "LIVEPATCH",
}


def decode_kernel_taint(value: int) -> List[str]:
    """Decode a kernel taint bitmask into a list of flag names."""
    return [name for bit, name in KERNEL_TAINT_BITS.items() if value & (1 << bit)]


def get_certificate_expirations(
    roots: Optional[List[str]] = None,
    max_files: int = 50,
) -> List[Dict[str, Any]]:
    """Walk well-known TLS-cert roots and return list of {path, days_left}.

    Returns empty list when openssl is unavailable or no cert dirs exist.
    Bounded by max_files to avoid runaway IO on misconfigured hosts.
    """
    import shutil

    if not shutil.which("openssl"):
        return []
    if roots is None:
        # NB: /etc/ssl/certs is the system CA bundle (root CAs ship with
        # far-future or already-past notAfter dates intentionally) — scanning
        # it produces spam, so we focus on server-cert locations only.
        roots = [
            "/etc/letsencrypt/live",
            "/etc/letsencrypt/archive",
            "/etc/nginx/ssl",
            "/etc/nginx/certs",
            "/etc/apache2/ssl",
            "/etc/haproxy/certs",
            "/etc/pki/tls/private",
            "/etc/dovecot/certs",
            "/etc/postfix/certs",
            "/etc/ssl/private",
        ]
    candidates: List[str] = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, filenames in os.walk(root, followlinks=False):
            for f in filenames:
                low = f.lower()
                if not (low.endswith(".pem") or low.endswith(".crt") or low.endswith(".cert")):
                    continue
                # Skip private keys masquerading as .pem files.
                if "privkey" in low or "private" in low or "key" in low:
                    if "pubkey" not in low:
                        continue
                candidates.append(os.path.join(dirpath, f))
                if len(candidates) >= max_files:
                    break
            if len(candidates) >= max_files:
                break
        if len(candidates) >= max_files:
            break

    results: List[Dict[str, Any]] = []
    seen_inodes: set = set()
    for path in candidates:
        try:
            st = os.stat(path)
            if st.st_ino in seen_inodes:
                continue
            seen_inodes.add(st.st_ino)
        except OSError:
            continue
        days = _parse_cert_expiry_days(path)
        if days is None:
            continue
        results.append({"path": path, "days_left": days})
    results.sort(key=lambda r: r["days_left"])
    return results


def _parse_cert_expiry_days(path: str) -> Optional[int]:
    """Return days until notAfter, or None if unparseable / not a cert."""
    rc, out, _ = run(["openssl", "x509", "-enddate", "-noout", "-in", path], timeout=3)
    if rc != 0 or "=" not in out:
        return None
    _, _, when = out.strip().partition("=")
    when = when.strip()
    try:
        from datetime import datetime, timezone

        dt = datetime.strptime(when, "%b %d %H:%M:%S %Y %Z")
        delta = dt.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
        return delta.days
    except (ValueError, ImportError):
        return None


def _snap_tcp() -> Optional[Dict[str, int]]:
    """Snapshot of /proc/net/snmp Tcp counters."""
    content = read_file("/proc/net/snmp")
    if not content:
        return None
    header: Optional[List[str]] = None
    values: Optional[List[str]] = None
    for line in content.splitlines():
        if line.startswith("Tcp:"):
            parts = line.split()[1:]
            if header is None:
                header = parts
            else:
                values = parts
                break
    if not header or not values or len(header) != len(values):
        return None
    out: Dict[str, int] = {}
    for k, v in zip(header, values):
        try:
            out[k] = int(v)
        except ValueError:
            continue
    return out


def get_tcp_retransmit_rate(sample_seconds: float = 1.0) -> Optional[float]:
    """Sample TCP RetransSegs/OutSegs over a short window. Returns percent.

    Returns None when /proc/net/snmp is unreadable. Returns 0.0 when there was
    no outbound TCP traffic during the sample (rate is undefined; we treat it
    as "no problem").
    """
    first = _snap_tcp()
    if first is None:
        return None
    time.sleep(sample_seconds)
    second = _snap_tcp()
    if second is None:
        return None
    out_delta = second.get("OutSegs", 0) - first.get("OutSegs", 0)
    retr_delta = second.get("RetransSegs", 0) - first.get("RetransSegs", 0)
    if out_delta <= 0:
        return 0.0
    return round(100.0 * retr_delta / out_delta, 2)


def get_service_details(unit: str) -> Optional[Dict[str, Any]]:
    """Drilldown info for a single systemd unit. None if not found."""
    if "." not in unit:
        unit = f"{unit}.service"
    rc, out, _ = run(
        [
            "systemctl",
            "show",
            "-p",
            "Id",
            "-p",
            "Description",
            "-p",
            "LoadState",
            "-p",
            "ActiveState",
            "-p",
            "SubState",
            "-p",
            "Result",
            "-p",
            "UnitFileState",
            "-p",
            "MainPID",
            "-p",
            "NRestarts",
            "-p",
            "MemoryCurrent",
            "-p",
            "TasksCurrent",
            "-p",
            "ActiveEnterTimestamp",
            "-p",
            "ExecMainStartTimestamp",
            "-p",
            "FragmentPath",
            unit,
        ],
        timeout=8,
    )
    if rc != 0 or not out:
        return None
    data: Dict[str, str] = {}
    for line in out.splitlines():
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    if not data.get("Id") or data.get("LoadState") == "not-found":
        return None
    return data


def get_service_journal(unit: str, lines: int = 20) -> List[str]:
    """Recent journal lines for a single unit."""
    if "." not in unit:
        unit = f"{unit}.service"
    rc, out, _ = run(["journalctl", "-u", unit, "-n", str(lines), "--no-pager", "-q"], timeout=8)
    if rc != 0 or not out:
        return []
    return [line for line in out.splitlines() if line.strip()]


def get_pid_count() -> Tuple[int, int]:
    """Return (current process count, kernel pid_max)."""
    pid_max_raw = read_file("/proc/sys/kernel/pid_max").strip()
    try:
        pid_max = int(pid_max_raw)
    except ValueError:
        pid_max = 0
    count = 0
    try:
        for name in os.listdir("/proc"):
            if name.isdigit():
                count += 1
    except OSError:
        count = 0
    return count, pid_max


def get_oom_events(hours: int = 24) -> List[str]:
    """Find OOM-kill events in journal/dmesg from the recent window."""
    events: List[str] = []
    rc, out, _ = run(
        ["journalctl", "-k", "--since", f"{hours} hours ago", "--no-pager", "-q"],
        timeout=8,
    )
    if rc == 0 and out:
        for line in out.splitlines():
            low = line.lower()
            if "out of memory" in low or "killed process" in low or "oom-killer" in low:
                events.append(line.strip())
        return events
    # Fallback: dmesg (may need root)
    rc, out, _ = run(["dmesg", "-T"], timeout=5)
    if rc == 0:
        for line in out.splitlines():
            low = line.lower()
            if "out of memory" in low or "oom-killer" in low or "killed process" in low:
                events.append(line.strip())
    return events


def get_recent_kernel_errors(hours: int = 24, limit: int = 5) -> List[str]:
    """Recent kernel error/critical lines from journal."""
    rc, out, _ = run(
        ["journalctl", "-k", "-p", "err", "--since", f"{hours} hours ago", "--no-pager", "-q"],
        timeout=8,
    )
    if rc != 0 or not out:
        return []
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    return lines[-limit:]


def get_listening_ports() -> List[Dict[str, Any]]:
    """List of listening TCP ports."""
    if HAS_PSUTIL:
        try:
            ports: List[Dict[str, Any]] = []
            for conn in psutil.net_connections(kind="inet"):
                if conn.status != psutil.CONN_LISTEN:
                    continue
                if conn.type != socket.SOCK_STREAM:
                    continue
                if not conn.laddr:
                    continue
                ports.append(
                    {
                        "addr": conn.laddr.ip,
                        "port": conn.laddr.port,
                        "pid": conn.pid,
                    }
                )
            return ports
        except Exception:
            pass
    rc, out, _ = run(["ss", "-tlnH"], timeout=5)
    if rc != 0:
        return []
    ports = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        local = parts[3]
        if ":" not in local:
            continue
        addr, _, port = local.rpartition(":")
        try:
            ports.append({"addr": addr, "port": int(port), "pid": None})
        except ValueError:
            continue
    return ports


def get_pending_updates() -> int:
    """Count of pending apt updates. -1 if cannot determine."""
    if not shutil.which("apt"):
        return -1
    rc, out, _ = run(["apt", "list", "--upgradable"], timeout=10)
    if rc != 0:
        return -1
    count = 0
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("Listing"):
            continue
        count += 1
    return count


def get_last_logins(limit: int = 5) -> List[str]:
    """Recent successful logins via `last`."""
    rc, out, _ = run(["last", "-n", str(limit), "-F"], timeout=5)
    if rc != 0:
        return []
    return [line for line in out.splitlines()[:limit] if line.strip()]


def get_failed_auth_count(hours: int = 24) -> int:
    """Count of failed authentication events in the recent window."""
    rc, out, _ = run(
        ["journalctl", "_SYSTEMD_UNIT=ssh.service", "_SYSTEMD_UNIT=sshd.service", "--since", f"{hours} hours ago", "--no-pager", "-q"],
        timeout=8,
    )
    if rc != 0 or not out:
        # Fallback to /var/log/auth.log
        out = read_file("/var/log/auth.log")
        if not out:
            return 0
    count = 0
    for line in out.splitlines():
        low = line.lower()
        if "failed password" in low or "authentication failure" in low or "invalid user" in low:
            count += 1
    return count


def get_disk_io_busy() -> Optional[float]:
    """Average disk busy percent across all disks. Requires psutil."""
    if not HAS_PSUTIL:
        return None
    try:
        first = psutil.disk_io_counters(perdisk=False)
        if first is None:
            return None
        time.sleep(0.5)
        second = psutil.disk_io_counters(perdisk=False)
        if second is None:
            return None
        busy_delta = (second.busy_time - first.busy_time) if hasattr(second, "busy_time") else 0
        return float(busy_delta) / 5.0  # 500ms window, expressed as pct
    except Exception:
        return None


def get_open_fds() -> Optional[Tuple[int, int]]:
    """Return (used, max) open file descriptors."""
    fs_file_nr = read_file("/proc/sys/fs/file-nr")
    fs_file_max = read_file("/proc/sys/fs/file-max")
    try:
        used = int(fs_file_nr.split()[0])
    except (ValueError, IndexError):
        return None
    try:
        max_fd = int(fs_file_max.strip())
    except ValueError:
        return None
    return used, max_fd


def _is_noisy_iface(name: str) -> bool:
    """Filter out container/virtual interfaces from the default network listing."""
    noisy_prefixes = ("veth", "docker", "br-", "virbr", "cni", "flannel", "cali", "lxcbr", "tun", "tap")
    return any(name.startswith(p) for p in noisy_prefixes)


def get_network_interfaces(include_virtual: bool = False) -> List[Dict[str, Any]]:
    """List of non-loopback network interfaces with IPs."""
    result: List[Dict[str, Any]] = []
    if HAS_PSUTIL:
        try:
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            for name, addr_list in addrs.items():
                if name == "lo":
                    continue
                if not include_virtual and _is_noisy_iface(name):
                    continue
                ipv4 = [a.address for a in addr_list if a.family == socket.AF_INET]
                ipv6 = [a.address for a in addr_list if a.family == socket.AF_INET6 and not a.address.startswith("fe80")]
                is_up = stats.get(name).isup if name in stats else False
                result.append({"name": name, "ipv4": ipv4, "ipv6": ipv6, "up": is_up})
            return result
        except Exception:
            pass
    rc, out, _ = run(["ip", "-o", "-4", "addr", "show"], timeout=5)
    if rc != 0:
        return []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            name = parts[1]
            if name == "lo":
                continue
            if not include_virtual and _is_noisy_iface(name):
                continue
            ip = parts[3].split("/")[0]
            result.append({"name": name, "ipv4": [ip], "ipv6": [], "up": True})
    return result


def get_default_gateway() -> Optional[Dict[str, str]]:
    """Default IPv4 gateway from /proc/net/route. None when not found."""
    content = read_file("/proc/net/route")
    for line in content.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        iface, dest, gateway_hex = parts[0], parts[1], parts[2]
        if dest != "00000000":
            continue
        try:
            raw = int(gateway_hex, 16)
        except ValueError:
            continue
        ip = socket.inet_ntoa(raw.to_bytes(4, "little"))
        return {"gateway": ip, "iface": iface}
    return None


def get_dns_servers() -> List[str]:
    """Nameserver addresses from /etc/resolv.conf."""
    servers: List[str] = []
    for line in read_file("/etc/resolv.conf").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "nameserver":
            servers.append(parts[1])
    return servers


def get_logged_in_users() -> List[Dict[str, str]]:
    """Currently logged-in users (psutil, falling back to `who`)."""
    if HAS_PSUTIL:
        try:
            result: List[Dict[str, str]] = []
            for u in psutil.users():
                since = time.strftime("%Y-%m-%d %H:%M", time.localtime(u.started))
                result.append({"user": u.name, "tty": u.terminal or "-", "host": u.host or "-", "since": since})
            return result
        except Exception:
            pass
    rc, out, _ = run(["who"], timeout=5)
    if rc != 0:
        return []
    result = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        host = parts[4].strip("()") if len(parts) >= 5 else "-"
        result.append({"user": parts[0], "tty": parts[1], "host": host, "since": f"{parts[2]} {parts[3]}"})
    return result


def get_du_map(directory: str, max_depth: int = 1, timeout: int = 120) -> Dict[str, int]:
    """Map {abspath: cumulative_bytes} under `directory`, down to max_depth.

    `max_depth` counts levels below `directory` (1 = immediate children). Uses
    `du -x` (single filesystem). du exits non-zero on permission errors but
    still prints what it could read, so partial output is kept; an empty result
    means nothing was readable or the scan timed out. The timeout is generous
    because a cold scan of a multi-terabyte tree can take a minute or more.
    """
    if not shutil.which("du") or not os.path.isdir(directory):
        return {}
    directory = os.path.abspath(directory).rstrip("/") or "/"
    rc, out, _ = run(["du", "-x", f"-d{max_depth}", "--block-size=1", directory], timeout=timeout)
    if not out:
        return {}
    sizes: Dict[str, int] = {}
    for line in out.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        try:
            size = int(parts[0])
        except ValueError:
            continue
        sizes[parts[1].rstrip("/") or "/"] = size
    return sizes


def get_disk_io_per_device(sample_seconds: float = 0.5, limit: int = 5) -> List[Dict[str, Any]]:
    """Per-device IO rates sampled from /proc/diskstats over a short window."""

    def snapshot() -> Dict[str, Tuple[int, int, int]]:
        stats: Dict[str, Tuple[int, int, int]] = {}
        for line in read_file("/proc/diskstats").splitlines():
            parts = line.split()
            if len(parts) < 14:
                continue
            name = parts[2]
            if name.startswith(("loop", "ram", "zram")):
                continue
            try:
                stats[name] = (int(parts[5]), int(parts[9]), int(parts[12]))
            except ValueError:
                continue
        return stats

    first = snapshot()
    if not first:
        return []
    time.sleep(sample_seconds)
    second = snapshot()
    results: List[Dict[str, Any]] = []
    for name, (sectors_read2, sectors_written2, io_ticks2) in second.items():
        if name not in first:
            continue
        sectors_read1, sectors_written1, io_ticks1 = first[name]
        read_bps = (sectors_read2 - sectors_read1) * 512 / sample_seconds
        write_bps = (sectors_written2 - sectors_written1) * 512 / sample_seconds
        util = min(100.0, (io_ticks2 - io_ticks1) / (sample_seconds * 1000) * 100)
        results.append(
            {
                "device": name,
                "read_bps": int(read_bps),
                "write_bps": int(write_bps),
                "util_percent": round(util, 1),
            }
        )
    results.sort(key=lambda d: (d["util_percent"], d["read_bps"] + d["write_bps"]), reverse=True)
    return results[:limit]


def get_proc_info(pid: int) -> Dict[str, Any]:
    """Best-effort /proc enrichment for a PID: exe, cwd, cmdline, user.

    Reading /proc/<pid>/exe and /cwd needs privilege for other users'
    processes; unreadable fields come back as None rather than raising.
    """
    info: Dict[str, Any] = {"pid": pid, "exe": None, "cwd": None, "cmdline": None, "user": None}
    try:
        info["exe"] = os.readlink(f"/proc/{pid}/exe")
    except OSError:
        pass
    try:
        info["cwd"] = os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        pass
    raw = read_file(f"/proc/{pid}/cmdline")
    if raw:
        info["cmdline"] = raw.replace("\x00", " ").strip()
    try:
        import pwd

        uid = os.stat(f"/proc/{pid}").st_uid
        info["user"] = pwd.getpwuid(uid).pw_name
    except (OSError, KeyError):
        pass
    return info


def _port_map_lsof(port: int) -> Optional[List[Dict[str, Any]]]:
    """Processes on `port` via lsof. None if lsof is unavailable/unusable."""
    if not shutil.which("lsof"):
        return None
    rc, out, _ = run(["lsof", "-nP", f"-i:{port}"], timeout=8)
    # lsof exits 1 when nothing matches — that is an empty result, not an error.
    if rc not in (0, 1):
        return None
    entries: List[Dict[str, Any]] = []
    for line in out.splitlines():
        parts = line.split(None, 8)
        if len(parts) < 9 or parts[0] == "COMMAND":
            continue
        name = parts[8]
        if f":{port}" not in name:
            continue
        try:
            pid = int(parts[1])
        except ValueError:
            continue
        state = ""
        addr = name
        if "(" in name:
            addr, _, rest = name.partition("(")
            addr = addr.strip()
            state = rest.rstrip(")")
        entries.append({"pid": pid, "command": parts[0], "user": parts[2], "proto": parts[7].lower(), "addr": addr, "state": state})
    return entries


def _port_map_psutil(port: int) -> Optional[List[Dict[str, Any]]]:
    """Processes on `port` via psutil. None if psutil is unavailable."""
    if not HAS_PSUTIL:
        return None
    try:
        entries: List[Dict[str, Any]] = []
        for conn in psutil.net_connections(kind="inet"):
            if not conn.laddr or conn.laddr.port != port:
                continue
            proto = "tcp" if conn.type == socket.SOCK_STREAM else "udp"
            command = ""
            user = ""
            if conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    command = proc.name()
                    user = proc.username()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            entries.append({"pid": conn.pid, "command": command, "user": user, "proto": proto, "addr": f"{conn.laddr.ip}:{conn.laddr.port}", "state": conn.status or ""})
        return entries
    except Exception:
        return None


def _port_map_ss(port: int) -> Optional[List[Dict[str, Any]]]:
    """Processes on `port` via ss. None if ss is unusable."""
    if not shutil.which("ss"):
        return None
    rc, out, _ = run(["ss", "-tulnpH", f"( sport = :{port} )"], timeout=5)
    if rc != 0:
        return None
    entries: List[Dict[str, Any]] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        pid = None
        command = ""
        pid_match = re.search(r"pid=(\d+)", line)
        if pid_match:
            pid = int(pid_match.group(1))
        name_match = re.search(r'\("([^"]+)"', line)
        if name_match:
            command = name_match.group(1)
        entries.append({"pid": pid, "command": command, "user": "", "proto": parts[0], "addr": parts[4], "state": parts[1]})
    return entries


def get_port_processes(port: int) -> List[Dict[str, Any]]:
    """Return processes using `port` (any protocol/state), enriched via /proc.

    Source preference: lsof (what the user asked for), then psutil, then ss.
    Each entry carries proto, addr, state, pid, user, command, exe, cwd, cmdline.
    """
    entries = _port_map_lsof(port)
    if entries is None:
        entries = _port_map_psutil(port)
    if entries is None:
        entries = _port_map_ss(port)
    entries = entries or []
    for entry in entries:
        pid = entry.get("pid")
        if not pid:
            entry.setdefault("exe", None)
            entry.setdefault("cwd", None)
            entry.setdefault("cmdline", None)
            continue
        proc = get_proc_info(pid)
        entry["exe"] = proc["exe"]
        entry["cwd"] = proc["cwd"]
        entry["cmdline"] = proc["cmdline"] or entry.get("command")
        if not entry.get("user"):
            entry["user"] = proc["user"]
    return entries


def _docker_log_bytes(log_path: Optional[str]) -> Optional[int]:
    """Stat a container's json-file log on the host. None if absent/unreadable.

    Requires read access to the path under /var/lib/docker — usually root or
    the docker group. Permission errors degrade to None, not a crash.
    """
    if not log_path or log_path == "<no value>":
        return None
    try:
        return os.path.getsize(log_path)
    except OSError:
        return None


def get_docker_container_origin(name: str) -> Optional[Dict[str, Any]]:
    """Compose origin and on-disk sizes for one container via `docker inspect`.

    Returns image/status, the compose project/service/host working directory
    and config files, plus byte sizes: `image_bytes` (read-only image layers),
    `container_bytes` (the writable layer) and `logs_bytes` (json-file log).
    None when docker is missing or the container is unknown. `working_dir` is
    None for non-compose containers (docker does not record the host cwd of a
    plain `docker run`). Size fields are None when docker cannot report them
    (e.g. log file not readable without root).
    """
    if not shutil.which("docker"):
        return None
    rc, out, _ = run(["docker", "inspect", "--size", name], timeout=10)
    if rc != 0 or not out:
        return None
    try:
        data = json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return None
    if not data:
        return None
    container = data[0]
    config = container.get("Config") or {}
    labels = config.get("Labels") or {}
    state = container.get("State") or {}
    size_rw = container.get("SizeRw")
    size_root = container.get("SizeRootFs")
    image_bytes = size_root - size_rw if isinstance(size_rw, int) and isinstance(size_root, int) else size_root
    return {
        "name": (container.get("Name") or name).lstrip("/"),
        "image": config.get("Image", ""),
        "image_id": container.get("Image"),  # sha256 id, for deduping shared layers
        "status": state.get("Status", ""),
        "compose_project": labels.get("com.docker.compose.project"),
        "compose_service": labels.get("com.docker.compose.service"),
        "working_dir": labels.get("com.docker.compose.project.working_dir"),
        "config_files": labels.get("com.docker.compose.project.config_files"),
        "image_bytes": image_bytes,
        "container_bytes": size_rw,
        "logs_bytes": _docker_log_bytes(container.get("LogPath")),
    }


def get_docker_containers() -> Optional[List[Dict[str, Any]]]:
    """Running containers with their compose origin. None if docker is unusable."""
    if not shutil.which("docker"):
        return None
    rc, out, _ = run(["docker", "ps", "--format", "{{.Names}}"], timeout=8)
    if rc != 0:
        return None
    result: List[Dict[str, Any]] = []
    for name in out.splitlines():
        name = name.strip()
        if not name:
            continue
        info = get_docker_container_origin(name)
        if info:
            result.append(info)
    return result
