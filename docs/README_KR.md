# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> 지금 이 순간 리눅스 서버에서 무슨 일이 벌어지고 있는지 한 번의 명령으로 확인하세요.

[English](https://github.com/wachawo/wtftools/blob/main/README.md) | [Español](https://github.com/wachawo/wtftools/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/wtftools/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/wtftools/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/wtftools/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/wtftools/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/wtftools/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/wtftools/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/wtftools/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/wtftools/blob/main/docs/README_HI.md) | **한국어**

서버에 로그인했는데 뭔가 잘못된 것 같은 느낌이 듭니다. 열 개의 명령
(`htop`, `df -h`, `journalctl`, `systemctl --failed`, …)을 실행하는 대신 하나만 실행하세요:

```
$ wtf
─────────── AUDIT ────────────
[ OK ] uptime                  3d 4h 12m
[ OK ] load average            0.42 0.51 0.55 / 8 CPU
[ OK ] memory                  4.1GB / 16.0GB used (25%)
[WARN] disk /var               17.0GB / 20.0GB used (85%)
[ OK ] zombie processes        0 zombies
[FAIL] failed systemd units    1 failed unit(s)
[ OK ] crontab syntax          14 cron line(s), no errors

  Summary: 12 ok · 1 warn · 1 fail · 2 skip
```

초록색은 괜찮음, 노란색은 살펴봐야 함, 빨간색은 고쳐야 함을 뜻합니다. 그게 전부입니다.

## 설치

```bash
pipx install wtftools          # recommended — works on any modern distro
```

`pipx`가 없나요? 다음 방법들도 모두 사용할 수 있습니다:

```bash
pip install wtftools           # classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

설치 후에는 `wtf` 명령을 사용할 수 있습니다. 실행해 보세요: `wtf`.

## 실제로 쓰게 될 명령들

```bash
wtf              # full health check — start here
wtf problems     # show ONLY what is wrong (warnings + failures)
wtf explain      # what to do about each problem, step by step
```

그런 다음 스위치에서 `show` 명령을 쓰듯이 한 번에 하나의 리소스에 대해 물어보세요:

```bash
wtf disk         # is there space? per-mount usage, inodes, read-only
wtf disk --tree  # WHAT is eating the space (largest directories)
wtf cpu          # load, iowait, top CPU consumers
wtf mem          # RAM/swap, OOM kills, top memory consumers
wtf net          # interfaces, IPs, gateway, DNS, listening ports
wtf io           # disk read/write rates, IO-stuck processes
wtf who          # who is logged in, recent logins, failed auth
```

예시 — 디스크가 가득 차고 있을 때 원인을 찾기:

```
$ wtf disk --tree /var
────────────── DISK ──────────────
  /                [████████████████····]  79%  1.4TB / 1.8TB  ext4
  /var             [█████████████████···]  85%  17.0GB / 20.0GB  ext4

───────── LARGEST UNDER /var ─────────
      15.0GB  /var/lib
       3.1GB  /var/log
       1.8GB  /var/log/app
```

경로 없이 `wtf disk --tree`를 실행하면 가장 가득 찬 마운트를 자동으로 선택합니다.

리눅스를 배우는 중인가요? 모든 리소스 명령에 `--show-commands`를 추가하면
대체하는 고전적인 명령들도 함께 출력해 주므로, 직접 실행해 볼 수 있습니다:

```
$ wtf cpu --show-commands
  ...
  equivalent commands:
    $ uptime
    $ top -bn1 | head
    $ ps aux --sort=-%cpu | head
```

## 무언가 고장났을 때

```bash
wtf problems -v                 # every problem, with detail
wtf events --since 6            # timeline: reboots, OOM kills, failed units
wtf service nginx               # one service: state, restarts, ports, journal
wtf logs --since '2 hours ago'  # recent ERROR+ journal entries by service
wtf explain                     # actionable advice per finding
wtf explain --llm ollama        # or let a local LLM summarize it
```

## 스크립트용 출력: grep, awk, jq

파이프로 연결하면 색상이 자동으로 사라지므로, 일반 `grep`은 항상 동작합니다.
모든 명령에는 기계가 읽을 수 있는 형식도 있습니다 — `plain`(탭으로 구분,
헤더 없음)과 `json`입니다. 이 플래그는 서브명령 앞에도 쓸 수 있습니다:

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

리소스 명령의 JSON 페이로드에는 `schema_version`이 포함되어 있어,
업그레이드를 거쳐도 스크립트가 계속 동작합니다.

## 일상 점검과 모니터링

아침 점검을 위한 한 가지 명령 — 감사 결과, 마지막 실행 이후 변경된 내용,
그리고 이벤트 타임라인을 한 줄 요약과 함께 보여줍니다:

```bash
wtf daily                       # audit + diff vs yesterday + events
```

실행할 때마다 스냅샷을 저장하므로, 내일의 `wtf daily`는 변경된 내용을 보여줍니다.
무인 사용을 위한 crontab 줄(문제가 있을 때만 메일을 보냄):

```cron
0 8 * * * wtf daily --format json > /var/log/wtf-daily.json 2>&1 || mail -s "wtf $(hostname)" you@example.com < /var/log/wtf-daily.json
```

구성 요소들은 개별적으로도 사용할 수 있습니다:

```bash
wtf audit --brief               # one line — perfect for MOTD / SSH banner
wtf audit --save                # save a snapshot
wtf diff                        # what changed since the last snapshot
wtf history                     # list saved snapshots

# cron alerting without any monitoring stack:
wtf audit --alert 'mail -s "wtf $WTF_HOST" you@example.com'
wtf audit --alert-on warn --alert 'curl -X POST $SLACK_WEBHOOK -d @-'
```

종료 코드는 CI/cron 친화적입니다:

| 코드 | 의미                                             |
|------|--------------------------------------------------|
| 0    | 모두 정상                                         |
| 1    | `--strict`가 켜진 상태의 경고, 또는 crontab 오류  |
| 2    | 감사에서 `[FAIL]`을 발견                          |
| 130  | 중단됨 (Ctrl-C)                                   |

## 모든 서브명령

| 명령                | 하는 일                                                     |
|---------------------|-------------------------------------------------------------|
| `wtf` / `wtf audit` | 초록/노랑/빨강 체크리스트: 무엇이 정상이고 무엇이 아닌지     |
| `wtf problems`      | WARN+FAIL 행만 표시                                          |
| `wtf daily`         | 아침 점검: 감사 + 마지막 실행 대비 변경 + 이벤트             |
| `wtf explain`       | 점검별 실행 가능한 조언; `--llm`으로 LLM에 파이프 연결       |
| `wtf disk`          | 마운트별 사용량; `--tree`는 가장 큰 디렉터리를 표시          |
| `wtf cpu`           | 부하, iowait, 압력, CPU를 가장 많이 쓰는 프로세스           |
| `wtf mem`           | RAM/스왑, OOM 종료, 메모리를 가장 많이 쓰는 프로세스         |
| `wtf net`           | 인터페이스, 게이트웨이, DNS, 오류, 수신 대기 포트           |
| `wtf io`            | 장치별 IO 속도, 압력, 멈춘 프로세스                          |
| `wtf who`           | 로그인한 사용자, 최근 로그인, 실패한 인증                    |
| `wtf info`          | 한 페이지 스냅샷: 위의 모든 것을 한 번에                     |
| `wtf top`           | 집중 프로세스 top: cpu/rss로 정렬, user/name으로 필터링      |
| `wtf ports`         | 소유 PID/사용자/명령과 함께 수신 대기 소켓                   |
| `wtf service NAME`  | 서비스 하나를 자세히: 상태, 재시작, 메모리, 포트, 저널       |
| `wtf logs`          | 서비스별로 묶인 최근 ERROR+ 저널 항목                        |
| `wtf events`        | 시간순 타임라인: 재부팅, OOM, 실패한 유닛, …                |
| `wtf history`       | 저장된 감사 스냅샷 목록 (`wtf audit --save`로 생성)          |
| `wtf diff`          | 현재 상태를 저장된 스냅샷과 비교                             |
| `wtf crontab`       | 모든 표준 crontab 위치 + 사용자별 crontab 검증              |
| `wtf doctor`        | 자가 진단: wtftools가 실제로 사용할 수 있는 도구            |
| `wtf config`        | 적용된 설정 표시 / 예시 출력                                 |

`wtftools`는
[`checkcrontab`](https://github.com/wachawo/checkcrontab)을 흡수하고 대체합니다 —
동일한 cron 검증기가 이제 `wtf crontab`에 들어 있습니다.

## 고급 감사 옵션

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

### 내장 점검 항목

uptime · system state · load average · CPU iowait · PSI cpu/memory/io ·
TCP retransmits · memory · swap · disk (per mount) · inodes ·
read-only mounts · failed systemd units · enabled-but-down services ·
restart loops · network errors · conntrack · journal disk usage · zombies ·
D-state processes · OOM kills · kernel errors · kernel taint · cert expiry ·
open file descriptors · process count · failed auth · time sync ·
pending updates · reboot required · cron daemon · crontab syntax · docker ·
hw temperatures · disk SMART · DNS · HTTP/TCP probes · fail2ban.

## 설정

임계값과 무시 항목은 다음 위치 중 어디에든 둘 수 있는 INI 파일에 있습니다:

- `/etc/wtftools/config.ini`
- `/etc/wtf/config.ini`
- `~/.config/wtftools/config.ini`

전체 주석이 달린 템플릿을 보려면 `wtf config --example`을 실행하세요. 주요 항목:

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

## 호환성

- Python 3.8+
- 리눅스 (systemd 배포판이 가장 잘 동작하는 환경이며, `systemctl` /
  `journalctl` / `psutil`이 없을 때는 우아하게 기능이 축소됩니다)
- 핵심 CLI에는 네트워크 접근이 필요 없습니다
- 선택적 네트워크: `wtf explain --llm claude/openai`, `wtf doctor --check-updates`

## 소스에서 빌드

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
# or test without installing:
python3 wtf.py audit
```

## 라이선스

MIT
