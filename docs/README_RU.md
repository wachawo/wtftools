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

Автодополнение по Tab (необязательно) — добавьте одну строку в rc-файл вашей оболочки и нажмите `<Tab>`:

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

Запустите `wtf completion` без аргумента, чтобы увидеть полную инструкцию.

## Команды, которыми вы действительно будете пользоваться

```bash
wtf              # full health check — start here
wtf problems     # show ONLY what is wrong (warnings + failures)
wtf explain      # what to do about each problem, step by step
```

Затем спрашивайте об одном ресурсе за раз, как команды `show` на коммутаторе:

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

`wtf disk` без пути — это обзор разделов: полный путь, использовано/всего, процент
и полоса заполнения:

```
$ wtf disk
# DISK
  /            1.4TB / 1.8TB   79%  [████████████████····]  ext4
  /boot      216.4MB / 1.9GB   11%  [██··················]  ext4
  /mnt/Data    5.3TB / 13.9TB  38%  [████████············]  ext4
```

Пример — диск заполняется, найдём виновника. `wtf disk <path>` выводит папки
непосредственно внутри него, начиная с самых больших (`path/  size  % of root  depth`):

```
$ wtf disk /var
# DISK USAGE /var
  lib/      15.0GB  75%  0
  log/       3.1GB  16%  0
  cache/     1.2GB   6%  0
```

Добавьте `--tree`, чтобы спуститься в самую большую папку, уровень за уровнем (`--depth`,
по умолчанию 3); `--tree N` раскрывает N крупнейших на каждом уровне. Завершающее число —
это глубина:

```
$ wtf disk / --tree
# DISK USAGE /
  home/                 1021.0GB  70%  0
  home/wachawo/         1021.0GB  70%  1
  home/wachawo/myApps/   429.7GB  30%  2
  usr/                   207.9GB  14%  0
  var/                   206.5GB  14%  0
```

`wtf disk --tree` без пути спускается по самому заполненному разделу. Запускайте с `sudo`,
чтобы читать папки, принадлежащие root. Обзор разделов `# DISK` (без пути) остаётся без изменений.

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

### Кто занимает порт?

`wtf port <N>` (или `wtf ports <N>`) показывает, какой процесс держит порт — PID,
точный исполняемый файл за ним (через `lsof` + `/proc`) и каталог, из которого он
запущен:

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

Запустите с `sudo`, чтобы увидеть процессы, принадлежащие другим пользователям.

### Откуда был запущен этот контейнер?

`wtf docker <name>` отвечает на вопрос «в какой папке выполнялся `docker compose up`?»
прямо из меток контейнера — а также сколько диска он съедает (слои образа,
записываемый слой контейнера и json-лог):

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

`wtf docker` без имени выводит каждый запущенный контейнер со столбцами размеров
и рабочим каталогом, плюс строку TOTAL:

```
$ sudo wtf docker
# DOCKER
  NAME         STATUS       IMAGE   CONTNR     LOGS  WORKING DIR
  myapp_web    running      164MB    267MB   53.8MB  /home/deploy/myapp
  myapp_db     running      276MB     63B    4.02MB  /home/deploy/myapp
  TOTAL                     440MB    267MB   57.8MB
  note: IMAGE total is logical (images share layers); real disk 9.2GB, 1.1GB reclaimable — docker system df; logs cap with max-size; decimal units, like docker
```

Размеры используют десятичные единицы (1GB = 1000MB), поэтому они совпадают с
`docker container ls --size`. Значение IMAGE в строке — полный логический размер
образа (то, что `docker` называет *virtual* size). Итог по IMAGE дедуплицирует по id
образа, поэтому один образ, общий для многих контейнеров, считается один раз — а не
по разу на контейнер. **Но** разные образы всё равно разделяют базовые слои на диске,
поэтому даже эта дедуплицированная сумма завышает реальное использование; строка note
показывает истинный объём диска с дедупликацией слоёв прямо из `docker system df`.
CONTNR (записываемый слой) и LOGS считаются по каждому контейнеру, поэтому эти итоги
точны. Размеры логов требуют доступа на чтение в `/var/lib/docker` — запускайте с
`sudo`, иначе они показывают `?`.

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
wtf disk /var --format plain | awk -F'\t' 'NR==1 {print $3, $1}'   # biggest folder: path, bytes
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
| `wtf disk [PATH]`   | обзор разделов; с PATH — крупнейшие папки; `--tree` раскрывает |
| `wtf cpu`           | нагрузка, iowait, давление, главные потребители CPU         |
| `wtf mem`           | RAM/swap, OOM-убийства, главные потребители памяти          |
| `wtf net`           | интерфейсы, шлюз, DNS, ошибки, прослушиваемые порты         |
| `wtf io`            | скорости IO по устройствам, давление, зависшие процессы     |
| `wtf who`           | вошедшие пользователи, недавние входы, неудачная аутентификация |
| `wtf temp`          | температуры оборудования с датчиков /sys/class/hwmon         |
| `wtf info`          | одностраничный снимок: всё вышеперечисленное сразу          |
| `wtf top`           | фокусированный топ процессов: сортировка по cpu/rss, фильтр по пользователю/имени |
| `wtf ports`         | прослушиваемые сокеты с владеющим PID/пользователем/командой |
| `wtf port NUM`      | детальный разбор одного порта: PID, исполняемый файл, рабочий каталог |
| `wtf docker [NAME]` | рабочий каталог compose контейнера + размеры образа/контейнера/логов |
| `wtf service NAME`  | детальный разбор одной службы: состояние, перезапуски, память, порты, журнал |
| `wtf logs`          | недавние записи журнала уровня ERROR+, сгруппированные по службам |
| `wtf events`        | хронологическая лента: перезагрузки, OOM, упавшие юниты, …  |
| `wtf history`       | список сохранённых снимков аудита (`wtf audit --save` для создания) |
| `wtf diff`          | сравнение текущего состояния с сохранённым снимком          |
| `wtf crontab`       | проверка всех стандартных расположений crontab + crontab по пользователям |
| `wtf doctor`        | самодиагностика: какие инструменты wtftools реально может использовать |
| `wtf config`        | показать действующую конфигурацию / вывести пример          |
| `wtf completion`    | вывести скрипт автодополнения `<Tab>` для bash/zsh (или справку по настройке) |

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
