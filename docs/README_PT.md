# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> `wtf` — um único comando somente leitura que diz o que está errado em uma máquina Linux agora mesmo.

Sem agente. Sem daemon. Sem configuração. Sem chamadas de rede. Sem dependências
(apenas a biblioteca padrão do Python; `psutil` opcional). Seguro para executar em
produção via SSH — ele apenas *lê*. Experimente em dois segundos, sem nada para
instalar: `pipx run wtftools`

[English](https://github.com/wachawo/wtftools/blob/main/README.md) | [Español](https://github.com/wachawo/wtftools/blob/main/docs/README_ES.md) | **Português** | [Français](https://github.com/wachawo/wtftools/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/wtftools/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/wtftools/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/wtftools/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/wtftools/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/wtftools/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/wtftools/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/wtftools/blob/main/docs/README_KR.md)

Em vez de executar dez comandos (`htop`, `df -h`, `journalctl`,
`systemctl --failed`, `ss`, `dmesg`, …), você executa um:

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

Verde está bem, amarelo precisa de atenção, vermelho precisa ser corrigido. Duas formas de os administradores conviverem com ele:

- **Incidente** — algo parece errado → `wtf` → um checklist verde/amarelo/vermelho
  em vez de dez comandos dispersos.
- **Dia a dia** — `wtf daily` como verificação matinal, `wtf` no seu banner de login
  MOTD, `wtf audit --alert …` via cron. Sem necessidade de uma stack de monitoramento.

## O que ele faz

- **Auditoria de saúde** — mais de 35 verificações (disco, memória, swap, carga, PSI, mortes por OOM,
  unidades falhas, expiração de certificados, SMART, temperaturas, DNS, …) como um
  checklist verde / amarelo / vermelho.
- **Visões por recurso** — pergunte sobre uma coisa de cada vez, como comandos `show`
  em um switch: `wtf disk`, `wtf cpu`, `wtf mem`, `wtf net`, `wtf docker`, …
- **Triagem de incidentes** — `wtf problems`, `wtf events`, `wtf logs`,
  `wtf services <unit>`, `wtf explain` (opcionalmente através de uma LLM local ou hospedada).
- **Tendências e alertas** — `wtf daily`, snapshots + `wtf diff`, alertas via cron —
  sem necessidade de uma stack de monitoramento.
- **Scriptável** — `-f json` em cada comando e `-f plain` (separado por tabulações) nas
  visões de recursos e auditoria; o JSON carrega um `schema_version` para que os scripts sobrevivam às atualizações — para grep / awk / jq.
- **Amigável para iniciantes** — `--show-commands` imprime os comandos clássicos que cada
  visão substitui, para que você possa aprendê-los à mão.

## Instalação

```bash
pipx install wtftools          # recommended — works on any modern distro
pip install wtftools           # or classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i python3-wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

Após a instalação, você terá o comando `wtf`. Ative o autocompletar com `<Tab>` adicionando
uma linha ao rc do seu shell:

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

Novo por aqui? Comece pelo [guia rápido de 5 minutos](QUICKSTART.md).

## Comandos

Execute `wtf <command> --help` para ver as flags. Cada comando tem um link para sua página
de referência com exemplos.

### Saúde e monitoramento — [docs/AUDIT.md](AUDIT.md)

| command | o que faz |
|---------|--------------|
| [`wtf` / `wtf audit`](AUDIT.md#wtf-audit) | checklist verde/amarelo/vermelho do que está OK e do que não está |
| [`wtf problems`](AUDIT.md#wtf-problems) | apenas as linhas WARN+FAIL |
| [`wtf daily`](AUDIT.md#wtf-daily) | verificação matinal: auditoria + diff vs última execução + eventos |
| [`wtf explain`](AUDIT.md#wtf-explain) | conselhos práticos por verificação; `--llm` para enviar a uma LLM |
| [`wtf events`](AUDIT.md#wtf-events) | linha do tempo: reinicializações, mortes por OOM, unidades falhas, … |
| [`wtf logs`](AUDIT.md#wtf-logs) | entradas recentes ERROR+ do journal agrupadas por serviço |
| [`wtf services`](AUDIT.md#wtf-services) | detalhar uma unidade: estado, reinícios, portas, journal |
| [`wtf diff`](AUDIT.md#wtf-diff) | compara o estado atual com um snapshot salvo |
| [`wtf history`](AUDIT.md#wtf-history) | lista os snapshots de auditoria salvos |
| [`wtf crontab`](AUDIT.md#wtf-crontab) | valida o crontab do sistema + crontabs por usuário |
| [`wtf doctor`](AUDIT.md#wtf-doctor) | autodiagnóstico: quais ferramentas/arquivos o wtf pode usar |

### Visões por recurso — [docs/RESOURCES.md](RESOURCES.md)

| command | o que faz |
|---------|--------------|
| [`wtf disk [PATH]`](RESOURCES.md#wtf-disk) | visão geral das montagens; com um PATH, as maiores pastas; `--tree` detalha |
| [`wtf cpu`](RESOURCES.md#wtf-cpu) | carga, iowait, pressão, maiores consumidores de CPU |
| [`wtf mem`](RESOURCES.md#wtf-mem) | RAM/swap, mortes por OOM, maiores consumidores de memória |
| [`wtf net`](RESOURCES.md#wtf-net) | interfaces, gateway, DNS, erros, portas em escuta |
| [`wtf io`](RESOURCES.md#wtf-io) | taxas de IO por dispositivo, pressão, processos travados |
| [`wtf who`](RESOURCES.md#wtf-who) | usuários conectados, logins recentes, autenticações falhas |
| [`wtf temp`](RESOURCES.md#wtf-temp) | temperaturas de hardware de /sys/class/hwmon |
| [`wtf info`](RESOURCES.md#wtf-info) | snapshot de uma página: tudo acima de uma só vez |
| [`wtf top`](RESOURCES.md#wtf-top) | top de processos focado: ordenar por cpu/rss, filtrar por usuário/nome |
| [`wtf ports` / `wtf port N`](RESOURCES.md#wtf-ports) | sockets em escuta; detalhar uma porta até PID, exe, cwd |
| [`wtf docker [NAME]`](RESOURCES.md#wtf-docker) | diretório do compose do contêiner + tamanhos de imagem/contêiner/log |

### Saída e configuração

| command | o que faz |
|---------|--------------|
| [`wtf config`](CONFIG.md#wtf-config) | mostra a configuração efetiva / imprime um exemplo comentado |
| [`wtf completion`](#install) | imprime um script de autocompletar `<Tab>` para bash/zsh |
| [machine output](OUTPUT.md) | formatos `plain`/`json` e um receituário grep·awk·jq |

`wtftools` absorve e substitui
[`checkcrontab`](https://github.com/wachawo/checkcrontab) — o mesmo validador
de cron agora reside em `wtf crontab`.

## Documentação

- [QUICKSTART.md](QUICKSTART.md) — integração em 5 minutos e uma folha de dicas
- [AUDIT.md](AUDIT.md) — verificações de saúde, monitoramento, códigos de saída, a lista completa de verificações
- [RESOURCES.md](RESOURCES.md) — visões por recurso com exemplos
- [OUTPUT.md](OUTPUT.md) — formatos `plain`/`json` e o receituário de scripts
- [CONFIG.md](CONFIG.md) — arquivo de configuração, limiares, ignorar verificações
- [ROADMAP.md](ROADMAP.md) — o que está planejado e o que está fora do escopo

## Compatibilidade

- Python 3.9+
- Linux (as distribuições com systemd são o caminho ideal; a ferramenta se degrada
  de forma elegante quando `systemctl` / `journalctl` / `psutil` estão ausentes)
- Nenhum acesso à rede é necessário para a CLI principal; rede opcional apenas para
  `wtf explain --llm …` e `wtf doctor --check-updates`

## A partir do código-fonte

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
python3 wtf.py audit       # or run it without installing
```

## Licença

MIT
