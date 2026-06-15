# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> Un solo comando per vedere cosa sta succedendo sul tuo server Linux in questo momento.

[English](https://github.com/wachawo/wtftools/blob/main/README.md) | [Español](https://github.com/wachawo/wtftools/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/wtftools/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/wtftools/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/wtftools/blob/main/docs/README_DE.md) | **Italiano** | [Русский](https://github.com/wachawo/wtftools/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/wtftools/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/wtftools/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/wtftools/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/wtftools/blob/main/docs/README_KR.md)

Accedi a un server e qualcosa sembra non andare. Invece di eseguire dieci
comandi (`htop`, `df -h`, `journalctl`, `systemctl --failed`, …) ne esegui uno:

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

Il verde va bene, il giallo richiede un'occhiata, il rosso va sistemato. Tutto qui.

## Installazione

```bash
pipx install wtftools          # recommended — works on any modern distro
```

Niente `pipx`? Funziona anche uno qualsiasi di questi:

```bash
pip install wtftools           # classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

Dopo l'installazione hai il comando `wtf`. Provalo: `wtf`.

## I comandi che userai davvero

```bash
wtf              # full health check — start here
wtf problems     # show ONLY what is wrong (warnings + failures)
wtf explain      # what to do about each problem, step by step
```

Poi chiedi informazioni su una risorsa alla volta, come i comandi `show` su uno switch:

```bash
wtf disk         # is there space? per-mount usage, inodes, read-only
wtf disk --tree  # WHAT is eating the space (largest directories)
wtf cpu          # load, iowait, top CPU consumers
wtf mem          # RAM/swap, OOM kills, top memory consumers
wtf net          # interfaces, IPs, gateway, DNS, listening ports
wtf io           # disk read/write rates, IO-stuck processes
wtf who          # who is logged in, recent logins, failed auth
wtf temp         # hardware temperatures (CPU/disk/board sensors)
```

Esempio — il disco si sta riempiendo, trova il colpevole:

```
$ wtf disk --tree /var
# DISK
  /                [████████████████····]  79%  1.4TB / 1.8TB  ext4
  /var             [█████████████████···]  85%  17.0GB / 20.0GB  ext4

# LARGEST UNDER /var
      15.0GB  /var/lib
       3.1GB  /var/log
       1.8GB  /var/log/app
```

`wtf disk --tree` senza un percorso sceglie automaticamente il mount più pieno.

Stai imparando Linux? Aggiungi `--show-commands` a qualsiasi comando di risorsa e
stamperà anche i comandi classici che sostituisce, così puoi eseguirli da solo:

```
$ wtf cpu --show-commands
  ...
  equivalent commands:
    $ uptime
    $ top -bn1 | head
    $ ps aux --sort=-%cpu | head
```

## Quando qualcosa è rotto

```bash
wtf problems -v                 # every problem, with detail
wtf events --since 6            # timeline: reboots, OOM kills, failed units
wtf service nginx               # one service: state, restarts, ports, journal
wtf logs --since '2 hours ago'  # recent ERROR+ journal entries by service
wtf explain                     # actionable advice per finding
wtf explain --llm ollama        # or let a local LLM summarize it
```

### Chi è su una porta?

`wtf port <N>` (o `wtf ports <N>`) mostra quale processo occupa una porta — il
PID, l'esatto file eseguibile dietro di esso (tramite `lsof` + `/proc`) e la
directory da cui viene eseguito:

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

Eseguilo con `sudo` per vedere i processi di proprietà di altri utenti.

### Dove è stato avviato questo container?

`wtf docker <name>` risponde alla domanda "in quale cartella è stato eseguito
`docker compose up`?" direttamente dalle label del container — e quanto disco
consuma (i layer dell'immagine, il layer scrivibile del container e il log json):

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

`wtf docker` senza nome elenca ogni container in esecuzione con le sue colonne
di dimensione e la working dir, più una riga TOTAL:

```
$ sudo wtf docker
# DOCKER
  NAME         STATUS       IMAGE   CONTNR     LOGS  WORKING DIR
  myapp_web    running      164MB    267MB   53.8MB  /home/deploy/myapp
  myapp_db     running      276MB     63B    4.02MB  /home/deploy/myapp
  TOTAL                     440MB    267MB   57.8MB
  note: IMAGE total is logical (images share layers); real disk 9.2GB, 1.1GB reclaimable — docker system df; logs cap with max-size; decimal units, like docker
```

Le dimensioni usano unità decimali (1GB = 1000MB), così si allineano con
`docker container ls --size`. L'IMAGE per riga è la dimensione logica completa
dell'immagine (ciò che `docker` chiama dimensione *virtual*). Il totale IMAGE
deduplica per id immagine, quindi un'immagine condivisa da molti container viene
contata una sola volta — non una per ogni container. **Ma** immagini diverse
condividono comunque i layer di base sul disco, quindi anche quella somma
deduplicata sovrastima l'uso reale; la riga della nota mostra il disco reale
deduplicato per layer direttamente da `docker system df`. CONTNR (layer
scrivibile) e LOGS sono per container, quindi quei totali sono esatti. Le
dimensioni dei log richiedono accesso in lettura sotto `/var/lib/docker` —
esegui con `sudo`, altrimenti mostrano `?`.

## Output per gli script: grep, awk, jq

I colori scompaiono automaticamente quando usi una pipe, quindi un semplice `grep`
funziona sempre. Ogni comando ha anche formati leggibili da una macchina — `plain`
(separati da tabulazioni, senza intestazioni) e `json`. Il flag funziona anche prima
del sottocomando:

```bash
wtf -f json disk                         # same as: wtf disk --format json
wtf disk --format plain                  # tab-separated, no headers
wtf disk --format json | jq .            # full JSON

# mounts above 80%:
wtf disk --format json | jq -r '.mounts[] | select(.percent > 80) | .target'

# failed checks only, names column:
wtf audit --format plain | awk -F'\t' '$1 == "fail" {print $2}'

# top directory eating /var, bytes and path:
wtf disk --tree /var --format plain | awk -F'\t' '$1 == "tree" {print $2, $3; exit}'
```

I payload JSON dei comandi di risorsa includono `schema_version`, così i tuoi script
sopravvivono agli aggiornamenti.

## Routine quotidiana e monitoraggio

Un solo comando per il controllo mattutino — audit, cosa è cambiato dall'ultima
esecuzione e la cronologia degli eventi, con un verdetto su una riga in cima:

```bash
wtf daily                       # audit + diff vs yesterday + events
```

Salva uno snapshot a ogni esecuzione, così il `wtf daily` di domani mostra le
differenze. Una riga di crontab per l'uso non presidiato (invia email solo quando
qualcosa non va):

```cron
0 8 * * * wtf daily --format json > /var/log/wtf-daily.json 2>&1 || mail -s "wtf $(hostname)" you@example.com < /var/log/wtf-daily.json
```

I mattoni di base sono disponibili anche separatamente:

```bash
wtf audit --brief               # one line — perfect for MOTD / SSH banner
wtf audit --save                # save a snapshot
wtf diff                        # what changed since the last snapshot
wtf history                     # list saved snapshots

# cron alerting without any monitoring stack:
wtf audit --alert 'mail -s "wtf $WTF_HOST" you@example.com'
wtf audit --alert-on warn --alert 'curl -X POST $SLACK_WEBHOOK -d @-'
```

I codici di uscita sono adatti a CI/cron:

| codice | significato                                      |
|--------|--------------------------------------------------|
| 0      | tutto OK                                          |
| 1      | avvisi con `--strict`, o errori di crontab       |
| 2      | l'audit ha trovato un `[FAIL]`                   |
| 130    | interrotto (Ctrl-C)                              |

## Tutti i sottocomandi

| comando             | cosa fa                                                     |
|---------------------|-------------------------------------------------------------|
| `wtf` / `wtf audit` | checklist verde/giallo/rosso: cosa va bene e cosa no        |
| `wtf problems`      | solo le righe WARN+FAIL                                     |
| `wtf daily`         | controllo mattutino: audit + diff dall'ultima esecuzione + eventi |
| `wtf explain`       | consigli pratici per ogni controllo; `--llm` per inviarli a un LLM |
| `wtf disk`          | utilizzo per mount; `--tree` mostra le directory più grandi |
| `wtf cpu`           | carico, iowait, pressione, principali consumatori di CPU    |
| `wtf mem`           | RAM/swap, OOM kill, principali consumatori di memoria       |
| `wtf net`           | interfacce, gateway, DNS, errori, porte in ascolto          |
| `wtf io`            | tassi di IO per dispositivo, pressione, processi bloccati   |
| `wtf who`           | utenti connessi, accessi recenti, autenticazioni fallite    |
| `wtf temp`          | temperature hardware dai sensori /sys/class/hwmon           |
| `wtf info`          | snapshot su una pagina: tutto quanto sopra in una volta     |
| `wtf top`           | top dei processi mirato: ordina per cpu/rss, filtra utente/nome |
| `wtf ports`         | socket in ascolto con PID/utente/comando proprietario       |
| `wtf port NUM`      | dettaglio di una porta: PID, file eseguibile, working dir   |
| `wtf docker [NAME]` | working dir compose del container + dimensioni image/container/log |
| `wtf service NAME`  | dettaglio di un servizio: stato, riavvii, mem, porte, journal |
| `wtf logs`          | voci recenti ERROR+ del journal raggruppate per servizio    |
| `wtf events`        | cronologia in ordine temporale: riavvii, OOM, unità fallite, … |
| `wtf history`       | elenca gli snapshot di audit salvati (`wtf audit --save` per crearne) |
| `wtf diff`          | confronta lo stato corrente con uno snapshot salvato        |
| `wtf crontab`       | valida tutte le posizioni standard di crontab + i crontab per utente |
| `wtf doctor`        | autodiagnosi: quali strumenti wtftools può effettivamente usare |
| `wtf config`        | mostra la configurazione effettiva / stampa un esempio      |

`wtftools` assorbe e sostituisce
[`checkcrontab`](https://github.com/wachawo/checkcrontab) — lo stesso validatore
di cron ora si trova in `wtf crontab`.

## Opzioni avanzate dell'audit

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

### Controlli integrati

uptime · system state · load average · CPU iowait · PSI cpu/memory/io ·
TCP retransmits · memory · swap · disk (per mount) · inodes ·
read-only mounts · failed systemd units · enabled-but-down services ·
restart loops · network errors · conntrack · journal disk usage · zombies ·
D-state processes · OOM kills · kernel errors · kernel taint · cert expiry ·
open file descriptors · process count · failed auth · time sync ·
pending updates · reboot required · cron daemon · crontab syntax · docker ·
hw temperatures · disk SMART · DNS · HTTP/TCP probes · fail2ban.

## Configurazione

Le soglie e le esclusioni risiedono in un file INI in una di queste posizioni:

- `/etc/wtftools/config.ini`
- `/etc/wtf/config.ini`
- `~/.config/wtftools/config.ini`

Esegui `wtf config --example` per un modello completamente commentato. In sintesi:

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

## Compatibilità

- Python 3.8+
- Linux (le distribuzioni con systemd sono il percorso ideale; lo strumento si
  degrada con grazia quando `systemctl` / `journalctl` / `psutil` mancano)
- Nessun accesso di rete richiesto per la CLI principale
- Rete opzionale: `wtf explain --llm claude/openai`, `wtf doctor --check-updates`

## Dai sorgenti

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
# or test without installing:
python3 wtf.py audit
```

## Licenza

MIT
