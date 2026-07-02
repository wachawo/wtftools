# Roadmap

wtftools is a **read-only, stdlib-first, single-command** diagnostic CLI. This
roadmap keeps that identity. Every item must:

- stay **read-only** — never change host state;
- **degrade gracefully** when a tool or file is missing (return a skip, never crash);
- avoid heavy dependencies — Python standard library first, `psutil` optional;
- earn its place in the "diagnose in one command" story.

Anything that needs a daemon, a time-series database, or multi-host coordination
is a monitoring stack, not wtftools — see **Out of scope** below.

Labels: **[planned]** likely next · **[considering]** wanted, not committed. No
dates; items land when they're ready. Ideas welcome — see `CONTRIBUTING.md`.

---

## Incident triage — reach for it when something is on fire

### Deleted-but-open files eating disk — [planned]
**Pain:** `df` reports 100 % full, `du` finds nothing — a process is holding a
deleted 40 GB log open. The single most common "disk full" head-scratcher.
**Approach:** scan `/proc/*/fd` for links whose target ends in `(deleted)`, sum
by process. Pure `/proc`, no `lsof` dependency.
**Lands in:** `wtf disk` (a flagged section when reclaimable space is found).

### `wtf proc <PID>` — process drilldown — [planned]
**Pain:** the audit flags a CPU hog or a `D`-state process; there's nowhere to
drill in. Mirror of the existing `wtf port <N>`.
**Approach:** read `/proc/<pid>/` — cmdline, cwd, exe, open fds/sockets, limits,
`oom_score`, cgroup, parent tree, RSS/swap, state. All stdlib.
**Lands in:** new `wtf proc <PID>` subcommand (text/plain/json).

### Cross-signal correlation in `wtf explain` — [considering]
**Pain:** five separate WARN rows are often one incident. "Load is high →
because process X is in `D` state → because `/dev/sdb` is at 100 % util." Today
`explain` advises per finding but never links them.
**Approach:** a small rules layer that groups findings by shared cause
(same device, same PID, same unit) and prints the chain.
**Lands in:** `wtf explain` (a "likely one incident" grouping).

### Live sampling / rate window — [considering]
**Pain:** `wtf` is a single frame. "Load 20" says nothing about whether it is
climbing or clearing. One command should show movement.
**Approach:** an opt-in short sampling window (e.g. `--sample 5s`) that reports
CPU/IO/net **rates and deltas**, not one instantaneous read.
**Lands in:** `wtf cpu` / `wtf io` / `wtf net` / `wtf top` (`--sample`).

### Connection-state & exposure summary — [planned]
**Pain:** during a network incident you want socket-state counts
(ESTABLISHED / TIME_WAIT / SYN_RECV storms) and, for security, a loud flag on
sockets listening on `0.0.0.0` (reachable from the world) vs `127.0.0.1`.
**Approach:** parse `/proc/net/tcp{,6}` and `udp{,6}`; classify bind address.
**Lands in:** `wtf net` (state summary + an "exposed" marker on `wtf ports`).

---

## Health & prevention — the morning check

### Stale-library processes (needrestart-style) — [planned]
**Pain:** after `apt upgrade openssl`, nginx keeps running the old libssl mapped
in memory. A silent stability and security gap.
**Approach:** scan `/proc/*/maps` for mapped `.so` files whose path ends in
`(deleted)`; report the processes that need a restart. Pure `/proc`.
**Lands in:** a new audit check (`stale-libs`) + surfaced in `wtf problems`.

### RAID / md & hardware errors — [planned]
**Pain:** SMART is checked, but a degraded software-RAID array is not — a silent
killer on bare metal. Kernel hardware errors (MCE, thermal throttling events)
are likewise invisible.
**Approach:** read `/proc/mdstat` for array state; scan the kernel ring buffer
for hardware-error / throttle lines.
**Lands in:** audit checks (`raid`, `hw-errors`).

### systemd timers — [planned]
**Pain:** wtftools validates crontab but ignores `.timer` units — the modern
replacement for cron. A timer that stopped firing is a blind spot.
**Approach:** `systemctl list-timers --all` — flag timers that are dead, failed,
or overdue relative to their schedule.
**Lands in:** a `timers` audit check (and detail in `wtf crontab`/`services`).

### Container health & restarts — [considering]
**Pain:** `wtf docker` reports compose dir and sizes, but not `unhealthy`
containers or crash-loops (high restart counts) — usually the first question in
a "site is down" incident.
**Approach:** `docker inspect` health status + restart count; degrade when the
daemon is absent.
**Lands in:** `wtf docker` and a `containers` audit check.

### Capacity ETA (disk-full projection) — [considering]
**Pain:** "the disk is 85 % full" is less useful than "`/var` fills in ~2.5 days
at the current rate."
**Approach:** reuse the existing snapshot history — fit a simple rate from the
last N snapshots and project time-to-full for disks and inodes.
**Lands in:** `wtf disk` / audit (an ETA note when a mount is trending full).

---

## Out of scope

These are deliberately **not** planned — they would turn a one-shot CLI into a
monitoring platform:

- **Multi-host fleet aggregation / drift comparison.** Run wtftools per host;
  aggregate with your existing tooling.
- **A live TUI dashboard.** wtftools prints an answer and exits; use `htop` /
  `glances` for a live view.
- **Metric storage / a time-series database.** `--format prometheus` exports to
  the stack you already run; wtftools does not store history beyond its light
  snapshot/diff feature.
- **Any write/remediation action.** wtftools only reads. It tells you what is
  wrong; fixing is yours.

---

## Guiding test for new ideas

Before proposing a feature, ask: *does it help answer "what's wrong with this box
right now?" in one read-only command, without new heavy dependencies?* If yes,
open an issue. If it needs an agent, a database, or write access — it belongs in
a different tool.
