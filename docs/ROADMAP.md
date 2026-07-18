# Roadmap

wtftools is a **read-only, stdlib-first, single-command** diagnostic CLI. This
roadmap keeps that identity. Every item must:

- stay **read-only** — never change host state;
- **degrade gracefully** when a tool or file is missing (return a skip, never crash);
- avoid heavy dependencies — Python standard library first, `psutil` optional;
- earn its place in the "diagnose in one command" story.

Anything that needs a daemon, a time-series database, or multi-host coordination
is a monitoring stack, not wtftools — see **Out of scope**.

`[x]` done · `[ ]` planned. Ideas welcome — see `CONTRIBUTING.md`.

---

## Incident triage — reach for it when something is on fire

- [x] **Deleted-but-open files eating disk** — the classic "`df` says 100 % full,
  `du` finds nothing": a process holds a deleted file open. Scans `/proc/*/fd`
  for `(deleted)` targets and sums reclaimable space. Surfaces in `wtf audit`
  (`deleted-files` check) with per-holder detail and `explain` advice.
- [ ] **`wtf proc <PID>` — process drilldown.** Mirror of `wtf port <N>`: cmdline,
  cwd, exe, open fds/sockets, limits, `oom_score`, cgroup, parent tree, RSS/swap.
  All from `/proc/<pid>/`. text/plain/json.
- [ ] **Cross-signal correlation in `wtf explain`.** Group findings that share a
  cause (same device / PID / unit) and print the chain — "load high → proc X in
  `D` → `/dev/sdb` at 100 % util" — instead of five separate rows.
- [ ] **Live sampling / rate window.** Opt-in `--sample 5s` for `cpu`/`io`/`net`/
  `top` that reports **rates and deltas**, so one command shows movement, not a
  single frame.
- [ ] **Connection-state & exposure summary.** Socket-state counts
  (ESTABLISHED / TIME_WAIT / SYN_RECV storms) from `/proc/net/tcp{,6}`, plus a
  loud flag on sockets bound to `0.0.0.0` (world-reachable) vs `127.0.0.1`.

## Health & prevention — the morning check

- [x] **nginx config security analysis (`wtf nginx`)** — a read-only, stdlib-only
  linter for nginx configs. Ships its own tolerant parser (includes, quoted
  regexes, `map`/`geo`, Lua blocks) and eight checks: alias traversal, host
  spoofing, `valid_referers none`, dropped security headers, multi-line headers,
  SSRF, HTTP splitting and weak origin regexes. Standalone (`wtf nginx [PATH]`)
  and as the `nginx-config` audit check.
- [x] **Stale-library processes (needrestart-style)** — after `apt upgrade
  openssl`, services keep the old libssl mapped in memory. Scans `/proc/*/maps`
  for deleted `.so` mappings. Surfaces in `wtf audit` (`stale-libs` check) with
  restart advice.
- [x] **RAID / md health** — a degraded software-RAID array is a silent killer on
  bare metal. Reads `/proc/mdstat`; `wtf audit` (`raid` check) reports degraded
  (fail) or rebuilding (warn) arrays.
- [ ] **Hardware errors from the kernel ring buffer.** MCE / PCIe AER / thermal
  throttling events that today go unseen (temperatures are read, throttle events
  are not).
- [ ] **systemd timers.** wtftools validates crontab but ignores `.timer` units —
  the modern cron. Flag timers that are dead, failed, or overdue
  (`systemctl list-timers`).
- [ ] **Container health & restarts.** `wtf docker` reports sizes but not
  `unhealthy` status or crash-loops (restart counts) — usually the first
  question in a "site is down" incident.
- [ ] **Capacity ETA (disk-full projection).** Reuse the snapshot history to fit
  a rate and project time-to-full for disks and inodes — "`/var` fills in
  ~2.5 days" beats "85 % full".

## Out of scope

Deliberately **not** planned — these turn a one-shot CLI into a monitoring
platform:

- Multi-host fleet aggregation / drift comparison — run wtftools per host,
  aggregate with your existing tooling.
- A live TUI dashboard — wtftools prints an answer and exits (`htop`/`glances`
  are the live view).
- Metric storage / a time-series database — `--format prometheus` exports to the
  stack you already run.
- Any write / remediation action — wtftools only reads.

---

## Guiding test for new ideas

Before proposing a feature, ask: *does it help answer "what's wrong with this box
right now?" in one read-only command, without new heavy dependencies?* If yes,
open an issue. If it needs an agent, a database, or write access — it belongs in
a different tool.
