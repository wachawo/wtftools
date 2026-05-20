#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wtfd — background daemon: periodic audit + HTTP API.

Stdlib only. Single-process, thread-pool HTTP server. Designed to run under
systemd; binds to 127.0.0.1 by default and expects to be exposed (if at all)
behind nginx/haproxy with auth/TLS.

Endpoints:
    GET /              brief one-liner (same as `wtf audit --brief`)
    GET /healthz       liveness probe — always 200 if the daemon is up
    GET /audit         current state in plaintext audit format
    GET /audit.json    full audit as JSON (host, timestamp, results, summary)
    GET /audit.prom    Prometheus textfile-collector format
    GET /history       list of recent snapshot basenames
    GET /snapshot/N    nth-most-recent snapshot JSON

A scheduler thread re-runs the audit every --interval seconds and (optionally)
saves a snapshot. The HTTP server serves whatever the scheduler last wrote.
"""

import argparse
import http.server
import json
import logging
import os
import signal
import socketserver
import threading
import time
import traceback
from dataclasses import asdict
from typing import List, Optional

from wtftools import (
    __version__,
)
from wtftools import (
    audit as audit_mod,
)
from wtftools import (
    config as config_mod,
)
from wtftools import (
    snapshot as snapshot_mod,
)
from wtftools.checks import sysinfo

logger = logging.getLogger("wtfd")


class DaemonState:
    """Thread-safe holder for the last audit run."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._last_results: List[audit_mod.CheckResult] = []
        self._last_timestamp: Optional[float] = None
        self._last_error: Optional[str] = None
        self._run_count: int = 0
        # Wake-up flag the scheduler loop watches between sleeps. POST /run-now
        # sets this so the next iteration runs immediately.
        self._wake = threading.Event()
        self.host = sysinfo.get_hostname()
        self.started = time.time()

    def request_run_now(self) -> None:
        """Signal the scheduler to run an audit on the next loop tick (≤ 0.2s)."""
        self._wake.set()

    def wake_event(self) -> threading.Event:
        return self._wake

    def record_run(self, results: List[audit_mod.CheckResult]) -> None:
        with self._lock:
            self._last_results = list(results)
            self._last_timestamp = time.time()
            self._last_error = None
            self._run_count += 1

    def record_error(self, message: str) -> None:
        with self._lock:
            self._last_error = message

    @property
    def last_results(self) -> List[audit_mod.CheckResult]:
        with self._lock:
            return list(self._last_results)

    @property
    def last_timestamp(self) -> Optional[float]:
        with self._lock:
            return self._last_timestamp

    @property
    def last_error(self) -> Optional[str]:
        with self._lock:
            return self._last_error

    @property
    def run_count(self) -> int:
        with self._lock:
            return self._run_count


def _audit_loop(state: DaemonState, interval: float,
                stop_event: threading.Event, save_snapshots: bool) -> None:
    """Worker thread: run audit on a cadence (or on demand via /run-now)."""
    wake = state.wake_event()
    while not stop_event.is_set():
        try:
            results = audit_mod.run_audit()
            state.record_run(results)
            if save_snapshots:
                snapshot_mod.save_snapshot(results, host=state.host)
        except Exception as exc:
            state.record_error(f"{type(exc).__name__}: {exc}")
            logger.warning(
                f"audit loop error: {type(exc).__name__}: {exc}\n"
                f"{traceback.format_exc()}"
            )
        # Wait the configured interval — but break out early if either:
        #   - stop_event fires (graceful shutdown, SIGTERM)
        #   - wake fires (POST /run-now)
        # We split the wait so both signals are honored without busy-looping.
        deadline = time.monotonic() + interval
        while not stop_event.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if wake.wait(min(remaining, 1.0)):
                wake.clear()
                break


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """One thread per request — fine for our tiny endpoint set."""
    daemon_threads = True
    allow_reuse_address = True


def make_handler(state: DaemonState, auth_token: Optional[str] = None):
    """Build a request handler bound to this DaemonState."""

    class WTFHandler(http.server.BaseHTTPRequestHandler):
        server_version = f"wtfd/{__version__}"

        # ----- helpers -----

        def _authorized(self) -> bool:
            if not auth_token:
                return True
            header = self.headers.get("Authorization", "")
            return header == f"Bearer {auth_token}"

        def _send(self, status: int, body: str,
                  content_type: str = "text/plain; charset=utf-8") -> None:
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            if state.last_timestamp:
                self.send_header("X-WTF-Last-Audit", str(int(state.last_timestamp)))
            self.send_header("X-WTF-Host", state.host)
            self.send_header("X-WTF-Version", __version__)
            self.end_headers()
            self.wfile.write(data)

        def _send_json(self, status: int, obj: dict) -> None:
            self._send(status, json.dumps(obj, indent=2, default=str),
                       content_type="application/json")

        # ----- routes -----

        def do_GET(self) -> None:  # noqa: N802 — stdlib API
            if not self._authorized():
                self._send(401, "unauthorized\n")
                return
            path = self.path.split("?", 1)[0].rstrip("/")
            if path in ("", "/"):
                self._send(200, self._brief())
            elif path == "/healthz":
                self._send(200, "ok\n")
            elif path in ("/audit", "/audit.txt"):
                self._send(200, self._audit_text())
            elif path == "/audit.json":
                self._send_json(200, self._audit_dict())
            elif path == "/audit.prom":
                body = audit_mod.render_prometheus(state.last_results)
                self._send(200, body,
                           content_type="text/plain; version=0.0.4; charset=utf-8")
            elif path == "/history":
                self._send_json(200, self._history_dict())
            elif path.startswith("/snapshot/"):
                self._serve_snapshot(path[len("/snapshot/"):])
            else:
                self._send(404, "not found\n")

        def do_POST(self) -> None:  # noqa: N802 — stdlib API
            if not self._authorized():
                self._send(401, "unauthorized\n")
                return
            path = self.path.split("?", 1)[0].rstrip("/")
            if path == "/run-now":
                state.request_run_now()
                self._send(202, "audit requested\n")
            else:
                self._send(404, "not found\n")

        def log_message(self, fmt, *args) -> None:  # noqa: N802
            logger.info(f"{self.address_string()} {fmt % args}")

        def _brief(self) -> str:
            results = state.last_results
            if not results:
                return f"wtfd: warming up (host={state.host}, started {int(time.time() - state.started)}s ago)\n"
            totals = audit_mod.summarize(results)
            problems = [r for r in results if r.status in ("fail", "warn")]
            head = (f"host={state.host}  "
                    f"runs={state.run_count}  "
                    f"fail={totals['fail']}  warn={totals['warn']}  "
                    f"ok={totals['ok']}  skip={totals['skip']}")
            if not problems:
                return head + "\nall good\n"
            short = "; ".join(f"{p.name}: {p.message[:60]}" for p in problems[:5])
            tail = f"\nproblems: {short}"
            if len(problems) > 5:
                tail += f"  (+{len(problems) - 5} more)"
            return head + tail + "\n"

        def _audit_text(self) -> str:
            results = state.last_results
            if not results:
                return f"wtfd: warming up (host={state.host})\n"
            markers = {"ok": "[ OK ]", "warn": "[WARN]",
                       "fail": "[FAIL]", "skip": "[SKIP]"}
            lines = []
            for r in results:
                marker = markers.get(r.status, "[????]")
                lines.append(f"{marker} {r.name:<30} {r.message}")
            return "\n".join(lines) + "\n"

        def _audit_dict(self) -> dict:
            return {
                "host": state.host,
                "version": __version__,
                "timestamp": state.last_timestamp,
                "run_count": state.run_count,
                "results": [asdict(r) for r in state.last_results],
                "summary": audit_mod.summarize(state.last_results),
                "error": state.last_error,
            }

        def _history_dict(self) -> dict:
            paths = snapshot_mod.list_snapshots()
            return {
                "host": state.host,
                "snapshot_dir": snapshot_mod.default_snapshot_dir(),
                "snapshots": [os.path.basename(p) for p in paths[-30:]],
            }

        def _serve_snapshot(self, identifier: str) -> None:
            paths = snapshot_mod.list_snapshots()
            try:
                idx = int(identifier)
                target_idx = len(paths) - 1 - idx
                if target_idx < 0 or target_idx >= len(paths):
                    self._send(404, "snapshot index out of range\n")
                    return
                target = paths[target_idx]
            except ValueError:
                matches = [p for p in paths if os.path.basename(p).startswith(identifier)]
                if not matches:
                    self._send(404, "no matching snapshot\n")
                    return
                target = matches[-1]
            data = snapshot_mod.load_snapshot(target)
            if data is None:
                self._send(500, "snapshot unreadable\n")
                return
            self._send_json(200, data)

    return WTFHandler


def serve(host: str, port: int, interval: float, save_snapshots: bool,
          auth_token: Optional[str] = None,
          stop_event: Optional[threading.Event] = None) -> int:
    """Run the daemon. Blocking. Returns 0 on graceful shutdown.

    `stop_event` lets tests stop the daemon programmatically.
    """
    state = DaemonState()
    stop = stop_event or threading.Event()

    # Kick off scheduler thread.
    sched = threading.Thread(
        target=_audit_loop,
        args=(state, interval, stop, save_snapshots),
        name="wtfd-scheduler",
        daemon=True,
    )
    sched.start()

    handler_cls = make_handler(state, auth_token=auth_token)
    server = ThreadingHTTPServer((host, port), handler_cls)

    def _shutdown(_signum=None, _frame=None) -> None:
        stop.set()
        # server.shutdown is safe to call from a signal handler in CPython.
        threading.Thread(target=server.shutdown, daemon=True).start()

    # When wired into systemd / a TTY, SIGTERM/SIGINT trigger graceful exit.
    # In tests we omit the signal hookup (signals only work on main thread).
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)

    auth_note = "  [auth: bearer token]" if auth_token else ""
    logger.info(
        f"wtfd {__version__} listening on http://{host}:{port}{auth_note} "
        f"· audit every {interval}s · snapshots={'on' if save_snapshots else 'off'}"
    )
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        stop.set()
        server.server_close()
    return 0


def cli_main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the standalone `wtfd` console script."""
    parser = argparse.ArgumentParser(
        prog="wtfd",
        description=f"wtftools background daemon ({__version__})",
    )
    parser.add_argument("--listen", default="127.0.0.1:8765", metavar="HOST:PORT",
                        help="Bind address (default: 127.0.0.1:8765)")
    parser.add_argument("--interval", type=float, default=300.0,
                        help="Audit cadence in seconds (default: 300 = 5 min)")
    parser.add_argument("--save", action="store_true",
                        help="Persist every audit as a snapshot")
    parser.add_argument("--auth-token-file", metavar="PATH",
                        help="If set, requires `Authorization: Bearer <token>` on all "
                             "endpoints. The token is read from this file.")
    parser.add_argument("--config", metavar="PATH",
                        help="Extra wtftools config file (stacks on default paths)")
    parser.add_argument("-V", "--version", action="version",
                        version=f"wtfd {__version__}")

    args = parser.parse_args(argv)

    # Configure logging — same format wtf uses elsewhere.
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d [%(levelname)s]: (%(name)s) %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )

    paths = list(config_mod.DEFAULT_CONFIG_PATHS)
    if args.config:
        paths.append(args.config)
    config_mod.set_config(config_mod.load_config(paths))

    if ":" not in args.listen:
        logger.error("invalid --listen: expected HOST:PORT")
        return 2
    host, _, port_s = args.listen.rpartition(":")
    try:
        port = int(port_s)
    except ValueError:
        logger.error(f"invalid port: {port_s}")
        return 2
    host = host.strip("[]") or "127.0.0.1"

    token: Optional[str] = None
    if args.auth_token_file:
        try:
            with open(args.auth_token_file, encoding="utf-8") as f:
                token = f.read().strip()
        except OSError as exc:
            logger.error(f"cannot read auth token file: {exc}")
            return 2
        if not token:
            logger.error(f"auth token file is empty: {args.auth_token_file}")
            return 2

    return serve(host, port, args.interval, args.save, auth_token=token)


if __name__ == "__main__":
    raise SystemExit(cli_main())
