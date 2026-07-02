# wtf — health checks & monitoring

The audit and monitoring side of wtftools: the green/yellow/red health checklist, the commands that drill into problems, and the snapshot/diff/timeline tooling for a daily routine or unattended cron alerting.

Part of [wtftools](../README.md).

## `wtf audit`

The full green/yellow/red checklist of what is OK and what is not. Running `wtf` with no subcommand runs `audit` by default. Green is fine, yellow needs a look, red needs fixing.

```
$ wtf audit
# AUDIT
[ OK ] uptime                  3d 4h 12m
[ OK ] load average            0.42 0.51 0.55 / 8 CPU
[ OK ] memory                  4.1GB / 16.0GB used (25%)
[WARN] disk /var               17.0GB / 20.0GB used (85%)
[ OK ] zombie processes        0 zombies
[FAIL] failed systemd units    1 failed unit(s)
[ OK ] crontab syntax          14 cron line(s), no errors

  Summary: 12 ok · 1 warn · 1 fail · 2 skip
```

- `-v`, `--verbose` — show extra detail (failed units, OOM events).
- `--strict` — exit non-zero on warnings too.
- `--exit-zero` — always exit with code 0.
- `--check NAME` — run only the named check (repeatable); see `--list-checks`.
- `--only {fail,warn,problems,problem,skip,ok,all}` — show only results with the given status.
- `--since HOURS` — look-back window in hours for OOM/auth/kernel checks (default: 24).
- `--ignore NAME` — skip a check short-name or result-name (repeatable), e.g. `--ignore swap` or `--ignore 'disk /mnt/Backup'`.
- `--list-checks` — list all check short-names and exit.
- `--brief`, `-b` — one-line summary suitable for MOTD / SSH banners.
- `--serial` — run checks sequentially (for debugging; default is parallel).
- `--check-timeout SECONDS` — per-check timeout in seconds (default: 10, overrides config).
- `--alert CMD` — shell command to invoke when FAIL results exist; audit text is piped to stdin. Env: `WTF_FAIL_COUNT`, `WTF_WARN_COUNT`, `WTF_HOST`.
- `--alert-on {fail,warn,any}` — when to fire `--alert` (default: only on FAIL).
- `--save` — persist the audit result as a snapshot for history/diff.
- `--output FILE`, `-o FILE` — write the audit to FILE instead of stdout (drops ANSI colors).
- `--format {text,json,csv,html,prometheus,plain}` — output format. `csv` is spreadsheet-friendly, `html` is a self-contained report for tickets, `prometheus` produces metrics for a node_exporter textfile, `plain` is tab-separated with no headers.

## `wtf problems`

Shows ONLY what is wrong — the WARN and FAIL rows from the audit, nothing else. Use it to skip straight to what needs attention.

```
$ wtf problems -v
# PROBLEMS
[WARN] disk /var               17.0GB / 20.0GB used (85%)
[FAIL] failed systemd units    1 failed unit(s)
```

- `--check NAME` — run only the named check (repeatable); see `wtf audit --list-checks`.
- `--ignore NAME` — skip a check short-name or result-name.
- `--since HOURS` — look-back window for OOM/auth/kernel checks.
- `--strict` — exit non-zero on warnings too.
- `--exit-zero` — always exit with code 0.
- `--serial` — run checks sequentially.
- `--check-timeout SECONDS` — per-check timeout in seconds.
- `--verbose`, `-v` — show extra detail.
- `--output FILE`, `-o FILE` — write to FILE instead of stdout.
- `--format {text,json,prometheus,csv,plain,html}` — output format.

## `wtf daily`

The morning check in one command: the audit, what changed since the last run, and the recent event timeline, with a one-line verdict on top. It saves a snapshot on every run, so tomorrow's `wtf daily` shows the diff.

```
$ wtf daily
# DAILY
VERDICT: 1 warning, 1 failure since yesterday
... audit, diff vs last run, and events ...
```

A crontab line for unattended use (mails only when something is wrong):

```cron
0 8 * * * wtf daily --format json > /var/log/wtf-daily.json 2>&1 || mail -s "wtf $(hostname)" you@example.com < /var/log/wtf-daily.json
```

- `--since HOURS` — look-back window in hours (default: 24).
- `--ignore NAME` — skip a check short-name or result-name (repeatable).
- `--strict` — exit non-zero on warnings too.
- `--exit-zero` — always exit with code 0.
- `--format {text,json}` — output format.

## `wtf explain`

Per-check actionable advice: for each finding it tells you what to do about it, step by step. With `--llm` it can hand the structured findings to a local or hosted LLM for a summary.

```
$ wtf explain --llm ollama
# EXPLAIN
[FAIL] failed systemd units
  → systemctl --failed
  → journalctl -u <unit> -b --no-pager
```

- `--check NAME` — limit to specific checks.
- `--ignore NAME` — skip a check or result-name.
- `--since HOURS` — look-back window for time-bounded checks (default: 24).
- `--all` — also explain OK results (default: only WARN/FAIL).
- `--deep` — run dynamic investigation per finding (`du -d1` on the filling mount, `docker system df`, container/log sizes). Slower; opt-in.
- `--prompt` — print an LLM-ready prompt instead of built-in advice. Pipe it: `wtf explain --prompt | claude` or `| ollama run llama3`.
- `--llm {ollama,claude,openai,auto}` — call an LLM directly with the structured prompt and print its response. `ollama` needs the binary; `claude`/`openai` need the matching Python SDK plus API-key env. `auto` uses your **local** `ollama` only — it never falls back to a remote model, so pick `claude`/`openai` explicitly to use one.
- `--llm-model MODEL` — override the default model name for `--llm`.
- `--llm-timeout SECONDS` — LLM call timeout (default: 60s).
- `--yes` / `-y` — skip the confirmation prompt shown before a **remote** backend (`claude`/`openai`) receives this host's name and audit findings. `WTFTOOLS_LLM_YES=1` does the same. The disclosure note is always printed; on a non-interactive stdin the call proceeds without prompting.
- `--serial` — run audit sequentially (passes through to the underlying audit).
- `--check-timeout SECONDS` — per-check timeout in seconds (passes through to audit).
- `--format {text,json}` — output format.

## `wtf events`

A chronological timeline of notable events: reboots, OOM kills, failed units, kernel errors, failed auth, and logins.

```
$ wtf events --since 6
# EVENTS
2026-06-15 07:14  reboot       system booted
2026-06-15 08:02  failed-unit  nginx.service entered failed state
2026-06-15 08:05  auth-fail    failed password for invalid user from 198.51.100.7
```

- `--since HOURS` — look-back window in hours (default: 24).
- `--kind KIND` — filter to one kind (repeatable). Choices: `reboot`, `oom`, `failed-unit`, `kernel-err`, `auth-fail`, `login`.
- `--limit LIMIT` — max events to show (0 = unlimited).
- `--format {text,plain,json}` — output format.

## `wtf logs`

Recent ERROR-and-above journal entries, grouped by the service that produced them.

```
$ wtf logs --since '2 hours ago'
# LOGS
nginx.service (3)
  could not open error log file
  ...
```

- `--since SINCE` — `journalctl --since` value (default: `'1 hour ago'`).
- `--priority PRIORITY`, `-p PRIORITY` — journalctl priority filter (default: `'err'` = err+crit+alert+emerg).
- `--units UNITS` — number of top units to show (default: 10).
- `--lines LINES`, `-n LINES` — lines per unit (default: 5).
- `--format {text,plain,json}` — output format.

## `wtf services`

Drill into one service: state, restart count, memory, ports, and recent journal lines. `wtf service` is an alias for the same command.

```
$ wtf services nginx
# SERVICE nginx
  state     : active (running)
  restarts  : 0
  memory    : 24.1MB
  ports     : tcp *:80, tcp *:443
  ... recent journal lines ...
```

- `name` (positional) — service unit name, e.g. `nginx` or `nginx.service`.
- `-n LINES`, `--lines LINES` — recent journal lines to show (default: 20).
- `--format {text,plain,json}` — output format.

## `wtf diff`

Compares the current state to a saved snapshot and shows what changed. Snapshots come from `wtf audit --save` (and from `wtf daily`, which saves on every run).

```
$ wtf diff
# DIFF vs snapshot 0
+ [FAIL] failed systemd units    1 failed unit(s)
~ [WARN] disk /var               80% → 85%
```

- `--snapshot N` — compare against the Nth-most-recent snapshot (0=latest, 1=one before, …). Default: 0.
- `--against OLD NEW` — diff two snapshot files directly, no live audit.
- `--format {text,json}` — output format.

## `wtf history`

Lists the saved audit snapshots, most recent first. Create snapshots with `wtf audit --save`.

```
$ wtf history
# HISTORY
0  2026-06-15 08:00  12 ok · 1 warn · 1 fail
1  2026-06-14 08:00  13 ok · 1 warn · 0 fail
```

- `--limit LIMIT` — number of most-recent snapshots to show (default: 20).
- `--format {text,json}` — output format.

## `wtf crontab`

Validates crontab syntax across all standard crontab locations and per-user crontabs. Specific files, directories, or usernames can be passed as targets.

```
$ wtf crontab
# CRONTAB
[ OK ] /etc/crontab            6 line(s), no errors
[FAIL] /var/spool/cron/root    line 3: bad minute field
```

- `targets` (positional) — files, directories, or usernames.
- `-S FILE`, `--system FILE` — system crontab file.
- `-U FILE`, `--user-file FILE` — user crontab file.
- `-u USER`, `--username USER` — username.
- `--strict` — exit non-zero on warnings too.
- `--exit-zero` — always exit with code 0.
- `--format {text,json}` — output format.

## `wtf doctor`

A self-diagnostic: which underlying tools wtftools can actually use on this host (`systemctl`, `journalctl`, `psutil`, `lsof`, …) and what is missing or degraded.

```
$ wtf doctor
# DOCTOR
[ OK ] systemctl              available
[ OK ] journalctl             available
[WARN] psutil                 not installed (richer process info disabled)
```

- `--check-updates` — query PyPI for a newer wtftools version (network call).
- `--format {text,json}` — output format.

## Exit codes

Exit codes are CI/cron-friendly:

| code | meaning                                          |
|------|--------------------------------------------------|
| 0    | everything OK                                    |
| 1    | warnings with `--strict`, or crontab errors      |
| 2    | audit found a `[FAIL]`                            |
| 130  | interrupted (Ctrl-C)                             |

## Built-in checks

uptime · system state · load average · CPU iowait · PSI cpu/memory/io ·
TCP retransmits · memory · swap · disk (per mount) · inodes ·
read-only mounts · failed systemd units · enabled-but-down services ·
restart loops · network errors · conntrack · journal disk usage · zombies ·
D-state processes · OOM kills · kernel errors · kernel taint · cert expiry ·
open file descriptors · process count · failed auth · time sync ·
pending updates · reboot required · cron daemon · crontab syntax · docker ·
hw temperatures · disk SMART · DNS · HTTP/TCP probes · fail2ban.
