# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> Ein einziger Befehl, um zu sehen, was gerade auf deinem Linux-Server vor sich geht.

[English](https://github.com/wachawo/wtftools/blob/main/README.md) | [Español](https://github.com/wachawo/wtftools/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/wtftools/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/wtftools/blob/main/docs/README_FR.md) | **Deutsch** | [Italiano](https://github.com/wachawo/wtftools/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/wtftools/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/wtftools/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/wtftools/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/wtftools/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/wtftools/blob/main/docs/README_KR.md)

Du loggst dich auf einem Server ein und irgendetwas fühlt sich falsch an. Statt zehn
Befehle auszuführen (`htop`, `df -h`, `journalctl`, `systemctl --failed`, …), führst du nur einen aus:

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

Grün ist in Ordnung, Gelb braucht einen Blick, Rot muss behoben werden. `wtftools` ist eine
**schreibgeschützte, abhängigkeitsfreie CLI** (nur die Python-Standardbibliothek; `psutil`
optional), die einen Haufen Diagnosebefehle in eine lesbare Antwort verwandelt —
und in eine maschinenlesbare, wenn du die Ausgabe per Pipe weiterleitest.

## Was es kann

- **Health-Audit** — über 40 Prüfungen (disk, memory, swap, load, PSI, OOM-Kills,
  fehlgeschlagene Units, Zertifikatsablauf, SMART, Temperaturen, DNS, …) als
  grün/gelb/rot-Checkliste.
- **Ansichten pro Ressource** — frage nach jeweils einer Sache, ähnlich wie die `show`-Befehle
  auf einem Switch: `wtf disk`, `wtf cpu`, `wtf mem`, `wtf net`, `wtf docker`, …
- **Vorfall-Triage** — `wtf problems`, `wtf events`, `wtf logs`,
  `wtf services <unit>`, `wtf explain` (optional über ein lokales oder gehostetes LLM).
- **Trends & Alarmierung** — `wtf daily`, Snapshots + `wtf diff`, cron-Alerts —
  kein Monitoring-Stack erforderlich.
- **Skriptfähig** — jeder Befehl bietet `plain` (tabulatorgetrennt) und `json` als Ausgabe
  mit einer `schema_version`, für grep / awk / jq.
- **Einsteigerfreundlich** — `--show-commands` gibt die klassischen Befehle aus, die jede
  Ansicht ersetzt, sodass du sie von Hand lernen kannst.

## Installation

```bash
pipx install wtftools          # recommended — works on any modern distro
pip install wtftools           # or classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i python3-wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

Nach der Installation hast du den Befehl `wtf`. Aktiviere die `<Tab>`-Vervollständigung, indem du
eine Zeile zu deiner Shell-rc-Datei hinzufügst:

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

Neu hier? Beginne mit dem [5-Minuten-Quickstart](QUICKSTART.md).

## Befehle

Führe `wtf <command> --help` aus, um die Flags zu sehen. Jeder Befehl verlinkt auf seine Referenzseite
mit Beispielen.

### Health & Monitoring — [docs/AUDIT.md](AUDIT.md)

| command | was er macht |
|---------|--------------|
| [`wtf` / `wtf audit`](AUDIT.md#wtf-audit) | grün/gelb/rot-Checkliste: was in Ordnung ist und was nicht |
| [`wtf problems`](AUDIT.md#wtf-problems) | nur die WARN+FAIL-Zeilen |
| [`wtf daily`](AUDIT.md#wtf-daily) | morgendliche Prüfung: Audit + Diff zum letzten Lauf + Ereignisse |
| [`wtf explain`](AUDIT.md#wtf-explain) | umsetzbarer Rat pro Befund; `--llm` zum Weiterleiten an ein LLM |
| [`wtf events`](AUDIT.md#wtf-events) | Zeitleiste: Reboots, OOM-Kills, fehlgeschlagene Units, … |
| [`wtf logs`](AUDIT.md#wtf-logs) | letzte ERROR+ Journal-Einträge, gruppiert nach Dienst |
| [`wtf services`](AUDIT.md#wtf-services) | Detailansicht einer Unit: Zustand, Neustarts, Ports, Journal |
| [`wtf diff`](AUDIT.md#wtf-diff) | aktuellen Zustand mit einem gespeicherten Snapshot vergleichen |
| [`wtf history`](AUDIT.md#wtf-history) | gespeicherte Audit-Snapshots auflisten |
| [`wtf crontab`](AUDIT.md#wtf-crontab) | System- und benutzerspezifische crontabs validieren |
| [`wtf doctor`](AUDIT.md#wtf-doctor) | Selbstdiagnose: welche Werkzeuge/Dateien wtf nutzen kann |

### Ansichten pro Ressource — [docs/RESOURCES.md](RESOURCES.md)

| command | was er macht |
|---------|--------------|
| [`wtf disk [PATH]`](RESOURCES.md#wtf-disk) | Mount-Übersicht; mit einem PATH die größten Ordner; `--tree` arbeitet sich ein |
| [`wtf cpu`](RESOURCES.md#wtf-cpu) | Last, iowait, Pressure, Top-CPU-Verbraucher |
| [`wtf mem`](RESOURCES.md#wtf-mem) | RAM/Swap, OOM-Kills, Top-Speicher-Verbraucher |
| [`wtf net`](RESOURCES.md#wtf-net) | Schnittstellen, Gateway, DNS, Fehler, lauschende Ports |
| [`wtf io`](RESOURCES.md#wtf-io) | IO-Raten pro Gerät, Pressure, hängende Prozesse |
| [`wtf who`](RESOURCES.md#wtf-who) | angemeldete Benutzer, letzte Anmeldungen, fehlgeschlagene Authentifizierung |
| [`wtf temp`](RESOURCES.md#wtf-temp) | Hardware-Temperaturen aus /sys/class/hwmon |
| [`wtf info`](RESOURCES.md#wtf-info) | einseitiger Snapshot: alles oben Genannte auf einmal |
| [`wtf top`](RESOURCES.md#wtf-top) | fokussiertes Prozess-Top: sortiert nach cpu/rss, Filter nach Benutzer/Name |
| [`wtf ports` / `wtf port N`](RESOURCES.md#wtf-ports) | lauschende Sockets; ein Port im Detail bis zu PID, exe, cwd |
| [`wtf docker [NAME]`](RESOURCES.md#wtf-docker) | Compose-Verzeichnis des Containers + Image-/Container-/Log-Größen |

### Ausgabe & Konfiguration

| command | was er macht |
|---------|--------------|
| [`wtf config`](CONFIG.md#wtf-config) | effektive Konfiguration anzeigen / kommentiertes Beispiel ausgeben |
| [`wtf completion`](#install) | ein bash/zsh `<Tab>`-Completion-Skript ausgeben |
| [machine output](OUTPUT.md) | `plain`/`json`-Formate und ein grep·awk·jq-Kochbuch |

`wtftools` absorbiert und ersetzt
[`checkcrontab`](https://github.com/wachawo/checkcrontab) — derselbe cron-Validator
lebt jetzt unter `wtf crontab`.

## Dokumentation

- [QUICKSTART.md](QUICKSTART.md) — 5-minütiges Onboarding und ein Spickzettel
- [AUDIT.md](AUDIT.md) — Health-Prüfungen, Monitoring, Exit-Codes, die vollständige Prüfliste
- [RESOURCES.md](RESOURCES.md) — Ansichten pro Ressource mit Beispielen
- [OUTPUT.md](OUTPUT.md) — `plain`/`json`-Formate und das Skripting-Kochbuch
- [CONFIG.md](CONFIG.md) — Konfigurationsdatei, Schwellenwerte, Prüfungen ignorieren

## Kompatibilität

- Python 3.8+
- Linux (systemd-Distributionen sind der bevorzugte Weg; das Werkzeug funktioniert
  weiterhin sinnvoll, wenn `systemctl` / `journalctl` / `psutil` fehlen)
- Kein Netzwerkzugriff für die Kern-CLI erforderlich; optionales Netzwerk nur für
  `wtf explain --llm …` und `wtf doctor --check-updates`

## Aus dem Quellcode

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
python3 wtf.py audit       # or run it without installing
```

## Lizenz

MIT
