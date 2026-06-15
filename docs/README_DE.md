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
[ OK ] zombie processes        0 zombies
[FAIL] failed systemd units    1 failed unit(s)
[ OK ] crontab syntax          14 cron line(s), no errors

  Summary: 12 ok · 1 warn · 1 fail · 2 skip
```

Grün ist in Ordnung, Gelb braucht einen Blick, Rot muss behoben werden. Das war's.

## Installation

```bash
pipx install wtftools          # recommended — works on any modern distro
```

Kein `pipx`? Jede dieser Varianten funktioniert ebenfalls:

```bash
pip install wtftools           # classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

Nach der Installation hast du den Befehl `wtf`. Probiere ihn aus: `wtf`.

Tab-completion (optional) — füge eine Zeile zu deiner Shell-rc-Datei hinzu und drücke `<Tab>`:

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

Führe `wtf completion` ohne Argument aus, um die vollständige Anleitung zu erhalten.

## Die Befehle, die du wirklich verwenden wirst

```bash
wtf              # full health check — start here
wtf problems     # show ONLY what is wrong (warnings + failures)
wtf explain      # what to do about each problem, step by step
```

Frage anschließend nach jeweils einer Ressource, ähnlich wie die `show`-Befehle auf einem Switch:

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

`wtf disk` ohne Pfad ist die Mount-Übersicht — vollständiger Pfad, belegt/gesamt, Prozent
und ein Nutzungsbalken:

```
$ wtf disk
# DISK
  /            1.4TB / 1.8TB   79%  [████████████████····]  ext4
  /boot      216.4MB / 1.9GB   11%  [██··················]  ext4
  /mnt/Data    5.3TB / 13.9TB  38%  [████████············]  ext4
```

Beispiel — die Festplatte füllt sich, finde den Verursacher. `wtf disk <path>` listet die
Ordner direkt darunter auf, die größten zuerst (`path/  size  % of root  depth`):

```
$ wtf disk /var
# DISK USAGE /var
  lib/      15.0GB  75%  0
  log/       3.1GB  16%  0
  cache/     1.2GB   6%  0
```

Füge `--tree` hinzu, um dich in den größten Ordner einzuarbeiten, Ebene für Ebene (`--depth`,
Standard 3); `--tree N` öffnet die N größten auf jeder Ebene. Die abschließende Zahl
ist die Tiefe:

```
$ wtf disk / --tree
# DISK USAGE /
  home/                 1021.0GB  70%  0
  home/wachawo/         1021.0GB  70%  1
  home/wachawo/myApps/   429.7GB  30%  2
  usr/                   207.9GB  14%  0
  var/                   206.5GB  14%  0
```

`wtf disk --tree` ohne Pfad arbeitet sich in den vollsten Mountpoint ein. Führe es mit `sudo`
aus, um root-eigene Ordner zu lesen. Die `# DISK` Mount-Übersicht (ohne Pfad) bleibt unverändert.

Du lernst Linux? Füge `--show-commands` zu jedem Ressourcen-Befehl hinzu, und er
gibt zusätzlich die klassischen Befehle aus, die er ersetzt, damit du sie selbst ausführen kannst:

```
$ wtf cpu --show-commands
  ...
  equivalent commands:
    $ uptime
    $ top -bn1 | head
    $ ps aux --sort=-%cpu | head
```

## Wenn etwas kaputt ist

```bash
wtf problems -v                 # every problem, with detail
wtf events --since 6            # timeline: reboots, OOM kills, failed units
wtf service nginx               # one service: state, restarts, ports, journal
wtf logs --since '2 hours ago'  # recent ERROR+ journal entries by service
wtf explain                     # actionable advice per finding
wtf explain --llm ollama        # or let a local LLM summarize it
```

### Wer belegt einen Port?

`wtf port <N>` (oder `wtf ports <N>`) zeigt, welcher Prozess einen Port hält — die
PID, die genaue ausführbare Datei dahinter (über `lsof` + `/proc`) und das
Verzeichnis, aus dem er läuft:

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

Führe ihn mit `sudo` aus, um Prozesse anderer Benutzer zu sehen.

### Wo wurde dieser Container gestartet?

`wtf docker <name>` beantwortet die Frage "in welchem Ordner wurde `docker compose up`
ausgeführt?" direkt aus den Labels des Containers — und wie viel Speicherplatz er verbraucht
(Image-Layer, der beschreibbare Container-Layer und das json-Log):

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

`wtf docker` ohne Namen listet jeden laufenden Container mit seinen Größenspalten
und seinem Arbeitsverzeichnis auf, ergänzt um eine TOTAL-Zeile:

```
$ sudo wtf docker
# DOCKER
  NAME         STATUS       IMAGE   CONTNR     LOGS  WORKING DIR
  myapp_web    running      164MB    267MB   53.8MB  /home/deploy/myapp
  myapp_db     running      276MB     63B    4.02MB  /home/deploy/myapp
  TOTAL                     440MB    267MB   57.8MB
  note: IMAGE total is logical (images share layers); real disk 9.2GB, 1.1GB reclaimable — docker system df; logs cap with max-size; decimal units, like docker
```

Die Größen verwenden Dezimaleinheiten (1GB = 1000MB), sodass sie mit
`docker container ls --size` übereinstimmen. Der IMAGE-Wert pro Zeile ist die volle logische
Größe des Images (was `docker` als *virtuelle* Größe bezeichnet). Der IMAGE-Gesamtwert
dedupliziert nach Image-ID, sodass ein von vielen Containern gemeinsam genutztes Image
einmal gezählt wird — nicht einmal pro Container. **Aber** verschiedene Images teilen sich
auf der Festplatte trotzdem Basis-Layer, sodass selbst diese deduplizierte Summe die reale
Nutzung überschätzt; die note-Zeile zeigt den echten, layer-deduplizierten Festplattenwert
direkt aus `docker system df`. CONTNR (beschreibbarer Layer) und LOGS sind pro Container,
sodass diese Summen exakt sind. Log-Größen benötigen Lesezugriff unter
`/var/lib/docker` — führe den Befehl mit `sudo` aus, andernfalls zeigen sie `?`.

## Ausgabe für Skripte: grep, awk, jq

Farben verschwinden automatisch, wenn du die Ausgabe per Pipe weiterleitest, sodass einfaches `grep` immer funktioniert.
Jeder Befehl hat außerdem maschinenlesbare Formate — `plain` (tabulatorgetrennt,
ohne Kopfzeilen) und `json`. Das Flag funktioniert auch vor dem Unterbefehl:

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

Die JSON-Nutzdaten der Ressourcen-Befehle enthalten `schema_version`, damit deine
Skripte Upgrades überstehen.

## Tägliche Routine und Monitoring

Ein Befehl für die morgendliche Prüfung — Audit, was sich seit dem letzten Lauf geändert hat,
und die Ereignis-Zeitleiste, mit einem einzeiligen Urteil ganz oben:

```bash
wtf daily                       # audit + diff vs yesterday + events
```

Es speichert bei jedem Lauf einen Snapshot, sodass das morgige `wtf daily` den Unterschied anzeigt.
Eine crontab-Zeile für den unbeaufsichtigten Einsatz (verschickt nur dann Mails, wenn etwas nicht stimmt):

```cron
0 8 * * * wtf daily --format json > /var/log/wtf-daily.json 2>&1 || mail -s "wtf $(hostname)" you@example.com < /var/log/wtf-daily.json
```

Die Bausteine sind auch einzeln verfügbar:

```bash
wtf audit --brief               # one line — perfect for MOTD / SSH banner
wtf audit --save                # save a snapshot
wtf diff                        # what changed since the last snapshot
wtf history                     # list saved snapshots

# cron alerting without any monitoring stack:
wtf audit --alert 'mail -s "wtf $WTF_HOST" you@example.com'
wtf audit --alert-on warn --alert 'curl -X POST $SLACK_WEBHOOK -d @-'
```

Die Exit-Codes sind CI-/cron-freundlich:

| Code | Bedeutung                                        |
|------|--------------------------------------------------|
| 0    | alles in Ordnung                                 |
| 1    | Warnungen mit `--strict` oder crontab-Fehler     |
| 2    | Audit hat ein `[FAIL]` gefunden                  |
| 130  | unterbrochen (Strg-C)                            |

## Alle Unterbefehle

| Befehl              | was er macht                                                |
|---------------------|-------------------------------------------------------------|
| `wtf` / `wtf audit` | grün/gelb/rot Checkliste: was in Ordnung ist und was nicht  |
| `wtf problems`      | nur WARN+FAIL-Zeilen                                        |
| `wtf daily`         | morgendliche Prüfung: Audit + Diff zum letzten Lauf + Ereignisse |
| `wtf explain`       | umsetzbarer Rat pro Prüfung; `--llm` zum Weiterleiten an ein LLM |
| `wtf disk [PATH]`   | Mount-Übersicht; mit PATH die größten Ordner; `--tree` arbeitet sich ein |
| `wtf cpu`           | Last, iowait, Pressure, Top-CPU-Verbraucher                |
| `wtf mem`           | RAM/Swap, OOM-Kills, Top-Speicher-Verbraucher              |
| `wtf net`           | Schnittstellen, Gateway, DNS, Fehler, lauschende Ports     |
| `wtf io`            | IO-Raten pro Gerät, Pressure, hängende Prozesse            |
| `wtf who`           | angemeldete Benutzer, letzte Anmeldungen, fehlgeschlagene Authentifizierung |
| `wtf temp`          | Hardware-Temperaturen von /sys/class/hwmon-Sensoren        |
| `wtf info`          | einseitiger Snapshot: alles oben Genannte auf einmal       |
| `wtf top`           | fokussiertes Prozess-Top: sortiert nach cpu/rss, Filter nach Benutzer/Name |
| `wtf ports`         | lauschende Sockets mit zugehöriger PID/Benutzer/Befehl     |
| `wtf port NUM`      | einen Port im Detail: PID, ausführbare Datei, Arbeitsverzeichnis |
| `wtf docker [NAME]` | Compose-Arbeitsverzeichnis des Containers + Image-/Container-/Log-Größen |
| `wtf service NAME`  | Detailansicht eines Dienstes: Zustand, Neustarts, Speicher, Ports, Journal |
| `wtf logs`          | letzte ERROR+ Journal-Einträge, gruppiert nach Dienst      |
| `wtf events`        | chronologische Zeitleiste: Reboots, OOM, fehlgeschlagene Units, … |
| `wtf history`       | gespeicherte Audit-Snapshots auflisten (`wtf audit --save` zum Erstellen) |
| `wtf diff`          | aktuellen Zustand mit einem gespeicherten Snapshot vergleichen |
| `wtf crontab`       | alle Standard-crontab-Speicherorte + benutzerspezifische crontabs validieren |
| `wtf doctor`        | Selbstdiagnose: welche Werkzeuge wtftools tatsächlich nutzen kann |
| `wtf config`        | effektive Konfiguration anzeigen / Beispiel ausgeben       |
| `wtf completion`    | ein bash/zsh `<Tab>`-Completion-Skript ausgeben (oder Einrichtungshilfe) |

`wtftools` absorbiert und ersetzt
[`checkcrontab`](https://github.com/wachawo/checkcrontab) — derselbe cron-Validator
lebt jetzt unter `wtf crontab`.

## Erweiterte Audit-Optionen

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

### Eingebaute Prüfungen

uptime · system state · load average · CPU iowait · PSI cpu/memory/io ·
TCP retransmits · memory · swap · disk (per mount) · inodes ·
read-only mounts · failed systemd units · enabled-but-down services ·
restart loops · network errors · conntrack · journal disk usage · zombies ·
D-state processes · OOM kills · kernel errors · kernel taint · cert expiry ·
open file descriptors · process count · failed auth · time sync ·
pending updates · reboot required · cron daemon · crontab syntax · docker ·
hw temperatures · disk SMART · DNS · HTTP/TCP probes · fail2ban.

## Konfiguration

Schwellenwerte und Ausnahmen befinden sich in einer INI-Datei an einem der folgenden Orte:

- `/etc/wtftools/config.ini`
- `/etc/wtf/config.ini`
- `~/.config/wtftools/config.ini`

Führe `wtf config --example` aus, um eine vollständig kommentierte Vorlage zu erhalten. Die wichtigsten Punkte:

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

## Kompatibilität

- Python 3.8+
- Linux (systemd-Distributionen sind der bevorzugte Weg; das Werkzeug funktioniert
  weiterhin sinnvoll, wenn `systemctl` / `journalctl` / `psutil` fehlen)
- Kein Netzwerkzugriff für die Kern-CLI erforderlich
- Optionales Netzwerk: `wtf explain --llm claude/openai`, `wtf doctor --check-updates`

## Aus dem Quellcode

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
# or test without installing:
python3 wtf.py audit
```

## Lizenz

MIT
