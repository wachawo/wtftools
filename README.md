# wtftools

> One command to see what is going on with your Linux server right now.

**Status:** v0.0.0 — initial public release. 14 subcommands, 38 built-in
checks, bash + Python plugin SDK, snapshot/diff/history, LLM-driven explain.
One-shot CLI; no daemon, no fleet aggregator.

> **In a hurry?** See [docs/QUICKSTART.md](docs/QUICKSTART.md) for the 5-minute version.

```
$ wtf
─────────── AUDIT ────────────
[ OK ] uptime                  3d 4h 12m
[ OK ] load average            0.42 0.51 0.55 / 8 CPU
[ OK ] memory                  4.1GB / 16.0GB used (25%)
[WARN] disk /var               17.0GB / 20.0GB used (85%)
[ OK ] zombie processes        0 zombies
[FAIL] failed systemd units    1 failed unit(s)
[ OK ] crontab syntax          14 cron line(s), no errors

  Summary: 12 ok · 1 warn · 1 fail · 2 skip
```

## Subcommands

| command             | what it does                                                |
|---------------------|-------------------------------------------------------------|
| `wtf` / `wtf audit` | green/yellow/red checklist: what is OK and what is not      |
| `wtf problems`      | alias for `audit --only problems` — show WARN+FAIL only      |
| `wtf explain`       | per-check actionable advice; `--llm` to pipe to LLM          |
| `wtf info`          | one-page snapshot: host, uptime, load, mem, disks, top, net |
| `wtf top`           | focused process top: sort by cpu/rss, filter user/name      |
| `wtf ports`         | listening sockets with owning PID/user/command              |
| `wtf services NAME` | drilldown one service: state, restarts, mem, ports, journal |
| `wtf logs`          | recent ERROR+ journal entries grouped by service            |
| `wtf events`        | chronological timeline: reboots, OOM, failed units, …       |
| `wtf history`       | list saved audit snapshots (`wtf audit --save` to create)   |
| `wtf diff`          | compare current state to a saved snapshot                   |
| `wtf crontab`       | validate all standard crontab locations + per-user crontabs |
| `wtf doctor`        | self-diagnostic: which tools wtftools can actually use      |
| `wtf config`        | show effective config / print example                       |

`wtftools` absorbs and supersedes [`checkcrontab`](https://github.com/wachawo/checkcrontab) — the same cron validator now lives at `wtf crontab`.

## Install

### From PyPI

```bash
pip install wtftools           # core, stdlib-only
pip install wtftools[full]     # + psutil for richer metrics
```

After install the short command `wtf` (and the long alias `wtftools`) is on `$PATH`.

### From apt (Debian/Ubuntu)

```bash
sudo apt install python3-psutil
sudo dpkg -i wtftools_0.0.0-1_all.deb
```

A `.deb` is built from the same source via `scripts/build-deb.sh` (uses `stdeb`).

### From source

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
# or test without installing:
python3 wtf.py audit
```

## Usage

```bash
wtf                      # short audit summary (default)
wtf problems             # only WARN+FAIL rows
wtf info                 # detailed system snapshot
wtf info --format json   # machine-readable

wtf audit                # full audit with [OK]/[WARN]/[FAIL] markers
wtf audit -v             # show extra detail (failed units, OOM events)
wtf audit --strict       # exit 1 on warnings (CI-friendly)
wtf audit --format json  # JSON output for pipelines
wtf audit --check memory --check disks   # run named checks only
wtf audit --list-checks  # show all available check short-names
wtf audit --since 1      # look-back window for OOM/auth/kernel (default 24h)
wtf audit --brief        # one-line summary for MOTD / SSH banners
wtf audit --ignore swap --ignore "disk /mnt/Backup"   # silence specific checks
wtf audit --format csv > audit.csv               # spreadsheet-friendly
wtf audit --format plain | awk '$1=="fail"'      # shell-pipeline-friendly
wtf audit --format html -o report.html           # self-contained HTML for tickets

wtf audit --save                 # save snapshot to ~/.cache/wtftools/
wtf diff                         # what changed vs last snapshot
wtf diff --snapshot 5            # vs 5 snapshots ago
wtf history                      # list saved snapshots

wtf explain                                 # per-check actionable advice
wtf explain --prompt | ollama run llama3    # pipe to local LLM
wtf explain --llm ollama                    # built-in: call ollama directly
wtf explain --llm claude                    # anthropic SDK + ANTHROPIC_API_KEY
wtf explain --llm auto                      # try ollama → claude → openai

wtf audit --alert 'mail -s "wtf $WTF_HOST" sre@example.com'
wtf audit --alert-on warn --alert 'curl -X POST $SLACK_WEBHOOK -d @-'

wtf top                                       # top processes
wtf top --sort rss --user www-data --limit 5  # top RAM consumers for one user
wtf ports                                     # listening TCP + owning process

wtf services nginx       # state + restarts + ports + last 20 journal lines
wtf logs                                       # last hour, ERROR+
wtf events --since 48                          # 48-hour incident timeline
wtf events --kind oom --kind failed-unit       # filter to specific kinds

wtf doctor               # show which CLI tools wtf can use on this host
wtf doctor --check-updates  # also query PyPI for a newer version
```

## Exit codes

| code | meaning                                          |
|------|--------------------------------------------------|
| 0    | everything OK (`audit`) / no errors (`crontab`)  |
| 1    | warnings with `--strict`, or crontab errors      |
| 2    | audit found a `[FAIL]`                           |
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

Run `wtf audit --list-checks` for the full list of short names usable with
`--check` and `--ignore`.

## Config

Drop an INI at any of:

- `/etc/wtftools/config.ini`
- `/etc/wtf/config.ini`
- `~/.config/wtftools/config.ini`

Or stack one ad-hoc via `wtf --config /path/to.ini …`. Run `wtf config --example`
for a fully-commented template. Headlines:

```ini
[thresholds]
disk_warn = 85
disk_fail = 95
swap_warn = 50
swap_fail = 90
tcp_retrans_warn = 1.0
tcp_retrans_fail = 5.0

[ignore]
checks = swap, updates
result_names =
    disk /mnt/Backup
    disk /mnt/Video
```

## Plugins

Drop an executable script into one of:

- `/etc/wtf/checks.d/`
- `/etc/wtftools/checks.d/`
- `~/.config/wtftools/checks.d/`

It is automatically picked up by `wtf audit` under the name `plugin:<basename>`.

**Exit-code contract:** `0` ok, `1` warn, `2` fail, `77` skip (anything else
is treated as fail). stdout becomes the message line.

**JSON contract (optional, takes precedence):** the script may print a single
JSON line on stdout:

```json
{"status": "warn", "message": "TLS expires in 7 days", "detail": ["host=example.com"]}
```

See `examples/plugins/` for five production-ready examples
and [docs/PLUGIN_GUIDE.md](docs/PLUGIN_GUIDE.md) for the full author guide.

**Writing your own?** Python plugins can use
`wtftools.plugin_sdk` for boilerplate-free `ok() / warn() / fail() / skip()`
calls instead of hand-rolling the JSON.

## Compatibility

- Python 3.8+
- Linux (any systemd-based distribution is the happy path; the tool degrades
  gracefully when `systemctl` / `journalctl` are missing)
- No network access required for the core CLI
- Optional network: `wtf explain --llm claude/openai`, `wtf doctor --check-updates`

## License

MIT
