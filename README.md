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
[FAIL] failed systemd units    1 failed unit(s)

  Summary: 12 ok · 1 warn · 1 fail · 2 skip
```

Green is fine, yellow needs a look, red needs fixing. `wtftools` is a
**read-only, dependency-free CLI** (Python standard library only; `psutil`
optional) that turns a pile of diagnostic commands into one readable answer —
and a machine-readable one when you pipe it.

## What it can do

- **Health audit** — 40+ checks (disk, memory, swap, load, PSI, OOM kills,
  failed units, cert expiry, SMART, temperatures, DNS, …) as a
  green / yellow / red checklist.
- **Per-resource views** — ask about one thing at a time, like `show` commands
  on a switch: `wtf disk`, `wtf cpu`, `wtf mem`, `wtf net`, `wtf docker`, …
- **Incident triage** — `wtf problems`, `wtf events`, `wtf logs`,
  `wtf services <unit>`, `wtf explain` (optionally through a local or hosted LLM).
- **Trends & alerting** — `wtf daily`, snapshots + `wtf diff`, cron alerts —
  no monitoring stack required.
- **Scriptable** — every command has `plain` (tab-separated) and `json` output
  carrying a `schema_version`, for grep / awk / jq.
- **Beginner-friendly** — `--show-commands` prints the classic commands each
  view replaces, so you can learn them by hand.

## Install

```bash
pipx install wtftools          # recommended — works on any modern distro
pip install wtftools           # or classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

After install you have the `wtf` command. Enable `<Tab>` completion by adding
one line to your shell rc:

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

New here? Start with the [5-minute quickstart](docs/QUICKSTART.md).

## Commands

Run `wtf <command> --help` for flags. Each command links to its reference page
with examples.

### Health & monitoring — [docs/AUDIT.md](docs/AUDIT.md)

| command | what it does |
|---------|--------------|
| [`wtf` / `wtf audit`](docs/AUDIT.md#wtf-audit) | green/yellow/red checklist of what is OK and what is not |
| [`wtf problems`](docs/AUDIT.md#wtf-problems) | only the WARN+FAIL rows |
| [`wtf daily`](docs/AUDIT.md#wtf-daily) | morning check: audit + diff vs last run + events |
| [`wtf explain`](docs/AUDIT.md#wtf-explain) | actionable advice per finding; `--llm` to pipe to an LLM |
| [`wtf events`](docs/AUDIT.md#wtf-events) | timeline: reboots, OOM kills, failed units, … |
| [`wtf logs`](docs/AUDIT.md#wtf-logs) | recent ERROR+ journal entries grouped by service |
| [`wtf services`](docs/AUDIT.md#wtf-services) | drill into one unit: state, restarts, ports, journal |
| [`wtf diff`](docs/AUDIT.md#wtf-diff) | compare current state to a saved snapshot |
| [`wtf history`](docs/AUDIT.md#wtf-history) | list saved audit snapshots |
| [`wtf crontab`](docs/AUDIT.md#wtf-crontab) | validate system + per-user crontabs |
| [`wtf doctor`](docs/AUDIT.md#wtf-doctor) | self-diagnostic: which tools/files wtf can use |

### Resource views — [docs/RESOURCES.md](docs/RESOURCES.md)

| command | what it does |
|---------|--------------|
| [`wtf disk [PATH]`](docs/RESOURCES.md#wtf-disk) | mounts overview; with a PATH, the largest folders; `--tree` drills in |
| [`wtf cpu`](docs/RESOURCES.md#wtf-cpu) | load, iowait, pressure, top CPU consumers |
| [`wtf mem`](docs/RESOURCES.md#wtf-mem) | RAM/swap, OOM kills, top memory consumers |
| [`wtf net`](docs/RESOURCES.md#wtf-net) | interfaces, gateway, DNS, errors, listening ports |
| [`wtf io`](docs/RESOURCES.md#wtf-io) | per-device IO rates, pressure, stuck processes |
| [`wtf who`](docs/RESOURCES.md#wtf-who) | logged-in users, recent logins, failed auth |
| [`wtf temp`](docs/RESOURCES.md#wtf-temp) | hardware temperatures from /sys/class/hwmon |
| [`wtf info`](docs/RESOURCES.md#wtf-info) | one-page snapshot: all of the above at once |
| [`wtf top`](docs/RESOURCES.md#wtf-top) | focused process top: sort by cpu/rss, filter by user/name |
| [`wtf ports` / `wtf port N`](docs/RESOURCES.md#wtf-ports) | listening sockets; drill one port to PID, exe, cwd |
| [`wtf docker [NAME]`](docs/RESOURCES.md#wtf-docker) | container compose dir + image/container/log sizes |

### Output & configuration

| command | what it does |
|---------|--------------|
| [`wtf config`](docs/CONFIG.md#wtf-config) | show effective config / print a commented example |
| [`wtf completion`](#install) | print a bash/zsh `<Tab>`-completion script |
| [machine output](docs/OUTPUT.md) | `plain`/`json` formats and a grep·awk·jq cookbook |

`wtftools` absorbs and supersedes
[`checkcrontab`](https://github.com/wachawo/checkcrontab) — the same cron
validator now lives at `wtf crontab`.

## Documentation

- [QUICKSTART.md](docs/QUICKSTART.md) — 5-minute onboarding and a cheat sheet
- [AUDIT.md](docs/AUDIT.md) — health checks, monitoring, exit codes, the full check list
- [RESOURCES.md](docs/RESOURCES.md) — per-resource views with examples
- [OUTPUT.md](docs/OUTPUT.md) — `plain`/`json` formats and the scripting cookbook
- [CONFIG.md](docs/CONFIG.md) — config file, thresholds, ignoring checks

## Compatibility

- Python 3.8+
- Linux (systemd distributions are the happy path; the tool degrades
  gracefully when `systemctl` / `journalctl` / `psutil` are missing)
- No network access required for the core CLI; optional network only for
  `wtf explain --llm …` and `wtf doctor --check-updates`

## From source

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
python3 wtf.py audit       # or run it without installing
```

## License

MIT
