# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> `wtf` — one read-only command that tells you what's wrong with a Linux box right now.

No agent. No daemon. No config. No network calls. No dependencies (Python
standard library only; `psutil` optional). Safe to run on production over SSH —
it only *reads*. Try it in two seconds, nothing to install: `pipx run wtftools`

**English** | [Español](https://github.com/wachawo/wtftools/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/wtftools/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/wtftools/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/wtftools/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/wtftools/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/wtftools/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/wtftools/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/wtftools/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/wtftools/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/wtftools/blob/main/docs/README_KR.md)

Instead of running ten commands (`htop`, `df -h`, `journalctl`,
`systemctl --failed`, `ss`, `dmesg`, …) you run one:

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

Green is fine, yellow needs a look, red needs fixing. Two ways admins live in it:

- **Incident** — something feels off → `wtf` → a green/yellow/red checklist
  instead of ten scattered commands.
- **Daily** — `wtf daily` as the morning check, `wtf` in your MOTD login banner,
  `wtf audit --alert …` from cron. No monitoring stack required.

## What it can do

- **Health audit** — 35+ checks (disk, memory, swap, load, PSI, OOM kills,
  failed units, cert expiry, SMART, temperatures, DNS, …) as a
  green / yellow / red checklist.
- **Per-resource views** — ask about one thing at a time, like `show` commands
  on a switch: `wtf disk`, `wtf cpu`, `wtf mem`, `wtf net`, `wtf docker`, …
- **Incident triage** — `wtf problems`, `wtf events`, `wtf logs`,
  `wtf services <unit>`, `wtf explain` (optionally through a local or hosted LLM).
- **Trends & alerting** — `wtf daily`, snapshots + `wtf diff`, cron alerts —
  no monitoring stack required.
- **Scriptable** — `-f json` on every command and `-f plain` (tab-separated) on
  the resource and audit views; the JSON carries a `schema_version` so scripts
  survive upgrades — for grep / awk / jq.
- **Beginner-friendly** — `--show-commands` prints the classic commands each
  view replaces, so you can learn them by hand.

## Install

```bash
pipx install wtftools          # recommended — works on any modern distro
pip install wtftools           # or classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i python3-wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

After install you have the `wtf` command. Enable `<Tab>` completion by adding
one line to your shell rc:

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

New here? Start with the [5-minute quickstart](https://github.com/wachawo/wtftools/blob/main/docs/QUICKSTART.md).

## Commands

Run `wtf <command> --help` for flags. Each command links to its reference page
with examples.

### Health & monitoring — [docs/AUDIT.md](https://github.com/wachawo/wtftools/blob/main/docs/AUDIT.md)

| command | what it does |
|---------|--------------|
| [`wtf` / `wtf audit`](https://github.com/wachawo/wtftools/blob/main/docs/AUDIT.md#wtf-audit) | green/yellow/red checklist of what is OK and what is not |
| [`wtf problems`](https://github.com/wachawo/wtftools/blob/main/docs/AUDIT.md#wtf-problems) | only the WARN+FAIL rows |
| [`wtf daily`](https://github.com/wachawo/wtftools/blob/main/docs/AUDIT.md#wtf-daily) | morning check: audit + diff vs last run + events |
| [`wtf explain`](https://github.com/wachawo/wtftools/blob/main/docs/AUDIT.md#wtf-explain) | actionable advice per finding; `--llm` to pipe to an LLM |
| [`wtf events`](https://github.com/wachawo/wtftools/blob/main/docs/AUDIT.md#wtf-events) | timeline: reboots, OOM kills, failed units, … |
| [`wtf logs`](https://github.com/wachawo/wtftools/blob/main/docs/AUDIT.md#wtf-logs) | recent ERROR+ journal entries grouped by service |
| [`wtf services`](https://github.com/wachawo/wtftools/blob/main/docs/AUDIT.md#wtf-services) | drill into one unit: state, restarts, ports, journal |
| [`wtf diff`](https://github.com/wachawo/wtftools/blob/main/docs/AUDIT.md#wtf-diff) | compare current state to a saved snapshot |
| [`wtf history`](https://github.com/wachawo/wtftools/blob/main/docs/AUDIT.md#wtf-history) | list saved audit snapshots |
| [`wtf crontab`](https://github.com/wachawo/wtftools/blob/main/docs/AUDIT.md#wtf-crontab) | validate system + per-user crontabs |
| [`wtf doctor`](https://github.com/wachawo/wtftools/blob/main/docs/AUDIT.md#wtf-doctor) | self-diagnostic: which tools/files wtf can use |

### Resource views — [docs/RESOURCES.md](https://github.com/wachawo/wtftools/blob/main/docs/RESOURCES.md)

| command | what it does |
|---------|--------------|
| [`wtf disk [PATH]`](https://github.com/wachawo/wtftools/blob/main/docs/RESOURCES.md#wtf-disk) | mounts overview; with a PATH, the largest folders; `--tree` drills in |
| [`wtf cpu`](https://github.com/wachawo/wtftools/blob/main/docs/RESOURCES.md#wtf-cpu) | load, iowait, pressure, top CPU consumers |
| [`wtf mem`](https://github.com/wachawo/wtftools/blob/main/docs/RESOURCES.md#wtf-mem) | RAM/swap, OOM kills, top memory consumers |
| [`wtf net`](https://github.com/wachawo/wtftools/blob/main/docs/RESOURCES.md#wtf-net) | interfaces, gateway, DNS, errors, listening ports |
| [`wtf io`](https://github.com/wachawo/wtftools/blob/main/docs/RESOURCES.md#wtf-io) | per-device IO rates, pressure, stuck processes |
| [`wtf who`](https://github.com/wachawo/wtftools/blob/main/docs/RESOURCES.md#wtf-who) | logged-in users, recent logins, failed auth |
| [`wtf temp`](https://github.com/wachawo/wtftools/blob/main/docs/RESOURCES.md#wtf-temp) | hardware temperatures from /sys/class/hwmon |
| [`wtf info`](https://github.com/wachawo/wtftools/blob/main/docs/RESOURCES.md#wtf-info) | one-page snapshot: all of the above at once |
| [`wtf top`](https://github.com/wachawo/wtftools/blob/main/docs/RESOURCES.md#wtf-top) | focused process top: sort by cpu/rss, filter by user/name |
| [`wtf ports` / `wtf port N`](https://github.com/wachawo/wtftools/blob/main/docs/RESOURCES.md#wtf-ports) | listening sockets; drill one port to PID, exe, cwd |
| [`wtf docker [NAME]`](https://github.com/wachawo/wtftools/blob/main/docs/RESOURCES.md#wtf-docker) | container compose dir + image/container/log sizes |

### Output & configuration

| command | what it does |
|---------|--------------|
| [`wtf config`](https://github.com/wachawo/wtftools/blob/main/docs/CONFIG.md#wtf-config) | show effective config / print a commented example |
| [`wtf completion`](#install) | print a bash/zsh `<Tab>`-completion script |
| [machine output](https://github.com/wachawo/wtftools/blob/main/docs/OUTPUT.md) | `plain`/`json` formats and a grep·awk·jq cookbook |

`wtftools` absorbs and supersedes
[`checkcrontab`](https://github.com/wachawo/checkcrontab) — the same cron
validator now lives at `wtf crontab`.

## Documentation

- [QUICKSTART.md](https://github.com/wachawo/wtftools/blob/main/docs/QUICKSTART.md) — 5-minute onboarding and a cheat sheet
- [AUDIT.md](https://github.com/wachawo/wtftools/blob/main/docs/AUDIT.md) — health checks, monitoring, exit codes, the full check list
- [RESOURCES.md](https://github.com/wachawo/wtftools/blob/main/docs/RESOURCES.md) — per-resource views with examples
- [OUTPUT.md](https://github.com/wachawo/wtftools/blob/main/docs/OUTPUT.md) — `plain`/`json` formats and the scripting cookbook
- [CONFIG.md](https://github.com/wachawo/wtftools/blob/main/docs/CONFIG.md) — config file, thresholds, ignoring checks
- [ROADMAP.md](https://github.com/wachawo/wtftools/blob/main/docs/ROADMAP.md) — what's planned and what's out of scope

## Compatibility

- Python 3.9+
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
