#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fleet aggregation: pull `/audit.json` from many wtfd peers and merge.

Pure stdlib: urllib for HTTP, concurrent.futures for parallel fetches.

The peer endpoint contract is the JSON that `wtfd` already serves at
`/audit.json` — every wtftools-running host can be a peer without extra work.
"""

import json
import logging
import socket
import time
import traceback
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FleetHost:
    """One host's state as reported by its wtfd."""
    target: str                          # raw user-supplied target (host:port or URL)
    url: str                             # resolved full URL
    ok: bool = False                     # True if we got a response we could parse
    error: Optional[str] = None          # populated when ok is False
    host: Optional[str] = None           # hostname reported by the daemon
    timestamp: Optional[float] = None
    summary: Dict[str, int] = field(default_factory=lambda: {"ok": 0, "warn": 0,
                                                             "fail": 0, "skip": 0})
    results: List[Dict] = field(default_factory=list)
    latency_ms: Optional[float] = None


def _normalize(target: str) -> str:
    """Turn `host:port` or `host` into a full URL with the audit path."""
    if target.startswith(("http://", "https://")):
        base = target.rstrip("/")
    else:
        base = f"http://{target.strip('/')}"
    return base + "/audit.json"


def fetch_one(target: str, timeout: float = 5.0,
              token: Optional[str] = None) -> FleetHost:
    """Fetch one peer's audit. Always returns a FleetHost — never raises."""
    url = _normalize(target)
    headers = {"User-Agent": "wtftools/fleet"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    started = time.monotonic()
    out = FleetHost(target=target, url=url)
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            out.host = data.get("host")
            out.timestamp = data.get("timestamp")
            out.summary = data.get("summary") or out.summary
            out.results = data.get("results") or []
            out.ok = True
    except urllib.error.HTTPError as exc:
        out.error = f"HTTP {exc.code} {exc.reason}"
    except urllib.error.URLError as exc:
        out.error = f"connection error: {exc.reason}"
    except socket.timeout:
        out.error = f"timeout after {timeout}s"
    except (json.JSONDecodeError, ValueError) as exc:
        out.error = f"invalid JSON: {exc}"
    except Exception as exc:
        out.error = f"{type(exc).__name__}: {exc}"
        logger.debug(f"fetch_one({target}) failed:\n{traceback.format_exc()}")
    out.latency_ms = round((time.monotonic() - started) * 1000.0, 1)
    return out


def trigger_run_now(targets: List[str], timeout: float = 2.0,
                    workers: int = 16,
                    token: Optional[str] = None) -> dict:
    """Best-effort POST /run-now on every target. Returns {target: ok|error}.

    Errors are not raised — the caller is expected to follow this with
    `fetch_all`, which still works even if /run-now failed on some peers.
    """
    if not targets:
        return {}
    headers = {"User-Agent": "wtftools/fleet"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def _one(target: str) -> tuple:
        url = _normalize(target).replace("/audit.json", "/run-now")
        try:
            req = urllib.request.Request(url, data=b"", method="POST",
                                         headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return target, "ok" if resp.status in (200, 202) else f"HTTP {resp.status}"
        except urllib.error.HTTPError as exc:
            return target, f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            return target, f"connection error: {exc.reason}"
        except socket.timeout:
            return target, f"timeout after {timeout}s"
        except Exception as exc:
            return target, f"{type(exc).__name__}: {exc}"

    results: dict = {}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(targets)))) as pool:
        for fut in as_completed(pool.submit(_one, t) for t in targets):
            try:
                target, status = fut.result()
                results[target] = status
            except Exception as exc:
                results["_error"] = f"{type(exc).__name__}: {exc}"
    return results


def fetch_all(targets: List[str], timeout: float = 5.0,
              workers: int = 16,
              token: Optional[str] = None) -> List[FleetHost]:
    """Parallel fetch. Preserves submission order in the returned list."""
    if not targets:
        return []
    results: Dict[int, FleetHost] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(targets)))) as pool:
        futures = {
            pool.submit(fetch_one, target, timeout, token): idx
            for idx, target in enumerate(targets)
        }
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                results[idx] = fut.result()
            except Exception as exc:
                # Should never happen — fetch_one swallows everything.
                results[idx] = FleetHost(
                    target=targets[idx], url=_normalize(targets[idx]),
                    error=f"{type(exc).__name__}: {exc}",
                )
    return [results[i] for i in range(len(targets))]


def aggregate_summary(hosts: List[FleetHost]) -> Dict[str, int]:
    """Sum per-status counts across all reachable hosts."""
    totals = {"ok": 0, "warn": 0, "fail": 0, "skip": 0, "unreachable": 0}
    for h in hosts:
        if not h.ok:
            totals["unreachable"] += 1
            continue
        for k in ("ok", "warn", "fail", "skip"):
            totals[k] += h.summary.get(k, 0)
    return totals


def host_severity(h: FleetHost) -> int:
    """Sortable severity: lower is worse.

    -3 unreachable, -2 has fail, -1 has warn, 0 all-OK.
    Used to put problems first in the fleet listing.
    """
    if not h.ok:
        return -3
    if h.summary.get("fail", 0) > 0:
        return -2
    if h.summary.get("warn", 0) > 0:
        return -1
    return 0


@dataclass
class CompareRow:
    """One row in the side-by-side compare view."""
    name: str
    kind: str             # same | differ | a-only | b-only | both-missing
    a_status: Optional[str] = None
    b_status: Optional[str] = None
    a_message: Optional[str] = None
    b_message: Optional[str] = None


def compare_hosts(host_a: FleetHost, host_b: FleetHost) -> List[CompareRow]:
    """Build the merged list of comparison rows for two host audits.

    Both hosts must have ok=True for the comparison to make sense; the caller
    should surface unreachable hosts separately.
    """
    a_results = {r["name"]: r for r in (host_a.results or [])}
    b_results = {r["name"]: r for r in (host_b.results or [])}
    all_names = list(dict.fromkeys(list(a_results.keys()) + list(b_results.keys())))

    rows: List[CompareRow] = []
    for name in all_names:
        ra = a_results.get(name)
        rb = b_results.get(name)
        if ra is None:
            rows.append(CompareRow(name=name, kind="b-only",
                                   b_status=rb.get("status"),
                                   b_message=rb.get("message", "")))
            continue
        if rb is None:
            rows.append(CompareRow(name=name, kind="a-only",
                                   a_status=ra.get("status"),
                                   a_message=ra.get("message", "")))
            continue
        same_status = ra.get("status") == rb.get("status")
        same_message = ra.get("message") == rb.get("message")
        rows.append(CompareRow(
            name=name,
            kind="same" if (same_status and same_message) else "differ",
            a_status=ra.get("status"), b_status=rb.get("status"),
            a_message=ra.get("message", ""), b_message=rb.get("message", ""),
        ))
    return rows


def render_prometheus(hosts: List[FleetHost]) -> str:
    """Fleet view as Prometheus textfile-collector format."""
    lines = [
        "# HELP wtf_fleet_host_status Per-host result counts (0=ok,1=warn,2=fail,3=skip)",
        "# TYPE wtf_fleet_host_status gauge",
        "# HELP wtf_fleet_host_up Reachable boolean (1=up, 0=down)",
        "# TYPE wtf_fleet_host_up gauge",
    ]
    for h in hosts:
        label_host = (h.host or h.target).replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'wtf_fleet_host_up{{host="{label_host}"}} {1 if h.ok else 0}')
        for status_name in ("ok", "warn", "fail", "skip"):
            lines.append(
                f'wtf_fleet_summary_count{{host="{label_host}",status="{status_name}"}} '
                f'{h.summary.get(status_name, 0)}'
            )
    return "\n".join(lines) + "\n"
