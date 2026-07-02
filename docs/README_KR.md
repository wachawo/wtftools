# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> `wtf` — 지금 리눅스 머신에서 무엇이 잘못되었는지 알려 주는 단 하나의 읽기 전용 명령.

에이전트 없음. 데몬 없음. 설정 없음. 네트워크 호출 없음. 의존성 없음(Python 표준
라이브러리만 사용; `psutil`은 선택 사항). SSH로 프로덕션에서 실행해도 안전합니다 —
*읽기*만 합니다. 설치할 것 없이 2초 만에 사용해 보세요: `pipx run wtftools`

[English](https://github.com/wachawo/wtftools/blob/main/README.md) | [Español](https://github.com/wachawo/wtftools/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/wtftools/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/wtftools/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/wtftools/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/wtftools/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/wtftools/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/wtftools/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/wtftools/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/wtftools/blob/main/docs/README_HI.md) | **한국어**

열 개의 명령(`htop`, `df -h`, `journalctl`, `systemctl --failed`, `ss`,
`dmesg`, …)을 실행하는 대신 하나만 실행하세요:

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

초록색은 괜찮음, 노란색은 살펴봐야 함, 빨간색은 고쳐야 함을 뜻합니다. 관리자가 활용하는 두 가지 방식:

- **장애 대응** — 뭔가 이상하다 → `wtf` → 열 개의 흩어진 명령 대신
  초록/노랑/빨강 체크리스트.
- **일상** — 아침 점검으로 `wtf daily`, MOTD 로그인 배너에 `wtf`, cron에서
  `wtf audit --alert …`. 모니터링 스택이 필요 없습니다.

## 할 수 있는 일

- **상태 감사** — 35개 이상의 점검(디스크, 메모리, 스왑, 부하, PSI, OOM 종료,
  실패한 유닛, 인증서 만료, SMART, 온도, DNS, …)을
  초록 / 노랑 / 빨강 체크리스트로 보여줍니다.
- **리소스별 보기** — 스위치에서 `show` 명령을 쓰듯이 한 번에 하나씩
  물어봅니다: `wtf disk`, `wtf cpu`, `wtf mem`, `wtf net`, `wtf docker`, …
- **장애 분류** — `wtf problems`, `wtf events`, `wtf logs`,
  `wtf services <unit>`, `wtf explain`(선택적으로 로컬 또는 호스팅 LLM을 통해).
- **추세 및 알림** — `wtf daily`, 스냅샷 + `wtf diff`, cron 알림 —
  별도의 모니터링 스택이 필요 없습니다.
- **스크립트 친화적** — `-f json`은 모든 명령에서 쓸 수 있고, `-f plain`(탭으로 구분)은 리소스와 감사 보기에서만 쓸 수 있습니다;
  JSON은 `schema_version`을 포함하므로 스크립트가 업그레이드 후에도 동작합니다 — grep / awk / jq에 활용할 수 있습니다.
- **초보자 친화적** — `--show-commands`는 각 보기가 대체하는 고전적인 명령들을
  출력해 주므로, 직접 손으로 익힐 수 있습니다.

## Install

```bash
pipx install wtftools          # recommended — works on any modern distro
pip install wtftools           # or classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i python3-wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

설치 후에는 `wtf` 명령을 사용할 수 있습니다. 셸 rc 파일에 한 줄을 추가하면
`<Tab>` 자동완성을 켤 수 있습니다:

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

처음이신가요? [5분 빠른 시작](QUICKSTART.md)부터 시작하세요.

## Commands

플래그는 `wtf <command> --help`로 확인하세요. 각 명령은 예시가 포함된
참조 페이지로 연결됩니다.

### Health & monitoring — [docs/AUDIT.md](AUDIT.md)

| command | what it does |
|---------|--------------|
| [`wtf` / `wtf audit`](AUDIT.md#wtf-audit) | 무엇이 정상이고 무엇이 아닌지 보여주는 초록/노랑/빨강 체크리스트 |
| [`wtf problems`](AUDIT.md#wtf-problems) | WARN+FAIL 행만 표시 |
| [`wtf daily`](AUDIT.md#wtf-daily) | 아침 점검: 감사 + 마지막 실행 대비 변경 + 이벤트 |
| [`wtf explain`](AUDIT.md#wtf-explain) | 점검별 실행 가능한 조언; `--llm`으로 LLM에 파이프 연결 |
| [`wtf events`](AUDIT.md#wtf-events) | 타임라인: 재부팅, OOM 종료, 실패한 유닛, … |
| [`wtf logs`](AUDIT.md#wtf-logs) | 서비스별로 묶인 최근 ERROR+ 저널 항목 |
| [`wtf services`](AUDIT.md#wtf-services) | 유닛 하나를 자세히: 상태, 재시작, 포트, 저널 |
| [`wtf diff`](AUDIT.md#wtf-diff) | 현재 상태를 저장된 스냅샷과 비교 |
| [`wtf history`](AUDIT.md#wtf-history) | 저장된 감사 스냅샷 목록 |
| [`wtf crontab`](AUDIT.md#wtf-crontab) | 시스템 + 사용자별 crontab 검증 |
| [`wtf doctor`](AUDIT.md#wtf-doctor) | 자가 진단: wtf가 사용할 수 있는 도구/파일 |

### Resource views — [docs/RESOURCES.md](RESOURCES.md)

| command | what it does |
|---------|--------------|
| [`wtf disk [PATH]`](RESOURCES.md#wtf-disk) | 마운트 개요; PATH가 있으면 가장 큰 폴더; `--tree`로 파고들기 |
| [`wtf cpu`](RESOURCES.md#wtf-cpu) | 부하, iowait, 압력, CPU를 가장 많이 쓰는 프로세스 |
| [`wtf mem`](RESOURCES.md#wtf-mem) | RAM/스왑, OOM 종료, 메모리를 가장 많이 쓰는 프로세스 |
| [`wtf net`](RESOURCES.md#wtf-net) | 인터페이스, 게이트웨이, DNS, 오류, 수신 대기 포트 |
| [`wtf io`](RESOURCES.md#wtf-io) | 장치별 IO 속도, 압력, 멈춘 프로세스 |
| [`wtf who`](RESOURCES.md#wtf-who) | 로그인한 사용자, 최근 로그인, 실패한 인증 |
| [`wtf temp`](RESOURCES.md#wtf-temp) | /sys/class/hwmon에서 가져온 하드웨어 온도 |
| [`wtf info`](RESOURCES.md#wtf-info) | 한 페이지 스냅샷: 위의 모든 것을 한 번에 |
| [`wtf top`](RESOURCES.md#wtf-top) | 집중 프로세스 top: cpu/rss로 정렬, user/name으로 필터링 |
| [`wtf ports` / `wtf port N`](RESOURCES.md#wtf-ports) | 수신 대기 소켓; 포트 하나를 PID, exe, cwd까지 파고들기 |
| [`wtf docker [NAME]`](RESOURCES.md#wtf-docker) | 컨테이너 compose 디렉터리 + 이미지/컨테이너/로그 크기 |

### Output & configuration

| command | what it does |
|---------|--------------|
| [`wtf config`](CONFIG.md#wtf-config) | 적용된 설정 표시 / 주석이 달린 예시 출력 |
| [`wtf completion`](#install) | bash/zsh `<Tab>` 자동완성 스크립트 출력 |
| [machine output](OUTPUT.md) | `plain`/`json` 형식과 grep·awk·jq 쿡북 |

`wtftools`는
[`checkcrontab`](https://github.com/wachawo/checkcrontab)을 흡수하고 대체합니다 —
동일한 cron 검증기가 이제 `wtf crontab`에 들어 있습니다.

## Documentation

- [QUICKSTART.md](QUICKSTART.md) — 5분 온보딩과 치트 시트
- [AUDIT.md](AUDIT.md) — 상태 점검, 모니터링, 종료 코드, 전체 점검 목록
- [RESOURCES.md](RESOURCES.md) — 예시가 포함된 리소스별 보기
- [OUTPUT.md](OUTPUT.md) — `plain`/`json` 형식과 스크립팅 쿡북
- [CONFIG.md](CONFIG.md) — 설정 파일, 임계값, 점검 무시
- [ROADMAP.md](ROADMAP.md) — 계획된 것과 범위 밖인 것

## Compatibility

- Python 3.9+
- 리눅스 (systemd 배포판이 가장 잘 동작하는 환경이며, `systemctl` /
  `journalctl` / `psutil`이 없을 때는 우아하게 기능이 축소됩니다)
- 핵심 CLI에는 네트워크 접근이 필요 없습니다. 선택적 네트워크는
  `wtf explain --llm …`와 `wtf doctor --check-updates`에만 필요합니다

## From source

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
python3 wtf.py audit       # or run it without installing
```

## License

MIT
