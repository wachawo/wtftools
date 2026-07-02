# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> たった1つのコマンドで、いま Linux サーバーで何が起きているのかを把握できます。

[English](https://github.com/wachawo/wtftools/blob/main/README.md) | [Español](https://github.com/wachawo/wtftools/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/wtftools/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/wtftools/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/wtftools/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/wtftools/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/wtftools/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/wtftools/blob/main/docs/README_ZH.md) | **日本語** | [हिन्दी](https://github.com/wachawo/wtftools/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/wtftools/blob/main/docs/README_KR.md)

サーバーにログインして、何かおかしいと感じることがあります。10個もの
コマンド（`htop`、`df -h`、`journalctl`、`systemctl --failed`、…）を実行する代わりに、
たった1つを実行します。

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

緑は問題なし、黄色は確認が必要、赤は修正が必要です。`wtftools` は
**読み取り専用・依存関係なしの CLI**（Python 標準ライブラリのみ。`psutil` は
任意）で、山のような診断コマンドを1つの読みやすい答えに変えてくれます —
そしてパイプに渡せば機械可読な答えにもなります。

## できること

- **ヘルス監査** — 40 種類以上のチェック（disk、memory、swap、load、PSI、OOM kill、
  失敗ユニット、証明書の有効期限、SMART、温度、DNS、…）を
  緑／黄／赤のチェックリストとして表示。
- **リソースごとのビュー** — スイッチの `show` コマンドのように、一度に1つずつ
  確認します: `wtf disk`、`wtf cpu`、`wtf mem`、`wtf net`、`wtf docker`、…
- **インシデント切り分け** — `wtf problems`、`wtf events`、`wtf logs`、
  `wtf services <unit>`、`wtf explain`（任意でローカルまたはホスト型 LLM 経由）。
- **傾向とアラート** — `wtf daily`、スナップショット + `wtf diff`、cron アラート —
  監視スタックは不要です。
- **スクリプト対応** — すべてのコマンドに `plain`（タブ区切り）と `json` 出力があり、
  grep / awk / jq 向けに `schema_version` を持っています。
- **初心者にやさしい** — `--show-commands` を付けると、各ビューが置き換えている
  従来のコマンドが表示されるので、自分の手で学べます。

## インストール

```bash
pipx install wtftools          # recommended — works on any modern distro
pip install wtftools           # or classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

インストール後は `wtf` コマンドが使えます。シェルの rc ファイルに1行追加すると
`<Tab>` 補完を有効にできます。

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

はじめての方は [5分のクイックスタート](docs/QUICKSTART.md) からどうぞ。

## コマンド

フラグは `wtf <command> --help` で確認できます。各コマンドは、例付きの
リファレンスページにリンクしています。

### ヘルスと監視 — [docs/AUDIT.md](docs/AUDIT.md)

| command | what it does |
|---------|--------------|
| [`wtf` / `wtf audit`](docs/AUDIT.md#wtf-audit) | 何が正常で何が異常かを示す緑／黄／赤のチェックリスト |
| [`wtf problems`](docs/AUDIT.md#wtf-problems) | WARN+FAIL の行のみ |
| [`wtf daily`](docs/AUDIT.md#wtf-daily) | 朝のチェック: 監査 + 前回実行との差分 + イベント |
| [`wtf explain`](docs/AUDIT.md#wtf-explain) | 検出項目ごとの実行可能なアドバイス。`--llm` で LLM にパイプ |
| [`wtf events`](docs/AUDIT.md#wtf-events) | 時系列: 再起動、OOM kill、失敗ユニット、… |
| [`wtf logs`](docs/AUDIT.md#wtf-logs) | サービスごとにグループ化した最近の ERROR+ ジャーナルエントリ |
| [`wtf services`](docs/AUDIT.md#wtf-services) | 1つのユニットを詳細に: 状態、再起動、ポート、ジャーナル |
| [`wtf diff`](docs/AUDIT.md#wtf-diff) | 現在の状態を保存済みスナップショットと比較 |
| [`wtf history`](docs/AUDIT.md#wtf-history) | 保存済みの監査スナップショットを一覧 |
| [`wtf crontab`](docs/AUDIT.md#wtf-crontab) | システム + ユーザーごとの crontab を検証 |
| [`wtf doctor`](docs/AUDIT.md#wtf-doctor) | 自己診断: wtf が使えるツール／ファイルはどれか |

### リソースビュー — [docs/RESOURCES.md](docs/RESOURCES.md)

| command | what it does |
|---------|--------------|
| [`wtf disk [PATH]`](docs/RESOURCES.md#wtf-disk) | マウント概要。PATH を付けると最大のフォルダ。`--tree` で掘り下げ |
| [`wtf cpu`](docs/RESOURCES.md#wtf-cpu) | 負荷、iowait、プレッシャー、CPU 消費上位 |
| [`wtf mem`](docs/RESOURCES.md#wtf-mem) | RAM/swap、OOM kill、メモリ消費上位 |
| [`wtf net`](docs/RESOURCES.md#wtf-net) | インターフェース、ゲートウェイ、DNS、エラー、待ち受けポート |
| [`wtf io`](docs/RESOURCES.md#wtf-io) | デバイスごとの IO レート、プレッシャー、停止したプロセス |
| [`wtf who`](docs/RESOURCES.md#wtf-who) | ログイン中のユーザー、最近のログイン、認証失敗 |
| [`wtf temp`](docs/RESOURCES.md#wtf-temp) | /sys/class/hwmon からのハードウェア温度 |
| [`wtf info`](docs/RESOURCES.md#wtf-info) | 1ページのスナップショット: 上記すべてを一度に |
| [`wtf top`](docs/RESOURCES.md#wtf-top) | プロセスの絞り込み top: cpu/rss でソート、user/name でフィルタ |
| [`wtf ports` / `wtf port N`](docs/RESOURCES.md#wtf-ports) | 待ち受けソケット。1つのポートを掘り下げて PID、exe、cwd を表示 |
| [`wtf docker [NAME]`](docs/RESOURCES.md#wtf-docker) | コンテナの compose 作業ディレクトリ + イメージ/コンテナ/ログサイズ |

### 出力と設定

| command | what it does |
|---------|--------------|
| [`wtf config`](docs/CONFIG.md#wtf-config) | 有効な設定を表示／コメント付きの例を出力 |
| [`wtf completion`](#install) | bash/zsh の `<Tab>` 補完スクリプトを出力 |
| [machine output](docs/OUTPUT.md) | `plain`/`json` 形式と grep·awk·jq クックブック |

`wtftools` は
[`checkcrontab`](https://github.com/wachawo/checkcrontab) を取り込み、置き換えます —
同じ cron バリデーターが、いまは `wtf crontab` にあります。

## ドキュメント

- [QUICKSTART.md](docs/QUICKSTART.md) — 5分のオンボーディングとチートシート
- [AUDIT.md](docs/AUDIT.md) — ヘルスチェック、監視、終了コード、チェック項目の全リスト
- [RESOURCES.md](docs/RESOURCES.md) — 例付きのリソースごとのビュー
- [OUTPUT.md](docs/OUTPUT.md) — `plain`/`json` 形式とスクリプト向けクックブック
- [CONFIG.md](docs/CONFIG.md) — 設定ファイル、しきい値、チェックの無視

## 互換性

- Python 3.8+
- Linux（systemd ディストリビューションが最も快適に動作します。`systemctl` /
  `journalctl` / `psutil` が無い場合でも、ツールは緩やかに機能を縮退させます）
- コア CLI にネットワークアクセスは不要。任意のネットワーク利用は
  `wtf explain --llm …` と `wtf doctor --check-updates` のみ

## ソースから

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
python3 wtf.py audit       # or run it without installing
```

## ライセンス

MIT
