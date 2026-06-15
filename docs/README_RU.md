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
[FAIL] failed systemd units    1 failed unit(s)

  Summary: 12 ok · 1 warn · 1 fail · 2 skip
```

Зелёный — всё в порядке, жёлтый — стоит взглянуть, красный — нужно чинить. `wtftools` —
это **CLI только для чтения, без зависимостей** (только стандартная библиотека Python;
`psutil` опционально), который превращает кучу диагностических команд в один читаемый
ответ — и в машиночитаемый, когда вы перенаправляете вывод.

## Что он умеет

- **Аудит здоровья** — 40+ проверок (диск, память, swap, нагрузка, PSI, OOM-убийства,
  упавшие юниты, истечение сертификатов, SMART, температуры, DNS, …) в виде
  зелёного / жёлтого / красного чек-листа.
- **Просмотр по ресурсам** — спрашивайте об одном за раз, как команды `show`
  на коммутаторе: `wtf disk`, `wtf cpu`, `wtf mem`, `wtf net`, `wtf docker`, …
- **Разбор инцидентов** — `wtf problems`, `wtf events`, `wtf logs`,
  `wtf services <unit>`, `wtf explain` (опционально через локальную или облачную LLM).
- **Тренды и оповещения** — `wtf daily`, снимки + `wtf diff`, cron-оповещения —
  без всякого стека мониторинга.
- **Для скриптов** — у каждой команды есть вывод `plain` (с разделением табуляцией)
  и `json` с полем `schema_version`, для grep / awk / jq.
- **Дружелюбен к новичкам** — `--show-commands` печатает классические команды,
  которые заменяет каждый просмотр, чтобы вы могли освоить их вручную.

## Установка

```bash
pipx install wtftools          # recommended — works on any modern distro
pip install wtftools           # or classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

После установки у вас есть команда `wtf`. Включите автодополнение по `<Tab>`,
добавив одну строку в rc-файл вашей оболочки:

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

Впервые здесь? Начните с [5-минутного быстрого старта](docs/QUICKSTART.md).

## Команды

Запустите `wtf <command> --help` для просмотра флагов. Каждая команда ссылается
на свою справочную страницу с примерами.

### Здоровье и мониторинг — [docs/AUDIT.md](docs/AUDIT.md)

| command | что она делает |
|---------|--------------|
| [`wtf` / `wtf audit`](docs/AUDIT.md#wtf-audit) | чек-лист зелёный/жёлтый/красный: что в порядке, а что нет |
| [`wtf problems`](docs/AUDIT.md#wtf-problems) | только строки WARN+FAIL |
| [`wtf daily`](docs/AUDIT.md#wtf-daily) | утренняя проверка: аудит + изменения с прошлого запуска + события |
| [`wtf explain`](docs/AUDIT.md#wtf-explain) | практические советы по каждой проверке; `--llm` для передачи в LLM |
| [`wtf events`](docs/AUDIT.md#wtf-events) | хронология: перезагрузки, OOM-убийства, упавшие юниты, … |
| [`wtf logs`](docs/AUDIT.md#wtf-logs) | недавние записи журнала уровня ERROR+, сгруппированные по службам |
| [`wtf services`](docs/AUDIT.md#wtf-services) | детальный разбор одного юнита: состояние, перезапуски, порты, журнал |
| [`wtf diff`](docs/AUDIT.md#wtf-diff) | сравнение текущего состояния с сохранённым снимком |
| [`wtf history`](docs/AUDIT.md#wtf-history) | список сохранённых снимков аудита |
| [`wtf crontab`](docs/AUDIT.md#wtf-crontab) | проверка системных и пользовательских crontab |
| [`wtf doctor`](docs/AUDIT.md#wtf-doctor) | самодиагностика: какие инструменты/файлы wtf может использовать |

### Просмотр по ресурсам — [docs/RESOURCES.md](docs/RESOURCES.md)

| command | что она делает |
|---------|--------------|
| [`wtf disk [PATH]`](docs/RESOURCES.md#wtf-disk) | обзор разделов; с PATH — крупнейшие папки; `--tree` раскрывает вглубь |
| [`wtf cpu`](docs/RESOURCES.md#wtf-cpu) | нагрузка, iowait, давление, главные потребители CPU |
| [`wtf mem`](docs/RESOURCES.md#wtf-mem) | RAM/swap, OOM-убийства, главные потребители памяти |
| [`wtf net`](docs/RESOURCES.md#wtf-net) | интерфейсы, шлюз, DNS, ошибки, прослушиваемые порты |
| [`wtf io`](docs/RESOURCES.md#wtf-io) | скорости IO по устройствам, давление, зависшие процессы |
| [`wtf who`](docs/RESOURCES.md#wtf-who) | вошедшие пользователи, недавние входы, неудачная аутентификация |
| [`wtf temp`](docs/RESOURCES.md#wtf-temp) | температуры оборудования из /sys/class/hwmon |
| [`wtf info`](docs/RESOURCES.md#wtf-info) | одностраничный снимок: всё вышеперечисленное сразу |
| [`wtf top`](docs/RESOURCES.md#wtf-top) | фокусированный топ процессов: сортировка по cpu/rss, фильтр по пользователю/имени |
| [`wtf ports` / `wtf port N`](docs/RESOURCES.md#wtf-ports) | прослушиваемые сокеты; разбор одного порта до PID, exe, cwd |
| [`wtf docker [NAME]`](docs/RESOURCES.md#wtf-docker) | каталог compose контейнера + размеры образа/контейнера/логов |

### Вывод и конфигурация

| command | что она делает |
|---------|--------------|
| [`wtf config`](docs/CONFIG.md#wtf-config) | показать действующую конфигурацию / вывести прокомментированный пример |
| [`wtf completion`](#install) | вывести скрипт автодополнения по `<Tab>` для bash/zsh |
| [machine output](docs/OUTPUT.md) | форматы `plain`/`json` и сборник рецептов grep·awk·jq |

`wtftools` поглощает и заменяет
[`checkcrontab`](https://github.com/wachawo/checkcrontab) — тот же валидатор
cron теперь живёт в `wtf crontab`.

## Документация

- [QUICKSTART.md](docs/QUICKSTART.md) — 5-минутное знакомство и шпаргалка
- [AUDIT.md](docs/AUDIT.md) — проверки здоровья, мониторинг, коды завершения, полный список проверок
- [RESOURCES.md](docs/RESOURCES.md) — просмотр по ресурсам с примерами
- [OUTPUT.md](docs/OUTPUT.md) — форматы `plain`/`json` и сборник рецептов для скриптов
- [CONFIG.md](docs/CONFIG.md) — файл конфигурации, пороги, игнорирование проверок

## Совместимость

- Python 3.8+
- Linux (дистрибутивы с systemd — основной сценарий; инструмент корректно
  снижает функциональность, когда `systemctl` / `journalctl` / `psutil` отсутствуют)
- Для базового CLI доступ к сети не требуется; опциональная сеть только для
  `wtf explain --llm …` и `wtf doctor --check-updates`

## Из исходного кода

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
python3 wtf.py audit       # or run it without installing
```

## Лицензия

MIT
