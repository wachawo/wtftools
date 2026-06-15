# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> Une seule commande pour voir ce qui se passe sur votre serveur Linux en ce moment même.

[English](https://github.com/wachawo/wtftools/blob/main/README.md) | [Español](https://github.com/wachawo/wtftools/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/wtftools/blob/main/docs/README_PT.md) | **Français** | [Deutsch](https://github.com/wachawo/wtftools/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/wtftools/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/wtftools/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/wtftools/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/wtftools/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/wtftools/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/wtftools/blob/main/docs/README_KR.md)

Vous vous connectez à un serveur et quelque chose vous semble anormal. Au lieu de
lancer dix commandes (`htop`, `df -h`, `journalctl`, `systemctl --failed`, …), vous n'en lancez qu'une :

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

Le vert est bon, le jaune mérite un coup d'œil, le rouge doit être corrigé. C'est tout.

## Installation

```bash
pipx install wtftools          # recommended — works on any modern distro
```

Pas de `pipx` ? L'une de ces commandes fonctionne tout aussi bien :

```bash
pip install wtftools           # classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

Après l'installation, vous disposez de la commande `wtf`. Essayez-la : `wtf`.

## Les commandes que vous utiliserez réellement

```bash
wtf              # full health check — start here
wtf problems     # show ONLY what is wrong (warnings + failures)
wtf explain      # what to do about each problem, step by step
```

Ensuite, interrogez une ressource à la fois, comme les commandes `show` sur un commutateur :

```bash
wtf disk         # is there space? per-mount usage, inodes, read-only
wtf disk --tree  # WHAT is eating the space (largest directories)
wtf cpu          # load, iowait, top CPU consumers
wtf mem          # RAM/swap, OOM kills, top memory consumers
wtf net          # interfaces, IPs, gateway, DNS, listening ports
wtf io           # disk read/write rates, IO-stuck processes
wtf who          # who is logged in, recent logins, failed auth
```

Exemple — le disque se remplit, trouvez le coupable :

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

`wtf disk --tree` sans chemin choisit automatiquement le point de montage le plus plein.

Vous apprenez Linux ? Ajoutez `--show-commands` à n'importe quelle commande de ressource et elle
affiche aussi les commandes classiques qu'elle remplace, afin que vous puissiez les lancer vous-même :

```
$ wtf cpu --show-commands
  ...
  equivalent commands:
    $ uptime
    $ top -bn1 | head
    $ ps aux --sort=-%cpu | head
```

## Quand quelque chose est cassé

```bash
wtf problems -v                 # every problem, with detail
wtf events --since 6            # timeline: reboots, OOM kills, failed units
wtf service nginx               # one service: state, restarts, ports, journal
wtf logs --since '2 hours ago'  # recent ERROR+ journal entries by service
wtf explain                     # actionable advice per finding
wtf explain --llm ollama        # or let a local LLM summarize it
```

## Sortie pour les scripts : grep, awk, jq

Les couleurs disparaissent automatiquement lorsque vous redirigez la sortie, donc un simple `grep` fonctionne toujours.
Chaque commande propose aussi des formats lisibles par la machine — `plain` (séparé par des tabulations,
sans en-têtes) et `json`. Le drapeau fonctionne également avant la sous-commande :

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

Les charges utiles JSON des commandes de ressource transportent `schema_version` afin que vos
scripts survivent aux mises à niveau.

## Routine quotidienne et surveillance

Une seule commande pour le contrôle du matin — audit, ce qui a changé depuis la dernière exécution
et la chronologie des événements, avec un verdict d'une ligne en haut :

```bash
wtf daily                       # audit + diff vs yesterday + events
```

Elle enregistre un instantané à chaque exécution, de sorte que le `wtf daily` de demain affiche le différentiel.
Une ligne crontab pour une utilisation sans surveillance (envoie un courriel uniquement en cas de problème) :

```cron
0 8 * * * wtf daily --format json > /var/log/wtf-daily.json 2>&1 || mail -s "wtf $(hostname)" you@example.com < /var/log/wtf-daily.json
```

Les briques de base sont également disponibles séparément :

```bash
wtf audit --brief               # one line — perfect for MOTD / SSH banner
wtf audit --save                # save a snapshot
wtf diff                        # what changed since the last snapshot
wtf history                     # list saved snapshots

# cron alerting without any monitoring stack:
wtf audit --alert 'mail -s "wtf $WTF_HOST" you@example.com'
wtf audit --alert-on warn --alert 'curl -X POST $SLACK_WEBHOOK -d @-'
```

Les codes de sortie sont adaptés à la CI et au cron :

| code | signification                                    |
|------|--------------------------------------------------|
| 0    | tout va bien                                     |
| 1    | avertissements avec `--strict`, ou erreurs crontab |
| 2    | l'audit a trouvé un `[FAIL]`                     |
| 130  | interrompu (Ctrl-C)                              |

## Toutes les sous-commandes

| commande            | ce qu'elle fait                                             |
|---------------------|-------------------------------------------------------------|
| `wtf` / `wtf audit` | liste de contrôle vert/jaune/rouge : ce qui va et ce qui ne va pas |
| `wtf problems`      | uniquement les lignes WARN+FAIL                            |
| `wtf daily`         | contrôle du matin : audit + diff vs dernière exécution + événements |
| `wtf explain`       | conseils actionnables par vérification ; `--llm` pour transmettre à un LLM |
| `wtf disk`          | usage par montage ; `--tree` affiche les plus grands répertoires |
| `wtf cpu`           | charge, iowait, pression, plus gros consommateurs de CPU   |
| `wtf mem`           | RAM/swap, kills OOM, plus gros consommateurs de mémoire    |
| `wtf net`           | interfaces, passerelle, DNS, erreurs, ports en écoute      |
| `wtf io`            | débits d'E/S par périphérique, pression, processus bloqués |
| `wtf who`           | utilisateurs connectés, connexions récentes, authentifications échouées |
| `wtf info`          | instantané d'une page : tout ce qui précède en une fois    |
| `wtf top`           | top de processus ciblé : tri par cpu/rss, filtre utilisateur/nom |
| `wtf ports`         | sockets en écoute avec PID/utilisateur/commande propriétaire |
| `wtf service NAME`  | analyse détaillée d'un service : état, redémarrages, mémoire, ports, journal |
| `wtf logs`          | entrées de journal ERROR+ récentes groupées par service    |
| `wtf events`        | chronologie : redémarrages, OOM, unités en échec, …        |
| `wtf history`       | liste des instantanés d'audit enregistrés (`wtf audit --save` pour en créer) |
| `wtf diff`          | compare l'état actuel à un instantané enregistré           |
| `wtf crontab`       | valide tous les emplacements crontab standard + les crontabs par utilisateur |
| `wtf doctor`        | autodiagnostic : quels outils wtftools peut réellement utiliser |
| `wtf config`        | affiche la configuration effective / imprime un exemple    |

`wtftools` absorbe et remplace
[`checkcrontab`](https://github.com/wachawo/checkcrontab) — le même validateur de cron
réside désormais dans `wtf crontab`.

## Options d'audit avancées

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

### Vérifications intégrées

uptime · system state · load average · CPU iowait · PSI cpu/memory/io ·
TCP retransmits · memory · swap · disk (per mount) · inodes ·
read-only mounts · failed systemd units · enabled-but-down services ·
restart loops · network errors · conntrack · journal disk usage · zombies ·
D-state processes · OOM kills · kernel errors · kernel taint · cert expiry ·
open file descriptors · process count · failed auth · time sync ·
pending updates · reboot required · cron daemon · crontab syntax · docker ·
hw temperatures · disk SMART · DNS · HTTP/TCP probes · fail2ban.

## Configuration

Les seuils et les exclusions résident dans un fichier INI situé à l'un de ces emplacements :

- `/etc/wtftools/config.ini`
- `/etc/wtf/config.ini`
- `~/.config/wtftools/config.ini`

Lancez `wtf config --example` pour obtenir un modèle entièrement commenté. Les grandes lignes :

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

## Compatibilité

- Python 3.8+
- Linux (les distributions systemd sont la voie idéale ; l'outil se dégrade
  gracieusement lorsque `systemctl` / `journalctl` / `psutil` sont absents)
- Aucun accès réseau requis pour la CLI de base
- Réseau optionnel : `wtf explain --llm claude/openai`, `wtf doctor --check-updates`

## Depuis les sources

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
# or test without installing:
python3 wtf.py audit
```

## Licence

MIT
