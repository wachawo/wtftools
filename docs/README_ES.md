# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> Un solo comando para ver qué está pasando con tu servidor Linux ahora mismo.

[English](https://github.com/wachawo/wtftools/blob/main/README.md) | **Español** | [Português](https://github.com/wachawo/wtftools/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/wtftools/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/wtftools/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/wtftools/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/wtftools/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/wtftools/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/wtftools/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/wtftools/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/wtftools/blob/main/docs/README_KR.md)

Inicias sesión en un servidor y algo no va bien. En lugar de ejecutar diez
comandos (`htop`, `df -h`, `journalctl`, `systemctl --failed`, …) ejecutas uno solo:

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

El verde está bien, el amarillo necesita una revisión, el rojo necesita arreglo. Eso es todo.

## Instalación

```bash
pipx install wtftools          # recommended — works on any modern distro
```

¿No tienes `pipx`? Cualquiera de estos también funciona:

```bash
pip install wtftools           # classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

Tras la instalación tienes el comando `wtf`. Pruébalo: `wtf`.

Autocompletado con Tab (opcional): añade una línea al rc de tu shell y pulsa `<Tab>`:

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

Ejecuta `wtf completion` sin argumentos para ver las instrucciones completas.

## Los comandos que realmente usarás

```bash
wtf              # full health check — start here
wtf problems     # show ONLY what is wrong (warnings + failures)
wtf explain      # what to do about each problem, step by step
```

Luego pregunta por un recurso a la vez, como los comandos `show` en un switch:

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

`wtf disk` sin ruta es el resumen de puntos de montaje: ruta completa, usado/total, porcentaje
y una barra de uso:

```
$ wtf disk
# DISK
  /            1.4TB / 1.8TB   79%  [████████████████····]  ext4
  /boot      216.4MB / 1.9GB   11%  [██··················]  ext4
  /mnt/Data    5.3TB / 13.9TB  38%  [████████············]  ext4
```

Ejemplo: el disco se está llenando, encuentra al culpable. `wtf disk <path>` lista las
carpetas directamente dentro de él, las más grandes primero (`path/  size  % of root  depth`):

```
$ wtf disk /var
# DISK USAGE /var
  lib/      15.0GB  75%  0
  log/       3.1GB  16%  0
  cache/     1.2GB   6%  0
```

Añade `--tree` para profundizar en la carpeta más grande, nivel por nivel (`--depth`,
por defecto 3); `--tree N` abre las N más grandes en cada nivel. El número final
es la profundidad:

```
$ wtf disk / --tree
# DISK USAGE /
  home/                 1021.0GB  70%  0
  home/wachawo/         1021.0GB  70%  1
  home/wachawo/myApps/   429.7GB  30%  2
  usr/                   207.9GB  14%  0
  var/                   206.5GB  14%  0
```

`wtf disk --tree` sin una ruta profundiza en el punto de montaje más lleno. Ejecútalo con `sudo`
para leer carpetas propiedad de root. El resumen de montajes `# DISK` (sin ruta) no cambia.

¿Estás aprendiendo Linux? Añade `--show-commands` a cualquier comando de recurso y
también imprimirá los comandos clásicos que reemplaza, para que puedas ejecutarlos tú mismo:

```
$ wtf cpu --show-commands
  ...
  equivalent commands:
    $ uptime
    $ top -bn1 | head
    $ ps aux --sort=-%cpu | head
```

## Cuando algo está roto

```bash
wtf problems -v                 # every problem, with detail
wtf events --since 6            # timeline: reboots, OOM kills, failed units
wtf service nginx               # one service: state, restarts, ports, journal
wtf logs --since '2 hours ago'  # recent ERROR+ journal entries by service
wtf explain                     # actionable advice per finding
wtf explain --llm ollama        # or let a local LLM summarize it
```

### ¿Quién está en un puerto?

`wtf port <N>` (o `wtf ports <N>`) muestra qué proceso ocupa un puerto: el
PID, el archivo ejecutable exacto detrás de él (vía `lsof` + `/proc`) y el
directorio desde el que se ejecuta:

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

Ejecútalo con `sudo` para ver procesos de otros usuarios.

### ¿Dónde se inició este contenedor?

`wtf docker <name>` responde a "¿en qué carpeta se ejecutó `docker compose up`?"
directamente desde las etiquetas del contenedor, y cuánto disco consume (capas
de la imagen, la capa de contenedor escribible y el log json):

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

`wtf docker` sin nombre lista todos los contenedores en ejecución con sus
columnas de tamaño y directorio de trabajo, más una fila TOTAL:

```
$ sudo wtf docker
# DOCKER
  NAME         STATUS       IMAGE   CONTNR     LOGS  WORKING DIR
  myapp_web    running      164MB    267MB   53.8MB  /home/deploy/myapp
  myapp_db     running      276MB     63B    4.02MB  /home/deploy/myapp
  TOTAL                     440MB    267MB   57.8MB
  note: IMAGE total is logical (images share layers); real disk 9.2GB, 1.1GB reclaimable — docker system df; logs cap with max-size; decimal units, like docker
```

Los tamaños usan unidades decimales (1GB = 1000MB), así que coinciden con
`docker container ls --size`. El IMAGE por fila es el tamaño lógico completo
de la imagen (lo que `docker` llama tamaño *virtual*). El total de IMAGE
deduplica por id de imagen, así que una imagen compartida por muchos
contenedores se cuenta una sola vez, no una por contenedor. **Pero**
imágenes distintas igualmente comparten capas base en disco, así que incluso
esa suma deduplicada sobreestima el uso real; la línea de nota muestra el
disco real con capas deduplicadas directamente desde `docker system df`.
CONTNR (capa escribible) y LOGS son por contenedor, así que esos totales son
exactos. Los tamaños de los logs requieren acceso de lectura bajo
`/var/lib/docker`: ejecútalo con `sudo`, de lo contrario muestran `?`.

## Salida para scripts: grep, awk, jq

Los colores desaparecen automáticamente cuando rediriges con un pipe, así que un simple `grep` siempre funciona.
Cada comando también tiene formatos legibles por máquina: `plain` (separado por tabuladores,
sin encabezados) y `json`. La opción funciona también antes del subcomando:

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

Las cargas útiles JSON de los comandos de recursos llevan `schema_version` para que tus
scripts sobrevivan a las actualizaciones.

## Rutina diaria y monitoreo

Un solo comando para la revisión matutina: auditoría, qué cambió desde la última ejecución
y la línea de tiempo de eventos, con un veredicto de una línea en la parte superior:

```bash
wtf daily                       # audit + diff vs yesterday + events
```

Guarda una instantánea en cada ejecución, así que el `wtf daily` de mañana muestra la diferencia.
Una línea de crontab para uso desatendido (solo envía correo cuando algo va mal):

```cron
0 8 * * * wtf daily --format json > /var/log/wtf-daily.json 2>&1 || mail -s "wtf $(hostname)" you@example.com < /var/log/wtf-daily.json
```

Los bloques de construcción también están disponibles por separado:

```bash
wtf audit --brief               # one line — perfect for MOTD / SSH banner
wtf audit --save                # save a snapshot
wtf diff                        # what changed since the last snapshot
wtf history                     # list saved snapshots

# cron alerting without any monitoring stack:
wtf audit --alert 'mail -s "wtf $WTF_HOST" you@example.com'
wtf audit --alert-on warn --alert 'curl -X POST $SLACK_WEBHOOK -d @-'
```

Los códigos de salida son compatibles con CI/cron:

| código | significado                                       |
|------|--------------------------------------------------|
| 0    | todo correcto                                    |
| 1    | advertencias con `--strict`, o errores de crontab |
| 2    | la auditoría encontró un `[FAIL]`                |
| 130  | interrumpido (Ctrl-C)                            |

## Todos los subcomandos

| comando             | qué hace                                                    |
|---------------------|-------------------------------------------------------------|
| `wtf` / `wtf audit` | lista de verificación verde/amarillo/rojo: qué está bien y qué no |
| `wtf problems`      | solo filas WARN+FAIL                                        |
| `wtf daily`         | revisión matutina: auditoría + diff vs última ejecución + eventos |
| `wtf explain`       | consejos accionables por verificación; `--llm` para canalizar a un LLM |
| `wtf disk [PATH]`   | resumen de montajes; con PATH, las carpetas más grandes; `--tree` profundiza |
| `wtf cpu`           | carga, iowait, presión, mayores consumidores de CPU         |
| `wtf mem`           | RAM/swap, OOM kills, mayores consumidores de memoria        |
| `wtf net`           | interfaces, gateway, DNS, errores, puertos en escucha       |
| `wtf io`            | tasas de IO por dispositivo, presión, procesos bloqueados   |
| `wtf who`           | usuarios conectados, inicios de sesión recientes, autenticaciones fallidas |
| `wtf temp`          | temperaturas de hardware desde los sensores /sys/class/hwmon |
| `wtf info`          | instantánea de una página: todo lo anterior a la vez        |
| `wtf top`           | top de procesos enfocado: ordena por cpu/rss, filtra usuario/nombre |
| `wtf ports`         | sockets en escucha con PID/usuario/comando propietario      |
| `wtf port NUM`      | detalle de un puerto: PID, archivo ejecutable, directorio de trabajo |
| `wtf docker [NAME]` | directorio de trabajo compose del contenedor + tamaños de imagen/contenedor/log |
| `wtf service NAME`  | detalle de un servicio: estado, reinicios, mem, puertos, journal |
| `wtf logs`          | entradas recientes ERROR+ del journal agrupadas por servicio |
| `wtf events`        | línea de tiempo cronológica: reinicios, OOM, unidades fallidas, … |
| `wtf history`       | lista las instantáneas de auditoría guardadas (`wtf audit --save` para crear) |
| `wtf diff`          | compara el estado actual con una instantánea guardada       |
| `wtf crontab`       | valida todas las ubicaciones estándar de crontab + crontabs por usuario |
| `wtf doctor`        | autodiagnóstico: qué herramientas puede usar realmente wtftools |
| `wtf config`        | muestra la configuración efectiva / imprime un ejemplo      |
| `wtf completion`    | imprime un script de autocompletado `<Tab>` para bash/zsh (o ayuda de configuración) |

`wtftools` absorbe y reemplaza a
[`checkcrontab`](https://github.com/wachawo/checkcrontab): el mismo validador
de cron ahora vive en `wtf crontab`.

## Opciones avanzadas de auditoría

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

### Verificaciones integradas

uptime · system state · load average · CPU iowait · PSI cpu/memory/io ·
TCP retransmits · memory · swap · disk (per mount) · inodes ·
read-only mounts · failed systemd units · enabled-but-down services ·
restart loops · network errors · conntrack · journal disk usage · zombies ·
D-state processes · OOM kills · kernel errors · kernel taint · cert expiry ·
open file descriptors · process count · failed auth · time sync ·
pending updates · reboot required · cron daemon · crontab syntax · docker ·
hw temperatures · disk SMART · DNS · HTTP/TCP probes · fail2ban.

## Configuración

Los umbrales y las exclusiones viven en un archivo INI en cualquiera de estas rutas:

- `/etc/wtftools/config.ini`
- `/etc/wtf/config.ini`
- `~/.config/wtftools/config.ini`

Ejecuta `wtf config --example` para obtener una plantilla completamente comentada. Lo esencial:

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

## Compatibilidad

- Python 3.8+
- Linux (las distribuciones con systemd son el camino ideal; la herramienta se degrada
  con elegancia cuando faltan `systemctl` / `journalctl` / `psutil`)
- No se requiere acceso a la red para la CLI principal
- Red opcional: `wtf explain --llm claude/openai`, `wtf doctor --check-updates`

## Desde el código fuente

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
# or test without installing:
python3 wtf.py audit
```

## Licencia

MIT
