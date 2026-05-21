# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed — plugin infrastructure
- `wtftools/plugin_sdk.py` — Python helper for plugin authors.
- `wtftools/checks/plugins.py` — discovery / executor / parser for
  `/etc/wtf/checks.d/` scripts (bash + Python).
- `_plugin_to_check` + `_all_check_callables` glue in `wtftools/audit.py`.
- `tests/test_plugins.py`, `tests/test_iteration16.py`.
- README's «Plugins» section and QUICKSTART's «Custom checks (plugins)»
  section.

The CLI is now a closed set of built-in checks. Custom logic should live
upstream (e.g. monitoring tools) or be added as new built-in checks via PR.

### Changed — layout flattening
- `wtftools/checks/cron.py` → `wtftools/cron.py`
- `wtftools/checks/sysinfo.py` → `wtftools/sysinfo.py`
- `wtftools/checks/` subpackage removed (`__init__.py` deleted).
- All imports updated: `from wtftools.checks import X` → `from wtftools import X`.

### Build & release
- `release.yml` no longer publishes a Docker image to GHCR. On a `v*` /
  `*.*.*` tag it now runs tests, builds a `.deb` via `scripts/build-deb.sh`
  (stdeb + debhelper toolchain), and attaches the artifact to the matching
  GitHub Release. PyPI publishing happens separately in `publish.yml` via
  OIDC trusted-publisher.
- `Dockerfile` stays in-repo for ad-hoc `docker build .` use, but no longer
  ships as a release artifact.

### Tooling
- `black` added to `.pre-commit-config.yaml`, running before `ruff` on
  every commit. Config lives in `pyproject.toml [tool.black]`
  (`line-length=180`, `target-version=["py38"]`). Existing tree is already
  black-compatible — no formatting churn.

### Changed — scope cleanup
wtftools is now strictly a **one-shot CLI**. The daemon / fleet / multi-host
story was removed in favor of the original PROJECT.md Phase 1 vision:
one server, one command, immediate answer. Removed:

- `wtfd` daemon (HTTP server, periodic audit loop, `POST /run-now`)
- `wtf serve` subcommand and `wtfd` console-script entry point
- `wtf fleet` (multi-host aggregation) and `wtf compare HOSTA HOSTB`
- `wtf plugins` listing subcommand (plugins still load — see
  `wtf audit --list-checks` for the `plugin:*` entries)
- `wtf motd-install` (replace with three lines of shell, see QUICKSTART)
- `wtf init` interactive wizard (its useful step — writing the example
  config — is `wtf config --example | sudo tee /etc/wtftools/config.ini`)
- `--watch` flags on `wtf audit`, `wtf info`, `wtf events`
- `wtf audit --diff` (the standalone `wtf diff` command remains)
- Bundled `scripts/wtfd.service` systemd unit
- `wtftools/daemon.py` and `wtftools/fleet.py` modules

Kept: `wtf audit --save`, `wtf diff`, `wtf history` — snapshots are pure
filesystem operations under `~/.cache/wtftools/`, no daemon required.

### Added
- **`wtf problems`** — alias for `wtf audit --only problem`, surfaces just
  the WARN+FAIL rows. Most common audit invocation during an incident,
  given its own subcommand for typing comfort.

## [0.0.0] — 2026-05-20

Initial public release. Highlights:

- **19 subcommands** covering audit / info / services / logs / events /
  history / diff / crontab / doctor / plugins / config / motd-install /
  init / fleet / compare / explain / top / ports / serve.
- **`wtfd` daemon** with HTTP API (`/audit`, `/audit.json`, `/audit.prom`,
  `/history`, `/snapshot/N`, `POST /run-now`) — drives the fleet story.
- **38 built-in checks**, plugin system with bash + Python SDK, six output
  formats (text/json/csv/plain/html/prometheus).
- **Multi-host fleet aggregation** (`wtf fleet`) + host-to-host drift
  detection (`wtf compare`), both with `--watch` and `--run-now`.
- **LLM bridge** for `wtf explain --llm ollama|claude|openai|auto`.
- Distribution: PyPI, debian packaging, Docker image, systemd unit,
  bundled MOTD installer, bash completion, GitHub Actions
  release workflow.
- **724 tests, 92.6 % coverage.**

### Added — Plugin SDK & docs (final iteration)
- **`wtftools.plugin_sdk`** — tiny helper module so Python plugins don't have
  to remember exit codes or hand-roll JSON:

  ```python
  #!/usr/bin/env python3
  from wtftools.plugin_sdk import ok, warn, fail, skip
  # ... your check ...
  fail("internal-api unreachable", detail=["…"])  # exits 2 with JSON
  ```

  Exposes `ok / warn / fail / skip` (terminating) and `result(status, message,
  detail=None)` (non-terminating, for scripts that emit multiple results).
  Detail items are coerced to strings.
- **`examples/plugins/check-http-health.py`** — example Python plugin using
  the SDK; probes an HTTP endpoint with latency thresholds.
- **`docs/PLUGIN_GUIDE.md`** — comprehensive plugin author's guide. Documents
  both exit-code and JSON contracts, shows bash + Python quickstarts, lists
  best practices, and points at the 5 example plugins.

- **`wtf fleet --watch SECONDS`** — auto-refresh fleet aggregation
  (mirrors the existing `audit --watch` and `info --watch`). Default
  off; pick an interval that respects N-hosts × per-fetch cost.
- **`wtf fleet --run-now`** — POST `/run-now` to every peer before
  fetching, so the aggregator gets fresh data instead of cached snapshots.
  Best-effort: partial failures print a `run-now reached M/N peer(s)`
  status line and the fetch proceeds anyway.
- **`wtf events --watch SECONDS`** — auto-refresh the event timeline.
  Useful in an incident war room.
- **`docs/QUICKSTART.md`** — 5-minute onboarding guide (README grew past 250
  lines — newcomers needed something smaller). Covers install, the
  incident-triage flow, fleet/Prometheus setup, custom checks, and a
  cheat-sheet table mapping common questions to commands.

- **`wtf events`** — chronological host timeline. Merges six event sources
  into one newest-first view: reboots (via `last -x reboot`), OOM kills,
  kernel errors, failed-unit transitions, SSH auth failures, recent logins.
  Flags: `--since HOURS` (default 24), `--kind KIND` (repeatable filter),
  `--limit N`, `--format json`. Useful during incident post-mortems: one
  command replaces `last`, `journalctl -k`, `journalctl SYSTEMD_UNIT=…`, and
  several SSH-log greps.
- **`POST /run-now`** in wtfd — trigger an immediate audit from outside the
  scheduler interval. Used by central dashboards that want fresh data on
  demand. Returns `202 Accepted` instantly; the actual run completes in the
  background and appears on the next `/audit.json` fetch. Auth-token-respecting.
  The scheduler now wakes within ~1s of receiving a `/run-now`.

- **`wtf compare HOSTA HOSTB`** — side-by-side diff of two wtfd hosts.
  Real-world SRE use case: «two boxes from the same template, why does
  one behave differently?» Fetches `/audit.json` from both, walks the
  merged set of check names, marks each row as `=` (identical), `DIFF`
  (status or message differs), `A→` (only on A), `→B` (only on B).
  `--only-drift` hides identical rows. `--format json` for pipelines.
  `--token-file` if peers require Bearer auth. Exit code: 0 identical,
  1 drift present, 2 if at least one host is unreachable.
- **`wtf doctor --check-updates`** — opt-in PyPI version check. Queries
  `https://pypi.org/pypi/wtftools/json` (3s timeout) and surfaces a
  `[WARN]` row if a newer release is published. Off by default — `doctor`
  stays an offline operation unless the operator explicitly opts in.

- **`wtf init`** — interactive setup wizard for fresh hosts. Walks through
  four optional steps:
  1. write `/etc/wtftools/config.ini` (sample with defaults)
  2. install `/etc/update-motd.d/99-wtf-brief` for the ssh-login banner
  3. install + enable the bundled `wtfd.service` (off by default)
  4. add `/etc/cron.d/wtftools-hourly` for an hourly audit snapshot

  Use `--non-interactive` for scripted deploys; `--dry-run` to preview;
  per-step `--enable-X` / `--no-X` flags override defaults.
- **`examples/plugins/`** — four ready-to-use plugin scripts:
  - `check-cert-domain.sh` — remote TLS cert expiry probe
  - `check-postgres-connections.sh` — Postgres `pg_stat_activity` vs `max_connections`
  - `check-redis-memory.sh` — Redis `used_memory` vs `maxmemory`
  - `check-disk-write.sh` — quick fsync-write latency test

  Drop any of these into `/etc/wtf/checks.d/` and `wtf audit` picks them up.
- **`docs/schema/`** — JSON Schema (draft-07) for `--format json` outputs:
  `audit-v1.json` and `fleet-v1.json`. Use with `check-jsonschema` or any
  validator to build typed parsers in your integration.
- **`CONTRIBUTING.md`** — dev setup, test/lint commands, how to add a new
  check or subcommand, release flow.
- **GitHub Actions release workflow** (`.github/workflows/release.yml`) —
  on `v*` tag: runs the suite, builds sdist+wheel, publishes to PyPI
  (via `PYPI_API_TOKEN` secret), builds + pushes a Docker image to GHCR.

- **`wtf fleet`** — multi-host aggregation. Pulls `/audit.json` from each
  configured wtfd peer in parallel (`urllib` + ThreadPoolExecutor, no extra
  deps). Renders an at-a-glance fleet view sorted by severity:
  unreachable → fail → warn → ok. Per-host row inlines the top two problems
  so an SRE doesn't need to drill in to know what's broken.
  - Targets from `--hosts a:8765,b:8765` (repeatable), `--hosts-file FILE`
    (one per line, `#` comments), or `[thresholds] fleet_hosts = …` in the
    config file. All sources merge and dedupe.
  - `--token-file FILE` sends `Authorization: Bearer …` to every peer.
  - `--problem-only` hides healthy hosts during incidents.
  - `--format prometheus` emits one set of metrics per host
    (`wtf_fleet_host_up{host="…"}`, `wtf_fleet_summary_count{host,status}`)
    suitable for a single scrape job targeting the aggregator.
  - Exit codes: 0 if all hosts OK; 1 if some unreachable but no FAIL;
    2 if any FAIL or everything is unreachable. CI-friendly.
- **Dockerfile** — `python:3.12-slim` base with `[full]` extras (psutil)
  plus tools wtftools probes (procps, iproute2, smartmontools, openssl,
  systemd-sysv, cron). `HEALTHCHECK` against `/healthz`, default entrypoint
  is `wtf`. `.dockerignore` keeps the image lean.

- **LLM bridge for `wtf explain`** — closes the loop: instead of piping the
  structured prompt to an LLM by hand, point at a backend directly.
  - `wtf explain --llm ollama` — subprocess call to local ollama (no API key).
  - `wtf explain --llm claude` — uses `anthropic` SDK if installed +
    `ANTHROPIC_API_KEY` env. Default model: `claude-haiku-4-5-20251001`.
  - `wtf explain --llm openai` — uses `openai` SDK + `OPENAI_API_KEY`.
  - `wtf explain --llm auto` — tries ollama → claude → openai, returns the
    first one that responds.
  - `--llm-model` overrides the default model; `--llm-timeout` overrides 60s.
  - No mandatory new dependencies — the SDKs are imported lazily, missing
    backends become a graceful skip with an explanatory message.
- **`wtf audit --format html`** — self-contained HTML with inline CSS.
  Color-coded rows, collapsible detail. Survives email/ticket paste.
- **`wtf audit --output FILE` / `-o FILE`** — write the audit to a file
  instead of stdout. Drops ANSI escapes automatically so logs stay clean.
- **`fail2ban` check** — surfaces currently-banned IP counts per jail
  (informational, not a problem signal). Skip when fail2ban-client missing
  or the daemon is down.

- **`wtfd` daemon** — PROJECT.md Phase 2 landed. Stdlib-only single-process
  daemon (`pip install wtftools` ships an extra `wtfd` console script).
  Runs `audit` on a configurable cadence and serves the result over HTTP:
  - `GET /` — brief one-liner (host, fail/warn counts, top problems)
  - `GET /healthz` — liveness probe
  - `GET /audit` / `/audit.txt` — current audit in plaintext
  - `GET /audit.json` — full audit + summary + timestamp + error state
  - `GET /audit.prom` — Prometheus textfile-collector
  - `GET /history` — snapshot dir + list of recent basenames
  - `GET /snapshot/N` — Nth-most-recent snapshot (by index or basename prefix)

  Flags: `--listen HOST:PORT` (default `127.0.0.1:8765`), `--interval SEC`
  (default 300 = 5 min), `--save` to persist each run as a snapshot,
  `--auth-token-file PATH` for `Authorization: Bearer …` protection.
  Every response carries `X-WTF-Host`, `X-WTF-Last-Audit`, `X-WTF-Version`
  headers for trivial observability. Run via `wtf serve …` or the bare
  `wtfd` console script.

- **systemd unit** in `scripts/wtfd.service` — `DynamicUser=yes`,
  `StateDirectory=wtftools`, hardened (`ProtectSystem=strict`,
  `NoNewPrivileges`, `ProtectKernel*`). Drop into `/etc/systemd/system/`,
  `systemctl enable --now wtfd`.

- **`http-probes` and `tcp-probes` checks** — declare endpoints in
  `[thresholds]` (`http_probes = http://localhost:80, http://localhost:9090`
  and `tcp_probes = 127.0.0.1:5432, db.internal:6379`). Each becomes its own
  audit row. HTTP non-2xx/3xx → FAIL; connect refused/timeout → FAIL; latency
  ≥ `probe_slow_ms` → WARN. Uses stdlib `http.client` + `socket` — no extra
  dependencies. Catches the "service is running but not actually serving"
  failure mode that `failed-units` misses.
- **`smart` check** — per-disk SMART health via `smartctl -H -j` (requires
  `smartmontools` package, typically also root). One FAILED disk → FAIL with
  device name in detail. Discovers disks via `lsblk`, filters out loop devices
  and partitions.
- **`wtf diff`** — standalone snapshot diff command. `wtf diff` compares the
  latest snapshot to a fresh audit (same as `wtf audit --diff`).
  `wtf diff --snapshot N` reaches back N snapshots. `wtf diff --against A B`
  diffs two snapshot files directly without running a live audit (useful for
  comparing snapshots shipped from other hosts).
- **`wtf audit --format plain`** — tab-separated `status<TAB>name<TAB>message`
  rows. No headers, no summary, no colors. Designed for shell pipelines:
  `wtf audit --format plain | awk '$1=="fail"'`.

- **`wtf top`** — focused process top with sort and filters.
  `--sort cpu|rss`, `--user PREFIX`, `--name SUBSTRING`, `--limit N`.
  Cuts through the noise of `wtf info`'s 5-row top section when you need
  the bigger picture.
- **`wtf ports`** — listening sockets with owning PID, user, command.
  Replaces `ss -tlnp` for the common "who's on :443?" question.
  `--proto tcp|udp|all`, `--public-only` (drops 127.x).
- **`wtf motd-install`** — installs `/etc/update-motd.d/99-wtf-brief` so
  every SSH login shows a one-line wtftools summary. `--path` to override
  destination, requires root.
- **`hw-temp` check** — reads `/sys/class/hwmon/*/temp*_input`. ≥75°C WARN,
  ≥90°C FAIL (configurable). Reports max + count, lists all sensors in
  `-v` detail. Filters absurd readings (<-50°C or >200°C broken sensors).
- **`dns` check** — probes well-known hosts via the system resolver.
  Configurable list (`dns_probe_hosts`, default `google.com,cloudflare.com`)
  + 2s per-probe timeout. All resolve → OK. Some fail → WARN. None
  resolve → FAIL (broken DNS / resolved.service down). Catches silently-
  broken `systemd-resolved`.
- **`wtf audit --format csv`** — CSV output with name,status,message,detail
  columns. For spreadsheet flows / lightweight reporting.

- **Snapshots, history, and diff** — `wtfd-lite` finally exists.
  - `wtf audit --save` persists the current run to `~/.cache/wtftools/snapshots/`
    (or `/var/lib/wtftools/snapshots/` when running as root, or
    `$WTFTOOLS_SNAPSHOT_DIR` if set). Auto-rotates to keep the newest 48.
  - `wtf audit --diff` compares the current audit to the most recent snapshot,
    flagging regressions / recoveries / new / removed checks. Sorted with
    regressions first.
  - `wtf history` lists stored snapshots with status counts.
  - Snapshot file format is plain JSON — easy to ship to a central host.
- **`docker` check** — surfaces containers in `unhealthy` or `Restarting` state.
  `unhealthy` → FAIL, `restarting`-only → WARN. Skips cleanly when docker is
  not installed or the daemon is unreachable.
- **NTP drift magnitude** in the `time-sync` check — when `chronyc tracking`
  is available, the reported offset (ms) augments the binary sync/no-sync
  signal. Drift ≥100ms → WARN, ≥1s → FAIL.
- **`wtf audit --format prometheus`** — Prometheus textfile-collector output.
  Two metrics: `wtf_check_status{name="..."}` (0/1/2/3 for ok/warn/fail/skip)
  and `wtf_summary_total{status="..."}`. Drop into node_exporter's
  `--collector.textfile.directory` for scraping.
- **`wtf info --watch SECONDS`** — live-refresh the host snapshot (mirror of
  the existing `wtf audit --watch`).

### Added (earlier in this Unreleased cycle)
- **`wtf explain`** — turns audit findings into actionable per-check advice.
  A rule-based table maps each `(name, status)` to a 1-2 sentence diagnosis
  and concrete next steps (which command to run, which file to vacuum, etc.).
  Covers every built-in check; unknown checks get a fallback hint.
- **`wtf explain --prompt`** — emit an LLM-ready prompt summarizing the audit.
  Pipe to `claude`, `ollama run llama3`, or any other LLM for a synthesized
  diagnosis without bundling an LLM dependency. The PROJECT.md headline finally
  has a delivery vehicle.
- **`wtf audit --alert <cmd>`** — fire a shell command when audit produces
  FAIL (or WARN, with `--alert-on warn`). Audit summary is piped to the
  command's stdin; env vars `WTF_FAIL_COUNT`, `WTF_WARN_COUNT`, `WTF_HOST`
  are set. Cron-driven monitoring without a notification client:
  `wtf audit --alert 'mail -s "wtf $WTF_HOST" sre@example.com'`.
- **`conntrack` check** — reads `/proc/sys/net/netfilter/nf_conntrack_count`
  vs `nf_conntrack_max`. NAT/firewall/proxy hosts silently drop new
  connections when the table fills; ≥70% WARN, ≥90% FAIL (configurable).
- **`journal-disk` check** — parses `journalctl --disk-usage`. ≥4GB WARN,
  ≥16GB FAIL (configurable). Includes a vacuum-size hint in the message.
- pyproject installs the bash-completion file system-wide.

### Added (earlier in this Unreleased cycle)
- **Parallel check execution** — checks now run on a `ThreadPoolExecutor`
  (default 8 workers, configurable via `config.ini` `parallel_workers` or env).
  Typical full audit dropped from ~2.3s to ~1.2s on a 24-core dev machine; one
  hung check no longer blocks the rest. Use `wtf audit --serial` to force the
  old sequential path for debugging.
- **Per-check timeout** — every check gets a default 10s budget. A check that
  exceeds it surfaces a `[SKIP]` result with a clear "timeout" message instead
  of hanging the whole audit. Tune via `config.ini` `check_timeout` or
  `wtf audit --check-timeout SECONDS`.
- **`psi` check** — reads `/proc/pressure/{cpu,memory,io}` (Linux ≥4.20). The
  modern kernel signal for real resource contention. Thresholds on PSI `some
  avg10`: ≥10% WARN, ≥30% FAIL (configurable). Three result rows: one per
  resource. Auto-skipped when `psi=0` boot cmdline is set.
- **`kernel-taint` check** — reads `/proc/sys/kernel/tainted`. Non-zero means
  the kernel saw a proprietary/forced/unsigned module, a machine check, a
  soft-lockup, etc. Decodes the bitmask into readable flag names; severe bits
  (`MACHINE_CHECK`, `SOFTLOCKUP`, `DIE`, `BAD_PAGE`) escalate to FAIL.
- **`cert-expiry` check** — walks server-cert dirs (`/etc/letsencrypt/live`,
  `/etc/nginx/ssl`, `/etc/haproxy/certs`, …), parses `notAfter` via openssl.
  ≥30d OK, <30d WARN, <7d FAIL. Bounded to 50 files. Avoids the system CA
  store (`/etc/ssl/certs`) which legitimately ships long-expired root CAs.
- **`wtf logs`** — recent ERROR+ journal entries grouped by service. Flags:
  `--since '1 hour ago'`, `--priority err`, `--units N`, `--lines N`,
  `--format json`. Natural complement to `wtf services <name>`.

- **`wtf services <name>`** — focused drilldown for one systemd unit: shows
  ActiveState, SubState, Result, UnitFileState, MainPID, NRestarts,
  MemoryCurrent, listening ports owned by the main pid, plus the last N journal
  lines. Replaces the SSH dance of `systemctl status … && journalctl -u … && ss -tlnp`.
- **Config file** — INI at `/etc/wtftools/config.ini`, `/etc/wtf/config.ini`,
  or `~/.config/wtftools/config.ini`. Customizable thresholds for disk, memory,
  swap, load, iowait, fds, pids, tcp-retrans, auth, service restarts, plus
  `[ignore]` lists. Global `--config PATH` stacks a further file on top.
- **`wtf config`** — print effective values + search paths. `wtf config --example`
  prints a fully-commented template ready for `> /etc/wtftools/config.ini`.
- **`wtf audit --ignore NAME`** — skip a check by short-name OR by result-name
  (e.g. `--ignore "disk /mnt/Backup"` to hush a single noisy mount). Repeatable.
- **`tcp-retrans`** check — samples `/proc/net/snmp` TCP RetransSegs/OutSegs
  over a 1-second window; ≥1% WARN, ≥5% FAIL (configurable).

### Changed
- All audit thresholds now read from the active config (no more hardcoded
  85/95/30/70). Defaults match prior behavior exactly.
- `run_audit()` accepts `ignore=` and merges it with the config's
  `[ignore]` lists.

- **Plugin system**: drop executable scripts into `/etc/wtf/checks.d/`,
  `/etc/wtftools/checks.d/`, or `~/.config/wtftools/checks.d/`. Exit codes
  `0=ok / 1=warn / 2=fail / 77=skip`; stdout becomes the message. A plugin
  may also emit a one-line JSON object `{"status":..., "message":...,
  "detail":[...]}` for full control. Plugins show up in `wtf audit` and
  `wtf audit --list-checks` under the `plugin:<name>` namespace.
- `wtf plugins` — list discovery dirs and registered plugins.
- `restart-loops` audit check — flags active services where systemd has had
  to bring them back ≥3 times (`NRestarts`). ≥10 → FAIL (the "flaky daemon"
  case where the service technically "runs" but isn't healthy).
- `network-errors` audit check — reads `/sys/class/net/*/statistics/` and
  surfaces interfaces with non-zero rx/tx errors or drops (≥1000 → WARN).
- `wtf audit --brief` / `-b` — one-line summary suitable for MOTD / SSH
  banners: `wtf: 1 fail, 3 warn — swap: 99% · …`. Exit code mirrors severity.
- Example plugin in `scripts/example-plugin-check-tmp.sh` (warns when /tmp
  usage crosses 80% / 95%).
- `wtf doctor` — self-diagnostic that probes which CLI tools (`systemctl`,
  `journalctl`, `apt`, `timedatectl`, …) and `/proc` files are available.
  Explains why checks may be skipped on this host.
- `wtf audit --check NAME` — run a single named check (repeatable). For CI
  and scripted use (e.g. `wtf audit --check disks --check memory --format json`).
- `wtf audit --list-checks` — print the short names of every registered check.
- `wtf audit --only fail|warn|problem|skip|ok|all` — filter output by status.
  Useful on terminal: `wtf audit --only problem` shows just what's broken.
- `wtf audit --since HOURS` — configurable look-back window for OOM, kernel
  errors and failed-auth checks (was hardcoded to 24h).
- `wtf audit --watch SECONDS` — live mode that re-runs the audit and re-prints
  every N seconds (Ctrl-C to exit).
- Bash completion in `scripts/wtf.bash-completion`.
- GitHub Actions CI workflow running tests + coverage on Python 3.10–3.12.

### Changed
- Audit registry now keys checks by stable short names so `--check` / `--list-checks`
  expose a documented, scriptable surface.
