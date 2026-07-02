# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> `wtf` — une seule commande en lecture seule qui vous dit ce qui ne va pas sur une machine Linux en ce moment même.

Aucun agent. Aucun démon. Aucune configuration. Aucun appel réseau. Aucune dépendance
(bibliothèque standard Python uniquement ; `psutil` optionnel). Sans danger à exécuter
en production via SSH — elle ne fait que *lire*. Essayez-la en deux secondes, rien à
installer : `pipx run wtftools`

[English](https://github.com/wachawo/wtftools/blob/main/README.md) | [Español](https://github.com/wachawo/wtftools/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/wtftools/blob/main/docs/README_PT.md) | **Français** | [Deutsch](https://github.com/wachawo/wtftools/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/wtftools/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/wtftools/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/wtftools/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/wtftools/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/wtftools/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/wtftools/blob/main/docs/README_KR.md)

Au lieu de lancer dix commandes (`htop`, `df -h`, `journalctl`,
`systemctl --failed`, `ss`, `dmesg`, …), vous n'en lancez qu'une :

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

Le vert est bon, le jaune mérite un coup d'œil, le rouge doit être corrigé. Deux façons dont les administrateurs l'utilisent au quotidien :

- **Incident** — quelque chose cloche → `wtf` → une liste de contrôle vert/jaune/rouge
  au lieu de dix commandes éparpillées.
- **Au quotidien** — `wtf daily` comme vérification matinale, `wtf` dans votre bannière
  de connexion MOTD, `wtf audit --alert …` depuis cron. Sans pile de supervision requise.

## Ce qu'il sait faire

- **Audit de santé** — plus de 35 vérifications (disque, mémoire, swap, charge, PSI, kills OOM,
  unités en échec, expiration de certificats, SMART, températures, DNS, …) sous forme de
  liste de contrôle vert / jaune / rouge.
- **Vues par ressource** — interrogez une chose à la fois, comme les commandes `show`
  sur un commutateur : `wtf disk`, `wtf cpu`, `wtf mem`, `wtf net`, `wtf docker`, …
- **Triage d'incidents** — `wtf problems`, `wtf events`, `wtf logs`,
  `wtf services <unit>`, `wtf explain` (éventuellement via un LLM local ou hébergé).
- **Tendances et alertes** — `wtf daily`, instantanés + `wtf diff`, alertes cron —
  aucune stack de surveillance requise.
- **Scriptable** — `-f json` sur chaque commande et `-f plain` (séparé par des tabulations) sur les
  vues de ressources et d'audit ; le JSON porte un `schema_version` pour que les scripts survivent aux mises à jour — pour grep / awk / jq.
- **Accessible aux débutants** — `--show-commands` affiche les commandes classiques que chaque
  vue remplace, afin que vous puissiez les apprendre à la main.

## Install

```bash
pipx install wtftools          # recommended — works on any modern distro
pip install wtftools           # or classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i python3-wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

Après l'installation, vous disposez de la commande `wtf`. Activez la complétion par `<Tab>`
en ajoutant une ligne au fichier rc de votre shell :

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

Nouveau ici ? Commencez par le [démarrage rapide en 5 minutes](QUICKSTART.md).

## Commandes

Lancez `wtf <command> --help` pour les drapeaux. Chaque commande renvoie vers sa page de
référence avec des exemples.

### Santé et surveillance — [docs/AUDIT.md](AUDIT.md)

| command | ce qu'elle fait |
|---------|--------------|
| [`wtf` / `wtf audit`](AUDIT.md#wtf-audit) | liste de contrôle vert/jaune/rouge de ce qui va et de ce qui ne va pas |
| [`wtf problems`](AUDIT.md#wtf-problems) | uniquement les lignes WARN+FAIL |
| [`wtf daily`](AUDIT.md#wtf-daily) | contrôle du matin : audit + diff vs dernière exécution + événements |
| [`wtf explain`](AUDIT.md#wtf-explain) | conseils actionnables par constat ; `--llm` pour transmettre à un LLM |
| [`wtf events`](AUDIT.md#wtf-events) | chronologie : redémarrages, kills OOM, unités en échec, … |
| [`wtf logs`](AUDIT.md#wtf-logs) | entrées de journal ERROR+ récentes groupées par service |
| [`wtf services`](AUDIT.md#wtf-services) | analyse détaillée d'une unité : état, redémarrages, ports, journal |
| [`wtf diff`](AUDIT.md#wtf-diff) | compare l'état actuel à un instantané enregistré |
| [`wtf history`](AUDIT.md#wtf-history) | liste des instantanés d'audit enregistrés |
| [`wtf crontab`](AUDIT.md#wtf-crontab) | valide les crontabs système + par utilisateur |
| [`wtf doctor`](AUDIT.md#wtf-doctor) | autodiagnostic : quels outils/fichiers wtf peut utiliser |

### Vues par ressource — [docs/RESOURCES.md](RESOURCES.md)

| command | ce qu'elle fait |
|---------|--------------|
| [`wtf disk [PATH]`](RESOURCES.md#wtf-disk) | vue d'ensemble des montages ; avec un PATH, les plus grands dossiers ; `--tree` explore |
| [`wtf cpu`](RESOURCES.md#wtf-cpu) | charge, iowait, pression, plus gros consommateurs de CPU |
| [`wtf mem`](RESOURCES.md#wtf-mem) | RAM/swap, kills OOM, plus gros consommateurs de mémoire |
| [`wtf net`](RESOURCES.md#wtf-net) | interfaces, passerelle, DNS, erreurs, ports en écoute |
| [`wtf io`](RESOURCES.md#wtf-io) | débits d'E/S par périphérique, pression, processus bloqués |
| [`wtf who`](RESOURCES.md#wtf-who) | utilisateurs connectés, connexions récentes, authentifications échouées |
| [`wtf temp`](RESOURCES.md#wtf-temp) | températures matérielles depuis /sys/class/hwmon |
| [`wtf info`](RESOURCES.md#wtf-info) | instantané d'une page : tout ce qui précède en une fois |
| [`wtf top`](RESOURCES.md#wtf-top) | top de processus ciblé : tri par cpu/rss, filtre par utilisateur/nom |
| [`wtf ports` / `wtf port N`](RESOURCES.md#wtf-ports) | sockets en écoute ; analyse un port jusqu'au PID, exe, cwd |
| [`wtf docker [NAME]`](RESOURCES.md#wtf-docker) | répertoire compose du conteneur + tailles image/conteneur/journal |

### Sortie et configuration

| command | ce qu'elle fait |
|---------|--------------|
| [`wtf config`](CONFIG.md#wtf-config) | affiche la configuration effective / imprime un exemple commenté |
| [`wtf completion`](#install) | imprime un script de complétion par `<Tab>` bash/zsh |
| [machine output](OUTPUT.md) | formats `plain`/`json` et un guide pratique grep·awk·jq |

`wtftools` absorbe et remplace
[`checkcrontab`](https://github.com/wachawo/checkcrontab) — le même validateur de cron
réside désormais dans `wtf crontab`.

## Documentation

- [QUICKSTART.md](QUICKSTART.md) — prise en main en 5 minutes et aide-mémoire
- [AUDIT.md](AUDIT.md) — vérifications de santé, surveillance, codes de sortie, la liste complète des vérifications
- [RESOURCES.md](RESOURCES.md) — vues par ressource avec exemples
- [OUTPUT.md](OUTPUT.md) — formats `plain`/`json` et le guide pratique de scripting
- [CONFIG.md](CONFIG.md) — fichier de configuration, seuils, ignorer des vérifications
- [ROADMAP.md](ROADMAP.md) — ce qui est prévu et ce qui est hors périmètre

## Compatibilité

- Python 3.9+
- Linux (les distributions systemd sont la voie idéale ; l'outil se dégrade
  gracieusement lorsque `systemctl` / `journalctl` / `psutil` sont absents)
- Aucun accès réseau requis pour la CLI de base ; réseau optionnel uniquement pour
  `wtf explain --llm …` et `wtf doctor --check-updates`

## Depuis les sources

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
python3 wtf.py audit       # or run it without installing
```

## Licence

MIT
