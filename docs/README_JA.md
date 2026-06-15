# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> たった1つのコマンドで、いま Linux サーバーで何が起きているのかを把握できます。

[English](https://github.com/wachawo/wtftools/blob/main/README.md) | [Español](https://github.com/wachawo/wtftools/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/wtftools/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/wtftools/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/wtftools/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/wtftools/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/wtftools/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/wtftools/blob/main/docs/README_ZH.md) | **日本語** | [हिन्दी](https://github.com/wachawo/wtftools/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/wtftools/blob/main/docs/README_KR.md)

サーバーにログインして、何かおかしいと感じることがあります。そんなとき、10個もの
コマンド（`htop`、`df -h`、`journalctl`、`systemctl --failed`、…）を実行する代わりに、
たった1つを実行します。

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

緑は問題なし、黄色は確認が必要、赤は修正が必要です。それだけです。

## インストール

```bash
pipx install wtftools          # recommended — works on any modern distro
```

`pipx` がない場合は、以下のいずれの方法でも動作します。

```bash
pip install wtftools           # classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

インストール後は `wtf` コマンドが使えます。試してみてください。`wtf`。

## 実際によく使うコマンド

```bash
wtf              # full health check — start here
wtf problems     # show ONLY what is wrong (warnings + failures)
wtf explain      # what to do about each problem, step by step
```

そのあとは、スイッチの `show` コマンドのように、リソースを1つずつ確認していきます。

```bash
wtf disk         # is there space? per-mount usage, inodes, read-only
wtf disk --tree  # WHAT is eating the space (largest directories)
wtf cpu          # load, iowait, top CPU consumers
wtf mem          # RAM/swap, OOM kills, top memory consumers
wtf net          # interfaces, IPs, gateway, DNS, listening ports
wtf io           # disk read/write rates, IO-stuck processes
wtf who          # who is logged in, recent logins, failed auth
```

例 — ディスクがいっぱいになりつつあるので、原因を突き止めます。

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

`wtf disk --tree` をパスなしで実行すると、最も使用率の高いマウントが自動的に選ばれます。

Linux を学習中ですか？ 任意のリソースコマンドに `--show-commands` を付けると、それが
置き換えている従来のコマンドも表示されるので、自分で実行してみることができます。

```
$ wtf cpu --show-commands
  ...
  equivalent commands:
    $ uptime
    $ top -bn1 | head
    $ ps aux --sort=-%cpu | head
```

## 何かが壊れているとき

```bash
wtf problems -v                 # every problem, with detail
wtf events --since 6            # timeline: reboots, OOM kills, failed units
wtf service nginx               # one service: state, restarts, ports, journal
wtf logs --since '2 hours ago'  # recent ERROR+ journal entries by service
wtf explain                     # actionable advice per finding
wtf explain --llm ollama        # or let a local LLM summarize it
```

## スクリプト向けの出力: grep、awk、jq

パイプに渡すと色は自動的に消えるので、ふつうの `grep` は常に機能します。
すべてのコマンドには機械可読の形式も用意されています — `plain`（タブ区切り、
ヘッダーなし）と `json` です。フラグはサブコマンドの前に置くこともできます。

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

リソースコマンドの JSON ペイロードには `schema_version` が含まれているので、
アップグレード後もスクリプトが動き続けます。

## 日々のルーチンと監視

朝のチェックを1つのコマンドで — 監査（audit）、前回実行からの変化、
そしてイベントのタイムラインを、先頭に1行の総括付きで表示します。

```bash
wtf daily                       # audit + diff vs yesterday + events
```

実行のたびにスナップショットを保存するので、翌日の `wtf daily` で差分が表示されます。
無人運用向けの crontab 行（問題があるときだけメールを送ります）。

```cron
0 8 * * * wtf daily --format json > /var/log/wtf-daily.json 2>&1 || mail -s "wtf $(hostname)" you@example.com < /var/log/wtf-daily.json
```

構成要素は個別にも利用できます。

```bash
wtf audit --brief               # one line — perfect for MOTD / SSH banner
wtf audit --save                # save a snapshot
wtf diff                        # what changed since the last snapshot
wtf history                     # list saved snapshots

# cron alerting without any monitoring stack:
wtf audit --alert 'mail -s "wtf $WTF_HOST" you@example.com'
wtf audit --alert-on warn --alert 'curl -X POST $SLACK_WEBHOOK -d @-'
```

終了コードは CI／cron に適しています。

| コード | 意味                                              |
|------|--------------------------------------------------|
| 0    | すべて正常                                          |
| 1    | `--strict` での警告、または crontab エラー            |
| 2    | 監査で `[FAIL]` を検出                              |
| 130  | 中断（Ctrl-C）                                     |

## すべてのサブコマンド

| コマンド             | 機能                                                         |
|---------------------|-------------------------------------------------------------|
| `wtf` / `wtf audit` | 緑／黄／赤のチェックリスト: 何が正常で何が異常かを表示          |
| `wtf problems`      | WARN+FAIL の行のみ                                           |
| `wtf daily`         | 朝のチェック: 監査 + 前回実行との差分 + イベント                |
| `wtf explain`       | チェックごとの実行可能なアドバイス。`--llm` で LLM にパイプ      |
| `wtf disk`          | マウントごとの使用率。`--tree` で最大のディレクトリを表示        |
| `wtf cpu`           | 負荷、iowait、プレッシャー、CPU 消費上位                       |
| `wtf mem`           | RAM/swap、OOM kill、メモリ消費上位                            |
| `wtf net`           | インターフェース、ゲートウェイ、DNS、エラー、待ち受けポート       |
| `wtf io`            | デバイスごとの IO レート、プレッシャー、停止したプロセス          |
| `wtf who`           | ログイン中のユーザー、最近のログイン、認証失敗                   |
| `wtf info`          | 1ページのスナップショット: 上記すべてを一度に                   |
| `wtf top`           | プロセスの絞り込み top: cpu/rss でソート、user/name でフィルタ  |
| `wtf ports`         | 所有 PID/ユーザー/コマンド付きの待ち受けソケット                 |
| `wtf service NAME`  | 1つのサービスを詳細に: 状態、再起動、メモリ、ポート、ジャーナル   |
| `wtf logs`          | サービスごとにグループ化した最近の ERROR+ ジャーナルエントリ      |
| `wtf events`        | 時系列のタイムライン: 再起動、OOM、失敗ユニット、…              |
| `wtf history`       | 保存済みの監査スナップショットを一覧（作成は `wtf audit --save`）|
| `wtf diff`          | 現在の状態を保存済みスナップショットと比較                       |
| `wtf crontab`       | 標準の全 crontab 配置 + ユーザーごとの crontab を検証           |
| `wtf doctor`        | 自己診断: wtftools が実際に使えるツールはどれか                 |
| `wtf config`        | 有効な設定を表示／例を出力                                     |

`wtftools` は
[`checkcrontab`](https://github.com/wachawo/checkcrontab) を取り込み、置き換えます。
同じ cron バリデーターが、いまは `wtf crontab` にあります。

## 高度な監査オプション

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

### 組み込みチェック

uptime · system state · load average · CPU iowait · PSI cpu/memory/io ·
TCP retransmits · memory · swap · disk (per mount) · inodes ·
read-only mounts · failed systemd units · enabled-but-down services ·
restart loops · network errors · conntrack · journal disk usage · zombies ·
D-state processes · OOM kills · kernel errors · kernel taint · cert expiry ·
open file descriptors · process count · failed auth · time sync ·
pending updates · reboot required · cron daemon · crontab syntax · docker ·
hw temperatures · disk SMART · DNS · HTTP/TCP probes · fail2ban.

## 設定

しきい値と無視設定は、以下のいずれかにある INI ファイルで管理します。

- `/etc/wtftools/config.ini`
- `/etc/wtf/config.ini`
- `~/.config/wtftools/config.ini`

完全にコメント付きのテンプレートは `wtf config --example` で確認できます。主な項目は次のとおりです。

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

## 互換性

- Python 3.8+
- Linux（systemd ディストリビューションが最も快適に動作します。`systemctl` /
  `journalctl` / `psutil` が無い場合でも、ツールは緩やかに機能を縮退させます）
- コア CLI にネットワークアクセスは不要
- 任意のネットワーク利用: `wtf explain --llm claude/openai`、`wtf doctor --check-updates`

## ソースから

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
# or test without installing:
python3 wtf.py audit
```

## ライセンス

MIT
