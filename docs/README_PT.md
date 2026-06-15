# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> Um único comando para ver o que está acontecendo com o seu servidor Linux agora mesmo.

[English](https://github.com/wachawo/wtftools/blob/main/README.md) | [Español](https://github.com/wachawo/wtftools/blob/main/docs/README_ES.md) | **Português** | [Français](https://github.com/wachawo/wtftools/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/wtftools/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/wtftools/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/wtftools/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/wtftools/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/wtftools/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/wtftools/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/wtftools/blob/main/docs/README_KR.md)

Você acessa um servidor e algo parece errado. Em vez de executar dez
comandos (`htop`, `df -h`, `journalctl`, `systemctl --failed`, …), você executa um:

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

Verde está bem, amarelo precisa de atenção, vermelho precisa ser corrigido. É só isso.

## Instalação

```bash
pipx install wtftools          # recommended — works on any modern distro
```

Não tem `pipx`? Qualquer um destes também funciona:

```bash
pip install wtftools           # classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

Após a instalação, você terá o comando `wtf`. Experimente: `wtf`.

Autocompletar com Tab (opcional) — adicione uma linha ao rc do seu shell e pressione `<Tab>`:

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

Execute `wtf completion` sem argumento para ver as instruções completas.

## Os comandos que você realmente vai usar

```bash
wtf              # full health check — start here
wtf problems     # show ONLY what is wrong (warnings + failures)
wtf explain      # what to do about each problem, step by step
```

Depois pergunte sobre um recurso de cada vez, como comandos `show` em um switch:

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

`wtf disk` sem caminho é a visão geral das montagens — caminho completo, usado/total, percentual
e uma barra de uso:

```
$ wtf disk
# DISK
  /            1.4TB / 1.8TB   79%  [████████████████····]  ext4
  /boot      216.4MB / 1.9GB   11%  [██··················]  ext4
  /mnt/Data    5.3TB / 13.9TB  38%  [████████············]  ext4
```

Exemplo — o disco está enchendo, encontre o culpado. `wtf disk <path>` lista as
pastas diretamente abaixo dele, da maior para a menor (`path/  size  % of root  depth`):

```
$ wtf disk /var
# DISK USAGE /var
  lib/      15.0GB  75%  0
  log/       3.1GB  16%  0
  cache/     1.2GB   6%  0
```

Adicione `--tree` para detalhar a maior pasta, nível por nível (`--depth`,
padrão 3); `--tree N` abre as N maiores em cada nível. O número final
é a profundidade:

```
$ wtf disk / --tree
# DISK USAGE /
  home/                 1021.0GB  70%  0
  home/wachawo/         1021.0GB  70%  1
  home/wachawo/myApps/   429.7GB  30%  2
  usr/                   207.9GB  14%  0
  var/                   206.5GB  14%  0
```

`wtf disk --tree` sem um caminho detalha a montagem mais cheia. Execute com `sudo` para
ler pastas pertencentes ao root. A visão geral das montagens `# DISK` (sem caminho) permanece inalterada.

Aprendendo Linux? Adicione `--show-commands` a qualquer comando de recurso e ele também
imprime os comandos clássicos que substitui, para que você possa executá-los você mesmo:

```
$ wtf cpu --show-commands
  ...
  equivalent commands:
    $ uptime
    $ top -bn1 | head
    $ ps aux --sort=-%cpu | head
```

## Quando algo está quebrado

```bash
wtf problems -v                 # every problem, with detail
wtf events --since 6            # timeline: reboots, OOM kills, failed units
wtf service nginx               # one service: state, restarts, ports, journal
wtf logs --since '2 hours ago'  # recent ERROR+ journal entries by service
wtf explain                     # actionable advice per finding
wtf explain --llm ollama        # or let a local LLM summarize it
```

### Quem está em uma porta?

`wtf port <N>` (ou `wtf ports <N>`) mostra qual processo detém uma porta — o
PID, o arquivo executável exato por trás dela (via `lsof` + `/proc`) e o
diretório de onde ele é executado:

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

Execute com `sudo` para ver os processos pertencentes a outros usuários.

### Onde este contêiner foi iniciado?

`wtf docker <name>` responde "em qual pasta o `docker compose up` foi executado?"
diretamente a partir dos labels do contêiner — e quanto disco ele consome (camadas
da imagem, a camada gravável do contêiner e o log json):

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

`wtf docker` sem nome lista todos os contêineres em execução com suas colunas
de tamanho e o diretório de trabalho, além de uma linha TOTAL:

```
$ sudo wtf docker
# DOCKER
  NAME         STATUS       IMAGE   CONTNR     LOGS  WORKING DIR
  myapp_web    running      164MB    267MB   53.8MB  /home/deploy/myapp
  myapp_db     running      276MB     63B    4.02MB  /home/deploy/myapp
  TOTAL                     440MB    267MB   57.8MB
  note: IMAGE total is logical (images share layers); real disk 9.2GB, 1.1GB reclaimable — docker system df; logs cap with max-size; decimal units, like docker
```

Os tamanhos usam unidades decimais (1GB = 1000MB), de modo que se alinham com
`docker container ls --size`. O IMAGE por linha é o tamanho lógico completo da imagem
(o que o `docker` chama de tamanho *virtual*). O total de IMAGE elimina duplicatas por id de imagem,
então uma imagem compartilhada por muitos contêineres é contada uma vez — não uma vez por
contêiner. **Mas** imagens diferentes ainda compartilham camadas base no disco, então mesmo
essa soma sem duplicatas superestima o uso real; a linha de nota mostra o disco real
deduplicado por camada diretamente do `docker system df`. CONTNR (camada
gravável) e LOGS são por contêiner, então esses totais são exatos. Os tamanhos de log precisam de
acesso de leitura em `/var/lib/docker` — execute com `sudo`, caso contrário eles mostram `?`.

## Saída para scripts: grep, awk, jq

As cores desaparecem automaticamente quando você usa um pipe, então o `grep` simples sempre funciona.
Cada comando também tem formatos legíveis por máquina — `plain` (separado por tabulações,
sem cabeçalhos) e `json`. A flag também funciona antes do subcomando:

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

As cargas JSON dos comandos de recurso incluem `schema_version` para que seus
scripts sobrevivam a atualizações.

## Rotina diária e monitoramento

Um único comando para a verificação matinal — auditoria, o que mudou desde a última execução,
e a linha do tempo de eventos, com um veredito de uma linha no topo:

```bash
wtf daily                       # audit + diff vs yesterday + events
```

Ele salva um snapshot a cada execução, então o `wtf daily` de amanhã mostra a diferença.
Uma linha de crontab para uso autônomo (envia e-mail apenas quando algo está errado):

```cron
0 8 * * * wtf daily --format json > /var/log/wtf-daily.json 2>&1 || mail -s "wtf $(hostname)" you@example.com < /var/log/wtf-daily.json
```

Os blocos de construção também estão disponíveis separadamente:

```bash
wtf audit --brief               # one line — perfect for MOTD / SSH banner
wtf audit --save                # save a snapshot
wtf diff                        # what changed since the last snapshot
wtf history                     # list saved snapshots

# cron alerting without any monitoring stack:
wtf audit --alert 'mail -s "wtf $WTF_HOST" you@example.com'
wtf audit --alert-on warn --alert 'curl -X POST $SLACK_WEBHOOK -d @-'
```

Os códigos de saída são amigáveis para CI/cron:

| código | significado                                      |
|------|--------------------------------------------------|
| 0    | tudo OK                                           |
| 1    | avisos com `--strict`, ou erros de crontab       |
| 2    | a auditoria encontrou um `[FAIL]`                |
| 130  | interrompido (Ctrl-C)                             |

## Todos os subcomandos

| comando             | o que faz                                                   |
|---------------------|-------------------------------------------------------------|
| `wtf` / `wtf audit` | checklist verde/amarelo/vermelho: o que está OK e o que não está |
| `wtf problems`      | apenas as linhas WARN+FAIL                                  |
| `wtf daily`         | verificação matinal: auditoria + diff vs última execução + eventos |
| `wtf explain`       | conselhos práticos por verificação; `--llm` para enviar a uma LLM |
| `wtf disk [PATH]`   | visão geral das montagens; com PATH, as maiores pastas; `--tree` detalha |
| `wtf cpu`           | carga, iowait, pressão, maiores consumidores de CPU         |
| `wtf mem`           | RAM/swap, mortes por OOM, maiores consumidores de memória   |
| `wtf net`           | interfaces, gateway, DNS, erros, portas em escuta           |
| `wtf io`            | taxas de IO por dispositivo, pressão, processos travados    |
| `wtf who`           | usuários conectados, logins recentes, autenticações falhas  |
| `wtf temp`          | temperaturas de hardware dos sensores em /sys/class/hwmon   |
| `wtf info`          | snapshot de uma página: tudo acima de uma só vez            |
| `wtf top`           | top de processos focado: ordenar por cpu/rss, filtrar usuário/nome |
| `wtf ports`         | sockets em escuta com PID/usuário/comando proprietário      |
| `wtf port NUM`      | detalhar uma porta: PID, arquivo executável, diretório de trabalho |
| `wtf docker [NAME]` | diretório de trabalho do compose do contêiner + tamanhos de imagem/contêiner/log |
| `wtf service NAME`  | detalhamento de um serviço: estado, reinícios, mem, portas, journal |
| `wtf logs`          | entradas recentes ERROR+ do journal agrupadas por serviço   |
| `wtf events`        | linha do tempo cronológica: reinicializações, OOM, unidades falhas, … |
| `wtf history`       | lista os snapshots de auditoria salvos (`wtf audit --save` para criar) |
| `wtf diff`          | compara o estado atual com um snapshot salvo                |
| `wtf crontab`       | valida todos os locais padrão de crontab + crontabs por usuário |
| `wtf doctor`        | autodiagnóstico: quais ferramentas o wtftools pode realmente usar |
| `wtf config`        | mostra a configuração efetiva / imprime exemplo             |
| `wtf completion`    | imprime um script de autocompletar `<Tab>` para bash/zsh (ou ajuda de configuração) |

`wtftools` absorve e substitui
[`checkcrontab`](https://github.com/wachawo/checkcrontab) — o mesmo validador
de cron agora reside em `wtf crontab`.

## Opções avançadas de auditoria

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

### Verificações integradas

uptime · system state · load average · CPU iowait · PSI cpu/memory/io ·
TCP retransmits · memory · swap · disk (per mount) · inodes ·
read-only mounts · failed systemd units · enabled-but-down services ·
restart loops · network errors · conntrack · journal disk usage · zombies ·
D-state processes · OOM kills · kernel errors · kernel taint · cert expiry ·
open file descriptors · process count · failed auth · time sync ·
pending updates · reboot required · cron daemon · crontab syntax · docker ·
hw temperatures · disk SMART · DNS · HTTP/TCP probes · fail2ban.

## Configuração

Os limiares e as exclusões ficam em um arquivo INI em qualquer um destes locais:

- `/etc/wtftools/config.ini`
- `/etc/wtf/config.ini`
- `~/.config/wtftools/config.ini`

Execute `wtf config --example` para obter um modelo totalmente comentado. Destaques:

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

## Compatibilidade

- Python 3.8+
- Linux (as distribuições com systemd são o caminho ideal; a ferramenta se degrada
  de forma elegante quando `systemctl` / `journalctl` / `psutil` estão ausentes)
- Nenhum acesso à rede é necessário para a CLI principal
- Rede opcional: `wtf explain --llm claude/openai`, `wtf doctor --check-updates`

## A partir do código-fonte

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
# or test without installing:
python3 wtf.py audit
```

## Licença

MIT
