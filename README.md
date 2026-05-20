# wtftools

> One command to see what is going on with your Linux server right now.

**Status:** v0.0.0 — initial public release. 19 subcommands, 38 built-in
checks, bash + Python plugin SDK, `wtfd` HTTP daemon for fleet management,
multi-host aggregation + drift detection, LLM-driven explain. 734 tests,
92.6 % coverage.

> **In a hurry?** See [QUICKSTART.md](QUICKSTART.md) for the 5-minute version.

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

Nineteen subcommands, plus a standalone daemon binary:

| command               | what it does                                                |
|-----------------------|-------------------------------------------------------------|
| `wtf` / `wtf audit`   | green/yellow/red checklist: what is OK and what is not      |
| `wtf explain`         | per-check actionable advice; `--prompt` for LLM pipelines   |
| `wtf info`            | one-page snapshot: host, uptime, load, mem, disks, top, net |
| `wtf top`             | focused process top: sort by cpu/rss, filter user/name      |
| `wtf ports`           | listening sockets with owning PID/user/command              |
| `wtf services NAME`   | drilldown one service: state, restarts, mem, ports, journal |
| `wtf logs`            | recent ERROR+ journal entries grouped by service            |
| `wtf events`          | chronological timeline: reboots, OOM, failed units, …       |
| `wtf history`         | list saved audit snapshots (`wtf audit --save` to create)   |
| `wtf diff`            | compare current state to a saved snapshot                   |
| `wtf serve` / `wtfd`  | run as a daemon: periodic audit + HTTP API                  |
| `wtf fleet`           | aggregate `/audit.json` from many wtfd peers in parallel    |
| `wtf compare A B`     | side-by-side diff of two wtfd hosts (config-drift)          |
| `wtf crontab`         | validate all standard crontab locations + per-user crontabs |
| `wtf doctor`          | self-diagnostic: which tools wtftools can actually use      |
| `wtf plugins`         | list discovered check plugins                               |
| `wtf config`          | show effective config / print example                       |
| `wtf motd-install`    | drop a one-line `wtf audit --brief` into update-motd.d      |
| `wtf init`            | interactive setup wizard for a fresh host                   |

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
sudo dpkg -i wtftools_0.1.0-1_all.deb
```

A `.deb` is built from the same source via `scripts/build-deb.sh` (uses `stdeb`).

### From source

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
```

### First-time setup

```bash
sudo wtf init                                # interactive wizard
sudo wtf init --non-interactive              # accept defaults (no wtfd)
sudo wtf init --non-interactive --enable-wtfd   # also enable the daemon
sudo wtf init --dry-run                      # preview without changing anything
```

## Usage

```bash
wtf                      # short audit summary (default)
wtf info                 # detailed system snapshot
wtf info --format json   # machine-readable

wtf audit                # full audit with [OK]/[WARN]/[FAIL] markers
wtf audit -v             # show extra detail (failed units, OOM events)
wtf audit --strict       # exit 1 on warnings (CI-friendly)
wtf audit --format json  # JSON output for pipelines
wtf audit --only problem # show only WARN+FAIL (great during incidents)
wtf audit --only fail    # show only FAILs
wtf audit --check memory --check disks   # run named checks only
wtf audit --list-checks  # show all available check short-names
wtf audit --since 1      # look-back window for OOM/auth/kernel (default 24h)
wtf audit --watch 5      # live mode: refresh every 5 seconds (Ctrl-C to exit)

wtf audit --brief        # one-line summary for MOTD / SSH banners
                         #   wtf: 1 fail, 3 warn — swap: 99% · zombies: 1 · …

wtf doctor               # show which CLI tools wtf can use on this host
wtf doctor --format json # machine-readable capability report
wtf doctor --check-updates  # also query PyPI for a newer version

wtf compare host1:8765 host2:8765            # full side-by-side
wtf compare host1:8765 host2:8765 --only-drift   # hide identical rows

wtf audit --ignore swap --ignore "disk /mnt/Backup"   # silence specific checks

wtf audit --serial            # disable parallelism (debug)
wtf audit --check-timeout 3   # tighten per-check budget

wtf events --since 48                          # 48-hour incident timeline
wtf events --kind oom --kind failed-unit       # filter to specific kinds
wtf events --format json                       # for ingestion

wtf logs                                       # last hour, ERROR+
wtf logs --since '6 hours ago' --priority warning
wtf logs --units 5 --lines 3 --format json     # for pipelines

wtf explain              # rule-based "what to do" for each WARN/FAIL
wtf explain --check swap --check disks
wtf explain --prompt | ollama run llama3    # pipe to local LLM
wtf explain --prompt | claude --no-tools     # or to Claude API CLI
wtf explain --llm ollama                    # built-in: call ollama directly
wtf explain --llm claude                    # built-in: anthropic SDK + ANTHROPIC_API_KEY
wtf explain --llm auto                      # try ollama → claude → openai

wtf top                                       # top processes, focused
wtf top --sort rss --user www-data --limit 5  # top RAM consumers for one user
wtf top --name redis --format json
wtf ports                                     # listening TCP + owning process
wtf ports --proto udp --public-only

sudo wtf motd-install                         # show wtf brief on each ssh login

wtf audit --format csv > audit.csv            # spreadsheet-friendly
wtf audit --format plain | awk '$1=="fail"'   # shell-pipeline-friendly
wtf audit --format html -o report.html        # self-contained HTML for tickets/email
wtf audit -o today.txt                        # write to file (drops colors)

wtf diff                                      # latest snapshot vs current
wtf diff --snapshot 5                         # 5 snapshots ago vs current
wtf diff --against old.json new.json          # two saved snapshots directly

wtf audit --save                              # save current run to ~/.cache/wtftools/
wtf audit --diff                              # show what changed vs last snapshot
wtf history                                   # list saved snapshots
wtf audit --format prometheus > /var/lib/node_exporter/wtf.prom

wtf info --watch 5                            # live host snapshot

wtf audit --alert 'mail -s "wtf $WTF_HOST" sre@example.com'
wtf audit --alert-on warn --alert 'curl -X POST $SLACK_WEBHOOK -d @-'

wtf services nginx       # state + restarts + ports + last 20 journal lines
wtf services nginx -n 50 # 50 journal lines
wtf services nginx --format json

wtf plugins              # list discovered check plugins
wtf config               # show effective thresholds + search paths
wtf config --example > /etc/wtftools/config.ini    # write a starter config
wtf --config /etc/wtftools/prod.ini audit          # stack an extra config file

wtf crontab              # check /etc/crontab, /etc/cron.d/*, all user crontabs
wtf crontab /etc/crontab # check a specific file
wtf crontab -u alice     # check a specific user
wtf crontab --format json
```

## Exit codes

| code | meaning                                          |
|------|--------------------------------------------------|
| 0    | everything OK (`audit`) / no errors (`crontab`)  |
| 1    | warnings with `--strict`, or crontab errors      |
| 2    | audit found a `[FAIL]`                            |
| 130  | interrupted (Ctrl-C)                              |

## What audit checks

uptime · load average · memory · swap · disk (per mount) · inode usage ·
failed systemd units · zombie processes · OOM kills in last 24h ·
recent kernel errors · open file descriptors · failed auth attempts ·
pending apt updates · cron daemon · crontab syntax across system + user files.

Each check is intentionally small and independent — `wtf` is the senior's
"first 10 commands" rolled into one diagnosis-oriented checklist.

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

## Daemon mode (`wtfd`)

For fleet management you want each host to expose its state. Install
`wtftools` and enable the bundled systemd unit:

```bash
sudo cp scripts/wtfd.service /etc/systemd/system/
sudo systemctl enable --now wtfd
curl -s http://127.0.0.1:8765/audit.json | jq '.summary'
```

Endpoints:

| path             | what it returns                                          |
|------------------|----------------------------------------------------------|
| `/`              | brief one-liner: host, run count, top problems           |
| `/healthz`       | liveness — always `ok` while daemon is up                |
| `/audit`         | plaintext audit (same as `wtf audit`)                    |
| `/audit.json`    | full JSON (results, summary, timestamp, error)           |
| `/audit.prom`    | Prometheus textfile-collector format                     |
| `/history`       | list of recent snapshot basenames                        |
| `/snapshot/N`    | Nth-most-recent snapshot (or pass a basename prefix)     |
| `POST /run-now`  | trigger an immediate audit refresh (202 Accepted)        |

Bind to `127.0.0.1` by default and expose through nginx/haproxy with TLS.
Or use `--auth-token-file /etc/wtftools/token` for built-in Bearer auth.

To scrape with Prometheus, point a job at `/audit.prom`:

```yaml
scrape_configs:
  - job_name: wtfd
    static_configs: [{ targets: ['host1:8765', 'host2:8765'] }]
    metrics_path: /audit.prom
```

## Fleet aggregation

Each host runs `wtfd` (see «Daemon mode» above). Then one machine (your
laptop, a jump host, a monitoring box) runs:

```bash
wtf fleet --hosts host1:8765,host2:8765,host3:8765
wtf fleet --hosts-file /etc/wtftools/fleet.hosts --problem-only
wtf fleet --hosts ... --format prometheus > /var/lib/node_exporter/fleet.prom
```

Or set `fleet_hosts = host1:8765, host2:8765` under `[thresholds]` in
`/etc/wtftools/config.ini` and just run `wtf fleet`.

Hosts are fetched in parallel (default 16 workers, 5s per-host timeout).
Output is sorted by severity — unreachable / fail / warn / ok — and includes
the top problems inline for at-a-glance triage. Use `--token-file FILE` to
authenticate against wtfd instances that have `--auth-token-file` set.

## Docker

```bash
docker build -t wtftools .
# one-shot audit of the host:
docker run --rm --pid=host --net=host -v /:/host:ro wtftools wtf audit
# wtfd daemon:
docker run -d --name wtfd --pid=host --net=host \
    -v /var/lib/wtftools:/var/lib/wtftools wtftools wtfd --listen 0.0.0.0:8765 --save
```

Most checks need `--pid=host --net=host` and a read-only `/` mount to see
the actual host state — a fully-isolated container has very little to audit.

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

See `scripts/example-plugin-check-tmp.sh` for a minimal bash example, and
`examples/plugins/` for five production-ready scripts (TLS cert probe,
PostgreSQL/Redis connection counts, disk-write latency, HTTP health).

**Writing your own?** See [PLUGIN_GUIDE.md](PLUGIN_GUIDE.md) for the full
contract + best practices. Python authors can use
`wtftools.plugin_sdk` for boilerplate-free `ok() / warn() / fail() / skip()`
calls instead of hand-rolling the JSON.

## Compatibility

- Python 3.8+
- Linux (any systemd-based distribution is the happy path; the tool degrades
  gracefully when `systemctl` / `journalctl` are missing)
- No network access required

## License

MIT
