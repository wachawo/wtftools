# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> One command to see what is going on with your Linux server right now.

**English** | [Español](https://github.com/wachawo/wtftools/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/wtftools/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/wtftools/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/wtftools/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/wtftools/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/wtftools/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/wtftools/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/wtftools/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/wtftools/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/wtftools/blob/main/docs/README_KR.md)

You log in to a server and something feels wrong. Instead of running ten
commands (`htop`, `df -h`, `journalctl`, `systemctl --failed`, …) you run one:

```
$ wtf
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

Green is fine, yellow needs a look, red needs fixing. That's it.

## Install

```bash
pipx install wtftools          # recommended — works on any modern distro
```

No `pipx`? Any of these works too:

```bash
pip install wtftools           # classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

After install you have the `wtf` command. Try it: `wtf`.

## The commands you will actually use

```bash
wtf              # full health check — start here
wtf problems     # show ONLY what is wrong (warnings + failures)
wtf explain      # what to do about each problem, step by step
```

Then ask about one resource at a time, like `show` commands on a switch:

```bash
wtf disk         # is there space? per-mount usage, inodes, read-only
wtf disk /var    # WHAT is eating space under /var (largest folders)
wtf disk / --tree  # drill into the biggest folders, level by level
wtf cpu          # load, iowait, top CPU consumers
wtf mem          # RAM/swap, OOM kills, top memory consumers
wtf net          # interfaces, IPs, gateway, DNS, listening ports
wtf io           # disk read/write rates, IO-stuck processes
wtf who          # who is logged in, recent logins, failed auth
wtf temp         # hardware temperatures (CPU/disk/board sensors)
```

`wtf disk` with no path is the mount overview — full path, used/total, percent
and a usage bar:

```
$ wtf disk
# DISK
  /            1.4TB / 1.8TB   79%  [████████████████····]  ext4
  /boot      216.4MB / 1.9GB   11%  [██··················]  ext4
  /mnt/Data    5.3TB / 13.9TB  38%  [████████············]  ext4
```

Example — disk is filling up, find the culprit. `wtf disk <path>` lists the
folders directly under it, biggest first (`path/  size  % of root  depth`):

```
$ wtf disk /var
# DISK USAGE /var
  lib/      15.0GB  75%  0
  log/       3.1GB  16%  0
  cache/     1.2GB   6%  0
```

Add `--tree` to drill into the biggest folder, level by level (`--depth`,
default 3); `--tree N` opens the N largest at each level. The trailing number
is the depth:

```
$ wtf disk / --tree
# DISK USAGE /
  home/                 1021.0GB  70%  0
  home/wachawo/         1021.0GB  70%  1
  home/wachawo/myApps/   429.7GB  30%  2
  usr/                   207.9GB  14%  0
  var/                   206.5GB  14%  0
```

`wtf disk --tree` without a path drills the fullest mount. Run with `sudo` to
read root-owned folders. The `# DISK` mount overview (no path) is unchanged.

Learning Linux? Add `--show-commands` to any resource command and it also
prints the classic commands it replaces, so you can run them yourself:

```
$ wtf cpu --show-commands
  ...
  equivalent commands:
    $ uptime
    $ top -bn1 | head
    $ ps aux --sort=-%cpu | head
```

## When something is broken

```bash
wtf problems -v                 # every problem, with detail
wtf events --since 6            # timeline: reboots, OOM kills, failed units
wtf service nginx               # one service: state, restarts, ports, journal
wtf logs --since '2 hours ago'  # recent ERROR+ journal entries by service
wtf explain                     # actionable advice per finding
wtf explain --llm ollama        # or let a local LLM summarize it
```

### Who is on a port?

`wtf port <N>` (or `wtf ports <N>`) shows which process holds a port — the
PID, the exact executable file behind it (via `lsof` + `/proc`), and the
directory it runs from:

```
$ wtf port 5060
# PORT 5060
  tcp *:5060 (LISTEN)
    pid     : 1234
    user    : asterisk
    command : asterisk
    exe     : /usr/sbin/asterisk
    cwd     : /var/lib/asterisk
```

Run it with `sudo` to see processes owned by other users.

### Where was this container started?

`wtf docker <name>` answers "which folder did `docker compose up` run in?"
straight from the container's labels — and how much disk it eats (image
layers, the writable container layer, and the json log):

```
$ wtf docker myapp_web
# myapp_web
  image        : myapp:latest
  status       : running
  compose      : myapp / web
  working dir  : /home/deploy/myapp
  config files : /home/deploy/myapp/docker-compose.yml
  image size   : 156.4MB
  container    : 254.3MB (writable layer)
  logs         : 53.8MB
```

`wtf docker` with no name lists every running container with its size
columns and working dir, plus a TOTAL row:

```
$ sudo wtf docker
# DOCKER
  NAME         STATUS       IMAGE   CONTNR     LOGS  WORKING DIR
  myapp_web    running      164MB    267MB   53.8MB  /home/deploy/myapp
  myapp_db     running      276MB     63B    4.02MB  /home/deploy/myapp
  TOTAL                     440MB    267MB   57.8MB
  note: IMAGE total is logical (images share layers); real disk 9.2GB, 1.1GB reclaimable — docker system df; logs cap with max-size; decimal units, like docker
```

Sizes use decimal units (1GB = 1000MB), so they line up with
`docker container ls --size`. Per-row IMAGE is the image's full logical size
(what `docker` calls the *virtual* size). The IMAGE total dedupes by image id,
so one image shared by many containers is counted once — not once per
container. **But** different images still share base layers on disk, so even
that deduped sum overstates real usage; the note line shows the true
layer-deduplicated disk straight from `docker system df`. CONTNR (writable
layer) and LOGS are per-container, so those totals are exact. Log sizes need
read access under `/var/lib/docker` — run with `sudo`, otherwise they show `?`.

## Output for scripts: grep, awk, jq

Colors disappear automatically when you pipe, so plain `grep` always works.
Every command also has machine-readable formats — `plain` (tab-separated,
no headers) and `json`. The flag works before the subcommand too:

```bash
wtf -f json disk                         # same as: wtf disk --format json
wtf disk --format plain                  # tab-separated, no headers
wtf disk --format json | jq .            # full JSON

# mounts above 80%:
wtf disk --format json | jq -r '.mounts[] | select(.percent > 80) | .target'

# failed checks only, names column:
wtf audit --format plain | awk -F'\t' '$1 == "fail" {print $2}'

# top directory eating /var, bytes and path:
wtf disk /var --format plain | awk -F'\t' 'NR==1 {print $3, $1}'   # biggest folder: path, bytes
```

JSON payloads of the resource commands carry `schema_version` so your
scripts survive upgrades.

## Daily routine and monitoring

One command for the morning check — audit, what changed since the last run,
and the event timeline, with a one-line verdict on top:

```bash
wtf daily                       # audit + diff vs yesterday + events
```

It saves a snapshot on every run, so tomorrow's `wtf daily` shows the diff.
A crontab line for unattended use (mails only when something is wrong):

```cron
0 8 * * * wtf daily --format json > /var/log/wtf-daily.json 2>&1 || mail -s "wtf $(hostname)" you@example.com < /var/log/wtf-daily.json
```

The building blocks are also available separately:

```bash
wtf audit --brief               # one line — perfect for MOTD / SSH banner
wtf audit --save                # save a snapshot
wtf diff                        # what changed since the last snapshot
wtf history                     # list saved snapshots

# cron alerting without any monitoring stack:
wtf audit --alert 'mail -s "wtf $WTF_HOST" you@example.com'
wtf audit --alert-on warn --alert 'curl -X POST $SLACK_WEBHOOK -d @-'
```

Exit codes are CI/cron-friendly:

| code | meaning                                          |
|------|--------------------------------------------------|
| 0    | everything OK                                    |
| 1    | warnings with `--strict`, or crontab errors      |
| 2    | audit found a `[FAIL]`                           |
| 130  | interrupted (Ctrl-C)                             |

## All subcommands

| command             | what it does                                                |
|---------------------|-------------------------------------------------------------|
| `wtf` / `wtf audit` | green/yellow/red checklist: what is OK and what is not      |
| `wtf problems`      | only WARN+FAIL rows                                         |
| `wtf daily`         | morning check: audit + diff vs last run + events            |
| `wtf explain`       | per-check actionable advice; `--llm` to pipe to an LLM      |
| `wtf disk [PATH]`   | mounts overview; with PATH, largest folders; `--tree` drills |
| `wtf cpu`           | load, iowait, pressure, top CPU consumers                   |
| `wtf mem`           | RAM/swap, OOM kills, top memory consumers                   |
| `wtf net`           | interfaces, gateway, DNS, errors, listening ports           |
| `wtf io`            | per-device IO rates, pressure, stuck processes              |
| `wtf who`           | logged-in users, recent logins, failed auth                 |
| `wtf temp`          | hardware temperatures from /sys/class/hwmon sensors         |
| `wtf info`          | one-page snapshot: all of the above at once                 |
| `wtf top`           | focused process top: sort by cpu/rss, filter user/name      |
| `wtf ports`         | listening sockets with owning PID/user/command              |
| `wtf port NUM`      | drill into one port: PID, executable file, working dir      |
| `wtf docker [NAME]` | container compose working dir + image/container/log sizes    |
| `wtf service NAME`  | drilldown one service: state, restarts, mem, ports, journal |
| `wtf logs`          | recent ERROR+ journal entries grouped by service            |
| `wtf events`        | chronological timeline: reboots, OOM, failed units, …       |
| `wtf history`       | list saved audit snapshots (`wtf audit --save` to create)   |
| `wtf diff`          | compare current state to a saved snapshot                   |
| `wtf crontab`       | validate all standard crontab locations + per-user crontabs |
| `wtf doctor`        | self-diagnostic: which tools wtftools can actually use      |
| `wtf config`        | show effective config / print example                       |

`wtftools` absorbs and supersedes
[`checkcrontab`](https://github.com/wachawo/checkcrontab) — the same cron
validator now lives at `wtf crontab`.

## Advanced audit options

```bash
wtf audit -v             # show extra detail (failed units, OOM events)
wtf audit --strict       # exit 1 on warnings (CI-friendly)
wtf audit --check memory --check disks    # run named checks only
wtf audit --list-checks  # show all available check short-names
wtf audit --since 1      # look-back window for OOM/auth/kernel (default 24h)
wtf audit --ignore swap --ignore "disk /mnt/Backup"   # silence checks
wtf audit --format csv > audit.csv        # spreadsheet-friendly
wtf audit --format html -o report.html    # self-contained HTML for tickets
wtf audit --format prometheus             # metrics for node_exporter textfile
```

### Built-in checks

uptime · system state · load average · CPU iowait · PSI cpu/memory/io ·
TCP retransmits · memory · swap · disk (per mount) · inodes ·
read-only mounts · failed systemd units · enabled-but-down services ·
restart loops · network errors · conntrack · journal disk usage · zombies ·
D-state processes · OOM kills · kernel errors · kernel taint · cert expiry ·
open file descriptors · process count · failed auth · time sync ·
pending updates · reboot required · cron daemon · crontab syntax · docker ·
hw temperatures · disk SMART · DNS · HTTP/TCP probes · fail2ban.

## Config

Thresholds and ignores live in an INI file at any of:

- `/etc/wtftools/config.ini`
- `/etc/wtf/config.ini`
- `~/.config/wtftools/config.ini`

Run `wtf config --example` for a fully-commented template. Headlines:

```ini
[thresholds]
disk_warn = 85
disk_fail = 95
swap_warn = 50
swap_fail = 90

[ignore]
checks = swap, updates
result_names =
    disk /mnt/Backup
```

## Compatibility

- Python 3.8+
- Linux (systemd distributions are the happy path; the tool degrades
  gracefully when `systemctl` / `journalctl` / `psutil` are missing)
- No network access required for the core CLI
- Optional network: `wtf explain --llm claude/openai`, `wtf doctor --check-updates`

## From source

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
# or test without installing:
python3 wtf.py audit
```

## License

MIT
