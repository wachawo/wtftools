# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> Одна команда, чтобы увидеть, что прямо сейчас происходит с вашим Linux-сервером.

[English](https://github.com/wachawo/wtftools/blob/main/README.md) | [Español](https://github.com/wachawo/wtftools/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/wtftools/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/wtftools/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/wtftools/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/wtftools/blob/main/docs/README_IT.md) | **Русский** | [中文](https://github.com/wachawo/wtftools/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/wtftools/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/wtftools/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/wtftools/blob/main/docs/README_KR.md)

Вы подключаетесь к серверу, и что-то кажется не так. Вместо того чтобы запускать
десяток команд (`htop`, `df -h`, `journalctl`, `systemctl --failed`, …), вы запускаете одну:

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

Зелёный — всё в порядке, жёлтый — стоит взглянуть, красный — нужно чинить. Вот и всё.

## Установка

```bash
pipx install wtftools          # recommended — works on any modern distro
```

Нет `pipx`? Любой из этих способов тоже подойдёт:

```bash
pip install wtftools           # classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

После установки у вас есть команда `wtf`. Попробуйте: `wtf`.

## Команды, которыми вы действительно будете пользоваться

```bash
wtf              # full health check — start here
wtf problems     # show ONLY what is wrong (warnings + failures)
wtf explain      # what to do about each problem, step by step
```

Затем спрашивайте об одном ресурсе за раз, как команды `show` на коммутаторе:

```bash
wtf disk         # is there space? per-mount usage, inodes, read-only
wtf disk --tree  # WHAT is eating the space (largest directories)
wtf cpu          # load, iowait, top CPU consumers
wtf mem          # RAM/swap, OOM kills, top memory consumers
wtf net          # interfaces, IPs, gateway, DNS, listening ports
wtf io           # disk read/write rates, IO-stuck processes
wtf who          # who is logged in, recent logins, failed auth
```

Пример — диск заполняется, найдём виновника:

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

`wtf disk --tree` без указания пути автоматически выбирает самый заполненный раздел.

Изучаете Linux? Добавьте `--show-commands` к любой команде ресурса, и она также
выведет классические команды, которые заменяет, чтобы вы могли запустить их сами:

```
$ wtf cpu --show-commands
  ...
  equivalent commands:
    $ uptime
    $ top -bn1 | head
    $ ps aux --sort=-%cpu | head
```

## Когда что-то сломалось

```bash
wtf problems -v                 # every problem, with detail
wtf events --since 6            # timeline: reboots, OOM kills, failed units
wtf service nginx               # one service: state, restarts, ports, journal
wtf logs --since '2 hours ago'  # recent ERROR+ journal entries by service
wtf explain                     # actionable advice per finding
wtf explain --llm ollama        # or let a local LLM summarize it
```

## Вывод для скриптов: grep, awk, jq

Цвета автоматически исчезают при перенаправлении вывода, поэтому обычный `grep` всегда работает.
У каждой команды также есть машиночитаемые форматы — `plain` (с разделением табуляцией,
без заголовков) и `json`. Флаг работает и перед подкомандой:

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

JSON-данные команд ресурсов содержат `schema_version`, чтобы ваши
скрипты переживали обновления.

## Ежедневный режим и мониторинг

Одна команда для утренней проверки — аудит, что изменилось с последнего запуска
и хронология событий, с однострочным вердиктом сверху:

```bash
wtf daily                       # audit + diff vs yesterday + events
```

Она сохраняет снимок при каждом запуске, поэтому завтрашний `wtf daily` покажет изменения.
Строка crontab для автоматического использования (отправляет почту только когда что-то не так):

```cron
0 8 * * * wtf daily --format json > /var/log/wtf-daily.json 2>&1 || mail -s "wtf $(hostname)" you@example.com < /var/log/wtf-daily.json
```

Составные части также доступны по отдельности:

```bash
wtf audit --brief               # one line — perfect for MOTD / SSH banner
wtf audit --save                # save a snapshot
wtf diff                        # what changed since the last snapshot
wtf history                     # list saved snapshots

# cron alerting without any monitoring stack:
wtf audit --alert 'mail -s "wtf $WTF_HOST" you@example.com'
wtf audit --alert-on warn --alert 'curl -X POST $SLACK_WEBHOOK -d @-'
```

Коды завершения удобны для CI/cron:

| код  | значение                                         |
|------|--------------------------------------------------|
| 0    | всё в порядке                                    |
| 1    | предупреждения с `--strict` или ошибки crontab   |
| 2    | аудит обнаружил `[FAIL]`                          |
| 130  | прервано (Ctrl-C)                                |

## Все подкоманды

| команда             | что она делает                                              |
|---------------------|-------------------------------------------------------------|
| `wtf` / `wtf audit` | чек-лист зелёный/жёлтый/красный: что в порядке, а что нет    |
| `wtf problems`      | только строки WARN+FAIL                                      |
| `wtf daily`         | утренняя проверка: аудит + изменения с прошлого запуска + события |
| `wtf explain`       | практические советы по каждой проверке; `--llm` для передачи в LLM |
| `wtf disk`          | использование по разделам; `--tree` показывает крупнейшие каталоги |
| `wtf cpu`           | нагрузка, iowait, давление, главные потребители CPU         |
| `wtf mem`           | RAM/swap, OOM-убийства, главные потребители памяти          |
| `wtf net`           | интерфейсы, шлюз, DNS, ошибки, прослушиваемые порты         |
| `wtf io`            | скорости IO по устройствам, давление, зависшие процессы     |
| `wtf who`           | вошедшие пользователи, недавние входы, неудачная аутентификация |
| `wtf info`          | одностраничный снимок: всё вышеперечисленное сразу          |
| `wtf top`           | фокусированный топ процессов: сортировка по cpu/rss, фильтр по пользователю/имени |
| `wtf ports`         | прослушиваемые сокеты с владеющим PID/пользователем/командой |
| `wtf service NAME`  | детальный разбор одной службы: состояние, перезапуски, память, порты, журнал |
| `wtf logs`          | недавние записи журнала уровня ERROR+, сгруппированные по службам |
| `wtf events`        | хронологическая лента: перезагрузки, OOM, упавшие юниты, …  |
| `wtf history`       | список сохранённых снимков аудита (`wtf audit --save` для создания) |
| `wtf diff`          | сравнение текущего состояния с сохранённым снимком          |
| `wtf crontab`       | проверка всех стандартных расположений crontab + crontab по пользователям |
| `wtf doctor`        | самодиагностика: какие инструменты wtftools реально может использовать |
| `wtf config`        | показать действующую конфигурацию / вывести пример          |

`wtftools` поглощает и заменяет
[`checkcrontab`](https://github.com/wachawo/checkcrontab) — тот же валидатор
cron теперь живёт в `wtf crontab`.

## Расширенные опции аудита

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

### Встроенные проверки

uptime · system state · load average · CPU iowait · PSI cpu/memory/io ·
TCP retransmits · memory · swap · disk (per mount) · inodes ·
read-only mounts · failed systemd units · enabled-but-down services ·
restart loops · network errors · conntrack · journal disk usage · zombies ·
D-state processes · OOM kills · kernel errors · kernel taint · cert expiry ·
open file descriptors · process count · failed auth · time sync ·
pending updates · reboot required · cron daemon · crontab syntax · docker ·
hw temperatures · disk SMART · DNS · HTTP/TCP probes · fail2ban.

## Конфигурация

Пороги и исключения хранятся в INI-файле в любом из расположений:

- `/etc/wtftools/config.ini`
- `/etc/wtf/config.ini`
- `~/.config/wtftools/config.ini`

Запустите `wtf config --example` для получения полностью прокомментированного шаблона. Основное:

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

## Совместимость

- Python 3.8+
- Linux (дистрибутивы с systemd — основной сценарий; инструмент корректно
  снижает функциональность, когда `systemctl` / `journalctl` / `psutil` отсутствуют)
- Для базового CLI доступ к сети не требуется
- Опциональная сеть: `wtf explain --llm claude/openai`, `wtf doctor --check-updates`

## Из исходного кода

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
# or test without installing:
python3 wtf.py audit
```

## Лицензия

MIT
