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
[FAIL] failed systemd units    1 failed unit(s)

  Summary: 12 ok · 1 warn · 1 fail · 2 skip
```

Il verde va bene, il giallo richiede un'occhiata, il rosso va sistemato.
`wtftools` è una **CLI di sola lettura e senza dipendenze** (solo libreria
standard di Python; `psutil` opzionale) che trasforma un mucchio di comandi
diagnostici in un'unica risposta leggibile — e in una leggibile da una macchina
quando la usi in pipe.

## Cosa può fare

- **Audit dello stato di salute** — oltre 40 controlli (disco, memoria, swap,
  carico, PSI, OOM kill, unità fallite, scadenza dei certificati, SMART,
  temperature, DNS, …) come una checklist verde / giallo / rosso.
- **Viste per risorsa** — chiedi una cosa alla volta, come i comandi `show` su
  uno switch: `wtf disk`, `wtf cpu`, `wtf mem`, `wtf net`, `wtf docker`, …
- **Triage degli incidenti** — `wtf problems`, `wtf events`, `wtf logs`,
  `wtf services <unit>`, `wtf explain` (opzionalmente tramite un LLM locale o ospitato).
- **Tendenze e avvisi** — `wtf daily`, snapshot + `wtf diff`, avvisi via cron —
  senza alcuno stack di monitoraggio.
- **Adatto agli script** — ogni comando ha output `plain` (separato da tabulazioni)
  e `json` che porta uno `schema_version`, per grep / awk / jq.
- **Adatto ai principianti** — `--show-commands` stampa i comandi classici che
  ogni vista sostituisce, così puoi impararli a mano.

## Installazione

```bash
pipx install wtftools          # recommended — works on any modern distro
pip install wtftools           # or classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

Dopo l'installazione hai il comando `wtf`. Abilita il completamento con `<Tab>`
aggiungendo una riga al file rc della tua shell:

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

Sei nuovo qui? Inizia con il [quickstart di 5 minuti](docs/QUICKSTART.md).

## Comandi

Esegui `wtf <command> --help` per i flag. Ogni comando rimanda alla sua pagina
di riferimento con esempi.

### Salute e monitoraggio — [docs/AUDIT.md](docs/AUDIT.md)

| command | cosa fa |
|---------|--------------|
| [`wtf` / `wtf audit`](docs/AUDIT.md#wtf-audit) | checklist verde/giallo/rosso di cosa va bene e cosa no |
| [`wtf problems`](docs/AUDIT.md#wtf-problems) | solo le righe WARN+FAIL |
| [`wtf daily`](docs/AUDIT.md#wtf-daily) | controllo mattutino: audit + diff dall'ultima esecuzione + eventi |
| [`wtf explain`](docs/AUDIT.md#wtf-explain) | consigli pratici per ogni controllo; `--llm` per inviarli a un LLM |
| [`wtf events`](docs/AUDIT.md#wtf-events) | cronologia: riavvii, OOM kill, unità fallite, … |
| [`wtf logs`](docs/AUDIT.md#wtf-logs) | voci recenti ERROR+ del journal raggruppate per servizio |
| [`wtf services`](docs/AUDIT.md#wtf-services) | dettaglio di una unità: stato, riavvii, porte, journal |
| [`wtf diff`](docs/AUDIT.md#wtf-diff) | confronta lo stato corrente con uno snapshot salvato |
| [`wtf history`](docs/AUDIT.md#wtf-history) | elenca gli snapshot di audit salvati |
| [`wtf crontab`](docs/AUDIT.md#wtf-crontab) | valida il crontab di sistema + i crontab per utente |
| [`wtf doctor`](docs/AUDIT.md#wtf-doctor) | autodiagnosi: quali strumenti/file wtf può usare |

### Viste delle risorse — [docs/RESOURCES.md](docs/RESOURCES.md)

| command | cosa fa |
|---------|--------------|
| [`wtf disk [PATH]`](docs/RESOURCES.md#wtf-disk) | panoramica dei mount; con un PATH, le cartelle più grandi; `--tree` analizza in profondità |
| [`wtf cpu`](docs/RESOURCES.md#wtf-cpu) | carico, iowait, pressione, principali consumatori di CPU |
| [`wtf mem`](docs/RESOURCES.md#wtf-mem) | RAM/swap, OOM kill, principali consumatori di memoria |
| [`wtf net`](docs/RESOURCES.md#wtf-net) | interfacce, gateway, DNS, errori, porte in ascolto |
| [`wtf io`](docs/RESOURCES.md#wtf-io) | tassi di IO per dispositivo, pressione, processi bloccati |
| [`wtf who`](docs/RESOURCES.md#wtf-who) | utenti connessi, accessi recenti, autenticazioni fallite |
| [`wtf temp`](docs/RESOURCES.md#wtf-temp) | temperature hardware da /sys/class/hwmon |
| [`wtf info`](docs/RESOURCES.md#wtf-info) | snapshot su una pagina: tutto quanto sopra in una volta |
| [`wtf top`](docs/RESOURCES.md#wtf-top) | top dei processi mirato: ordina per cpu/rss, filtra per utente/nome |
| [`wtf ports` / `wtf port N`](docs/RESOURCES.md#wtf-ports) | socket in ascolto; dettaglio di una porta fino a PID, exe, cwd |
| [`wtf docker [NAME]`](docs/RESOURCES.md#wtf-docker) | dir compose del container + dimensioni image/container/log |

### Output e configurazione

| command | cosa fa |
|---------|--------------|
| [`wtf config`](docs/CONFIG.md#wtf-config) | mostra la configurazione effettiva / stampa un esempio commentato |
| [`wtf completion`](#install) | stampa uno script di completamento `<Tab>` per bash/zsh |
| [machine output](docs/OUTPUT.md) | formati `plain`/`json` e un ricettario grep·awk·jq |

`wtftools` assorbe e sostituisce
[`checkcrontab`](https://github.com/wachawo/checkcrontab) — lo stesso validatore
di cron ora si trova in `wtf crontab`.

## Documentazione

- [QUICKSTART.md](docs/QUICKSTART.md) — onboarding di 5 minuti e un cheat sheet
- [AUDIT.md](docs/AUDIT.md) — controlli di salute, monitoraggio, codici di uscita, l'elenco completo dei controlli
- [RESOURCES.md](docs/RESOURCES.md) — viste per risorsa con esempi
- [OUTPUT.md](docs/OUTPUT.md) — formati `plain`/`json` e il ricettario per gli script
- [CONFIG.md](docs/CONFIG.md) — file di configurazione, soglie, esclusione dei controlli

## Compatibilità

- Python 3.8+
- Linux (le distribuzioni con systemd sono il percorso ideale; lo strumento si
  degrada con grazia quando `systemctl` / `journalctl` / `psutil` mancano)
- Nessun accesso di rete richiesto per la CLI principale; rete opzionale solo per
  `wtf explain --llm …` e `wtf doctor --check-updates`

## Dai sorgenti

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
python3 wtf.py audit       # or run it without installing
```

## Licenza

MIT
