# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> `wtf` — un único comando de solo lectura que te dice qué anda mal en una máquina Linux ahora mismo.

Sin agente. Sin demonio. Sin configuración. Sin llamadas de red. Sin dependencias
(solo la biblioteca estándar de Python; `psutil` opcional). Seguro de ejecutar en
producción por SSH — solo *lee*. Pruébalo en dos segundos, sin nada que instalar:
`pipx run wtftools`

[English](https://github.com/wachawo/wtftools/blob/main/README.md) | **Español** | [Português](https://github.com/wachawo/wtftools/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/wtftools/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/wtftools/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/wtftools/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/wtftools/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/wtftools/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/wtftools/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/wtftools/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/wtftools/blob/main/docs/README_KR.md)

En lugar de ejecutar diez comandos (`htop`, `df -h`, `journalctl`,
`systemctl --failed`, `ss`, `dmesg`, …) ejecutas uno solo:

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

El verde está bien, el amarillo necesita una revisión, el rojo necesita arreglo. Dos formas en que los administradores lo usan a diario:

- **Incidente** — algo va mal → `wtf` → una lista de verificación verde/amarillo/rojo
  en lugar de diez comandos dispersos.
- **Día a día** — `wtf daily` como revisión matutina, `wtf` en tu banner de inicio de
  sesión MOTD, `wtf audit --alert …` desde cron. Sin necesidad de una pila de monitoreo.

## Qué puede hacer

- **Auditoría de salud** — más de 35 verificaciones (disco, memoria, swap, carga, PSI, OOM kills,
  unidades fallidas, expiración de certificados, SMART, temperaturas, DNS, …) como una
  lista de verificación verde / amarillo / rojo.
- **Vistas por recurso** — pregunta por una cosa a la vez, como los comandos `show`
  en un switch: `wtf disk`, `wtf cpu`, `wtf mem`, `wtf net`, `wtf docker`, …
- **Triaje de incidentes** — `wtf problems`, `wtf events`, `wtf logs`,
  `wtf services <unit>`, `wtf explain` (opcionalmente a través de un LLM local o alojado).
- **Tendencias y alertas** — `wtf daily`, instantáneas + `wtf diff`, alertas por cron —
  sin necesidad de una pila de monitoreo.
- **Apto para scripts** — `-f json` en cada comando y `-f plain` (separado por tabuladores) en las
  vistas de recursos y auditoría; el JSON lleva un `schema_version` para que los scripts sobrevivan a las actualizaciones — para grep / awk / jq.
- **Apto para principiantes** — `--show-commands` imprime los comandos clásicos que cada
  vista reemplaza, para que puedas aprenderlos a mano.

## Instalación

```bash
pipx install wtftools          # recommended — works on any modern distro
pip install wtftools           # or classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i python3-wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

Tras la instalación tienes el comando `wtf`. Habilita el autocompletado con `<Tab>` añadiendo
una línea al rc de tu shell:

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

¿Nuevo por aquí? Empieza con la [guía rápida de 5 minutos](QUICKSTART.md).

## Comandos

Ejecuta `wtf <command> --help` para ver las opciones. Cada comando enlaza a su página de referencia
con ejemplos.

### Salud y monitoreo — [docs/AUDIT.md](AUDIT.md)

| command | qué hace |
|---------|--------------|
| [`wtf` / `wtf audit`](AUDIT.md#wtf-audit) | lista de verificación verde/amarillo/rojo de qué está bien y qué no |
| [`wtf problems`](AUDIT.md#wtf-problems) | solo las filas WARN+FAIL |
| [`wtf daily`](AUDIT.md#wtf-daily) | revisión matutina: auditoría + diff vs última ejecución + eventos |
| [`wtf explain`](AUDIT.md#wtf-explain) | consejos accionables por hallazgo; `--llm` para canalizar a un LLM |
| [`wtf events`](AUDIT.md#wtf-events) | línea de tiempo: reinicios, OOM kills, unidades fallidas, … |
| [`wtf logs`](AUDIT.md#wtf-logs) | entradas recientes ERROR+ del journal agrupadas por servicio |
| [`wtf services`](AUDIT.md#wtf-services) | profundiza en una unidad: estado, reinicios, puertos, journal |
| [`wtf diff`](AUDIT.md#wtf-diff) | compara el estado actual con una instantánea guardada |
| [`wtf history`](AUDIT.md#wtf-history) | lista las instantáneas de auditoría guardadas |
| [`wtf crontab`](AUDIT.md#wtf-crontab) | valida los crontabs del sistema + por usuario |
| [`wtf doctor`](AUDIT.md#wtf-doctor) | autodiagnóstico: qué herramientas/archivos puede usar wtf |

### Vistas de recursos — [docs/RESOURCES.md](RESOURCES.md)

| command | qué hace |
|---------|--------------|
| [`wtf disk [PATH]`](RESOURCES.md#wtf-disk) | resumen de montajes; con un PATH, las carpetas más grandes; `--tree` profundiza |
| [`wtf cpu`](RESOURCES.md#wtf-cpu) | carga, iowait, presión, mayores consumidores de CPU |
| [`wtf mem`](RESOURCES.md#wtf-mem) | RAM/swap, OOM kills, mayores consumidores de memoria |
| [`wtf net`](RESOURCES.md#wtf-net) | interfaces, gateway, DNS, errores, puertos en escucha |
| [`wtf io`](RESOURCES.md#wtf-io) | tasas de IO por dispositivo, presión, procesos bloqueados |
| [`wtf who`](RESOURCES.md#wtf-who) | usuarios conectados, inicios de sesión recientes, autenticaciones fallidas |
| [`wtf temp`](RESOURCES.md#wtf-temp) | temperaturas de hardware desde /sys/class/hwmon |
| [`wtf info`](RESOURCES.md#wtf-info) | instantánea de una página: todo lo anterior a la vez |
| [`wtf top`](RESOURCES.md#wtf-top) | top de procesos enfocado: ordena por cpu/rss, filtra por usuario/nombre |
| [`wtf ports` / `wtf port N`](RESOURCES.md#wtf-ports) | sockets en escucha; profundiza en un puerto hasta PID, exe, cwd |
| [`wtf docker [NAME]`](RESOURCES.md#wtf-docker) | directorio compose del contenedor + tamaños de imagen/contenedor/log |

### Salida y configuración

| command | qué hace |
|---------|--------------|
| [`wtf config`](CONFIG.md#wtf-config) | muestra la configuración efectiva / imprime un ejemplo comentado |
| [`wtf completion`](#install) | imprime un script de autocompletado `<Tab>` para bash/zsh |
| [machine output](OUTPUT.md) | formatos `plain`/`json` y un recetario grep·awk·jq |

`wtftools` absorbe y reemplaza a
[`checkcrontab`](https://github.com/wachawo/checkcrontab): el mismo validador
de cron ahora vive en `wtf crontab`.

## Documentación

- [QUICKSTART.md](QUICKSTART.md) — incorporación en 5 minutos y una hoja de referencia
- [AUDIT.md](AUDIT.md) — verificaciones de salud, monitoreo, códigos de salida, la lista completa de verificaciones
- [RESOURCES.md](RESOURCES.md) — vistas por recurso con ejemplos
- [OUTPUT.md](OUTPUT.md) — formatos `plain`/`json` y el recetario de scripting
- [CONFIG.md](CONFIG.md) — archivo de configuración, umbrales, ignorar verificaciones
- [ROADMAP.md](ROADMAP.md) — qué está planeado y qué queda fuera del alcance

## Compatibilidad

- Python 3.9+
- Linux (las distribuciones con systemd son el camino ideal; la herramienta se degrada
  con elegancia cuando faltan `systemctl` / `journalctl` / `psutil`)
- No se requiere acceso a la red para la CLI principal; red opcional solo para
  `wtf explain --llm …` y `wtf doctor --check-updates`

## Desde el código fuente

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
python3 wtf.py audit       # or run it without installing
```

## Licencia

MIT
