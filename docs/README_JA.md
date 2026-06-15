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

タブ補完（任意）— シェルの rc ファイルに1行追加して `<Tab>` を押します。

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

詳しい手順は `wtf completion` を引数なしで実行すると表示されます。

## 実際によく使うコマンド

```bash
wtf              # full health check — start here
wtf problems     # show ONLY what is wrong (warnings + failures)
wtf explain      # what to do about each problem, step by step
```

そのあとは、スイッチの `show` コマンドのように、リソースを1つずつ確認していきます。

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

`wtf disk` をパスなしで実行するとマウントの概要になります — フルパス、使用量／合計、
パーセント、そして使用率バーが表示されます。

```
$ wtf disk
# DISK
  /            1.4TB / 1.8TB   79%  [████████████████····]  ext4
  /boot      216.4MB / 1.9GB   11%  [██··················]  ext4
  /mnt/Data    5.3TB / 13.9TB  38%  [████████············]  ext4
```

例 — ディスクがいっぱいになりつつあるので、原因を突き止めます。`wtf disk <path>` は、
その直下のフォルダを大きい順に一覧表示します（`path/  size  % of root  depth`）。

```
$ wtf disk /var
# DISK USAGE /var
  lib/      15.0GB  75%  0
  log/       3.1GB  16%  0
  cache/     1.2GB   6%  0
```

`--tree` を付けると、最大のフォルダを階層ごとに掘り下げます（`--depth`、デフォルトは3）。
`--tree N` は各階層で最大 N 件を開きます。末尾の数字は深さを表します。

```
$ wtf disk / --tree
# DISK USAGE /
  home/                 1021.0GB  70%  0
  home/wachawo/         1021.0GB  70%  1
  home/wachawo/myApps/   429.7GB  30%  2
  usr/                   207.9GB  14%  0
  var/                   206.5GB  14%  0
```

`wtf disk --tree` をパスなしで実行すると、最も使用率の高いマウントを掘り下げます。
root 所有のフォルダを読むには `sudo` を付けて実行してください。`# DISK` マウント概要
（パスなし）は変更ありません。

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

### ポートを使っているのは誰か？

`wtf port <N>`（または `wtf ports <N>`）は、どのプロセスがそのポートを保持しているのかを
表示します — PID、その背後にある正確な実行ファイル（`lsof` + `/proc` 経由）、そして
それが動作しているディレクトリです。

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

他のユーザーが所有するプロセスも見るには `sudo` を付けて実行してください。

### このコンテナはどこで起動されたのか？

`wtf docker <name>` は、「どのフォルダで `docker compose up` を実行したのか？」という
疑問に、コンテナのラベルから直接答えます — さらに、どれだけディスクを消費しているか
（イメージレイヤー、書き込み可能なコンテナレイヤー、そして json ログ）も示します。

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

`wtf docker` を名前なしで実行すると、実行中のすべてのコンテナを、サイズの列と作業
ディレクトリ、そして TOTAL 行付きで一覧表示します。

```
$ sudo wtf docker
# DOCKER
  NAME         STATUS       IMAGE   CONTNR     LOGS  WORKING DIR
  myapp_web    running      164MB    267MB   53.8MB  /home/deploy/myapp
  myapp_db     running      276MB     63B    4.02MB  /home/deploy/myapp
  TOTAL                     440MB    267MB   57.8MB
  note: IMAGE total is logical (images share layers); real disk 9.2GB, 1.1GB reclaimable — docker system df; logs cap with max-size; decimal units, like docker
```

サイズは十進単位（1GB = 1000MB）を使うので、`docker container ls --size` と一致します。
行ごとの IMAGE は、そのイメージの完全な論理サイズ（`docker` が *virtual* サイズと呼ぶもの）
です。IMAGE の合計はイメージ ID で重複排除されるので、多くのコンテナで共有された1つの
イメージは、コンテナごとに数えられるのではなく、一度だけ数えられます。**しかし**、異なる
イメージでもディスク上ではベースレイヤーを共有するので、重複排除後の合計ですら実際の
使用量を過大に見積もります。note 行は、`docker system df` から直接得た、真にレイヤー
重複排除されたディスク容量を示します。CONTNR（書き込み可能レイヤー）と LOGS はコンテナ
ごとなので、それらの合計は正確です。ログサイズの取得には `/var/lib/docker` 配下への
読み取りアクセスが必要です — `sudo` で実行してください。そうでないと `?` と表示されます。

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
wtf disk /var --format plain | awk -F'\t' 'NR==1 {print $3, $1}'   # biggest folder: path, bytes
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

| command             | 機能                                                         |
|---------------------|-------------------------------------------------------------|
| `wtf` / `wtf audit` | 緑／黄／赤のチェックリスト: 何が正常で何が異常かを表示          |
| `wtf problems`      | WARN+FAIL の行のみ                                           |
| `wtf daily`         | 朝のチェック: 監査 + 前回実行との差分 + イベント                |
| `wtf explain`       | チェックごとの実行可能なアドバイス。`--llm` で LLM にパイプ      |
| `wtf disk [PATH]`   | マウント概要。PATH を付けると最大のフォルダ。`--tree` で掘り下げ |
| `wtf cpu`           | 負荷、iowait、プレッシャー、CPU 消費上位                       |
| `wtf mem`           | RAM/swap、OOM kill、メモリ消費上位                            |
| `wtf net`           | インターフェース、ゲートウェイ、DNS、エラー、待ち受けポート       |
| `wtf io`            | デバイスごとの IO レート、プレッシャー、停止したプロセス          |
| `wtf who`           | ログイン中のユーザー、最近のログイン、認証失敗                   |
| `wtf temp`          | /sys/class/hwmon センサーからのハードウェア温度                |
| `wtf info`          | 1ページのスナップショット: 上記すべてを一度に                   |
| `wtf top`           | プロセスの絞り込み top: cpu/rss でソート、user/name でフィルタ  |
| `wtf ports`         | 所有 PID/ユーザー/コマンド付きの待ち受けソケット                 |
| `wtf port NUM`      | 1つのポートを掘り下げ: PID、実行ファイル、作業ディレクトリ        |
| `wtf docker [NAME]` | コンテナの compose 作業ディレクトリ + イメージ/コンテナ/ログサイズ |
| `wtf service NAME`  | 1つのサービスを詳細に: 状態、再起動、メモリ、ポート、ジャーナル   |
| `wtf logs`          | サービスごとにグループ化した最近の ERROR+ ジャーナルエントリ      |
| `wtf events`        | 時系列のタイムライン: 再起動、OOM、失敗ユニット、…              |
| `wtf history`       | 保存済みの監査スナップショットを一覧（作成は `wtf audit --save`）|
| `wtf diff`          | 現在の状態を保存済みスナップショットと比較                       |
| `wtf crontab`       | 標準の全 crontab 配置 + ユーザーごとの crontab を検証           |
| `wtf doctor`        | 自己診断: wtftools が実際に使えるツールはどれか                 |
| `wtf config`        | 有効な設定を表示／例を出力                                     |
| `wtf completion`    | bash/zsh の `<Tab>` 補完スクリプトを出力（または設定ヘルプ）     |

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
