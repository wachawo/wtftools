# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> 一条命令即可查看你的 Linux 服务器此刻的运行状况。

[English](https://github.com/wachawo/wtftools/blob/main/README.md) | [Español](https://github.com/wachawo/wtftools/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/wtftools/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/wtftools/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/wtftools/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/wtftools/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/wtftools/blob/main/docs/README_RU.md) | **中文** | [日本語](https://github.com/wachawo/wtftools/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/wtftools/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/wtftools/blob/main/docs/README_KR.md)

你登录到一台服务器，感觉有些不对劲。你不必再运行十几条命令
（`htop`、`df -h`、`journalctl`、`systemctl --failed` ……），只需运行一条：

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

绿色表示正常，黄色需要留意，红色需要修复。就这么简单。

## 安装

```bash
pipx install wtftools          # recommended — works on any modern distro
```

没有 `pipx`？以下任意方式都可以：

```bash
pip install wtftools           # classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

安装后你就拥有了 `wtf` 命令。试一下：`wtf`。

## 你真正会用到的命令

```bash
wtf              # full health check — start here
wtf problems     # show ONLY what is wrong (warnings + failures)
wtf explain      # what to do about each problem, step by step
```

然后逐个查询资源，就像交换机上的 `show` 命令一样：

```bash
wtf disk         # is there space? per-mount usage, inodes, read-only
wtf disk --tree  # WHAT is eating the space (largest directories)
wtf cpu          # load, iowait, top CPU consumers
wtf mem          # RAM/swap, OOM kills, top memory consumers
wtf net          # interfaces, IPs, gateway, DNS, listening ports
wtf io           # disk read/write rates, IO-stuck processes
wtf who          # who is logged in, recent logins, failed auth
```

示例——磁盘快满了，找出罪魁祸首：

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

`wtf disk --tree` 不带路径时会自动选择最满的挂载点。

正在学习 Linux？给任意资源命令加上 `--show-commands`，它还会
打印出所替代的经典命令，方便你自己运行：

```
$ wtf cpu --show-commands
  ...
  equivalent commands:
    $ uptime
    $ top -bn1 | head
    $ ps aux --sort=-%cpu | head
```

## 当出现故障时

```bash
wtf problems -v                 # every problem, with detail
wtf events --since 6            # timeline: reboots, OOM kills, failed units
wtf service nginx               # one service: state, restarts, ports, journal
wtf logs --since '2 hours ago'  # recent ERROR+ journal entries by service
wtf explain                     # actionable advice per finding
wtf explain --llm ollama        # or let a local LLM summarize it
```

## 面向脚本的输出：grep、awk、jq

当你使用管道时颜色会自动消失，因此普通的 `grep` 始终有效。
每条命令还提供机器可读的格式——`plain`（制表符分隔，无表头）
和 `json`。该标志也可以放在子命令之前：

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

资源命令的 JSON 负载带有 `schema_version`，因此你的脚本在
升级后仍能正常运行。

## 日常例行检查与监控

一条命令完成早晨检查——审计、自上次运行以来的变化，
以及事件时间线，并在顶部给出一行结论：

```bash
wtf daily                       # audit + diff vs yesterday + events
```

它在每次运行时都会保存一份快照，因此明天的 `wtf daily` 会显示差异。
用于无人值守的 crontab 行（仅在出现问题时发送邮件）：

```cron
0 8 * * * wtf daily --format json > /var/log/wtf-daily.json 2>&1 || mail -s "wtf $(hostname)" you@example.com < /var/log/wtf-daily.json
```

这些构建模块也可单独使用：

```bash
wtf audit --brief               # one line — perfect for MOTD / SSH banner
wtf audit --save                # save a snapshot
wtf diff                        # what changed since the last snapshot
wtf history                     # list saved snapshots

# cron alerting without any monitoring stack:
wtf audit --alert 'mail -s "wtf $WTF_HOST" you@example.com'
wtf audit --alert-on warn --alert 'curl -X POST $SLACK_WEBHOOK -d @-'
```

退出码对 CI/cron 友好：

| 退出码 | 含义                                              |
|------|--------------------------------------------------|
| 0    | 一切正常                                           |
| 1    | 使用 `--strict` 时出现警告，或 crontab 错误         |
| 2    | 审计发现了 `[FAIL]`                                |
| 130  | 被中断（Ctrl-C）                                   |

## 所有子命令

| 命令                 | 作用                                                        |
|---------------------|-------------------------------------------------------------|
| `wtf` / `wtf audit` | 绿/黄/红检查清单：什么正常、什么不正常                          |
| `wtf problems`      | 仅显示 WARN+FAIL 行                                          |
| `wtf daily`         | 早晨检查：审计 + 与上次运行的差异 + 事件                       |
| `wtf explain`       | 针对每项检查给出可操作建议；用 `--llm` 传给 LLM                |
| `wtf disk`          | 各挂载点用量；`--tree` 显示最大的目录                         |
| `wtf cpu`           | 负载、iowait、压力、CPU 占用最高的进程                        |
| `wtf mem`           | RAM/swap、OOM kill、内存占用最高的进程                        |
| `wtf net`           | 网络接口、网关、DNS、错误、监听端口                            |
| `wtf io`            | 各设备的 IO 速率、压力、卡住的进程                            |
| `wtf who`           | 已登录用户、近期登录、失败的认证                              |
| `wtf info`          | 一页式快照：以上全部一次性呈现                                |
| `wtf top`           | 聚焦的进程 top：按 cpu/rss 排序，按用户/名称过滤              |
| `wtf ports`         | 监听套接字及其所属 PID/用户/命令                              |
| `wtf service NAME`  | 深入查看某个服务：状态、重启、内存、端口、日志                 |
| `wtf logs`          | 按服务分组的近期 ERROR+ 日志条目                              |
| `wtf events`        | 按时间顺序的时间线：重启、OOM、失败的单元……                   |
| `wtf history`       | 列出已保存的审计快照（用 `wtf audit --save` 创建）            |
| `wtf diff`          | 将当前状态与已保存的快照进行比较                              |
| `wtf crontab`       | 校验所有标准 crontab 位置 + 每个用户的 crontab                |
| `wtf doctor`        | 自我诊断：wtftools 实际能使用哪些工具                         |
| `wtf config`        | 显示生效的配置 / 打印示例                                     |

`wtftools` 吸收并取代了
[`checkcrontab`](https://github.com/wachawo/checkcrontab)——同一个 cron
校验器现在位于 `wtf crontab`。

## 高级审计选项

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

### 内置检查项

uptime · system state · load average · CPU iowait · PSI cpu/memory/io ·
TCP retransmits · memory · swap · disk (per mount) · inodes ·
read-only mounts · failed systemd units · enabled-but-down services ·
restart loops · network errors · conntrack · journal disk usage · zombies ·
D-state processes · OOM kills · kernel errors · kernel taint · cert expiry ·
open file descriptors · process count · failed auth · time sync ·
pending updates · reboot required · cron daemon · crontab syntax · docker ·
hw temperatures · disk SMART · DNS · HTTP/TCP probes · fail2ban.

## 配置

阈值和忽略项保存在 INI 文件中，可位于以下任意位置：

- `/etc/wtftools/config.ini`
- `/etc/wtf/config.ini`
- `~/.config/wtftools/config.ini`

运行 `wtf config --example` 可获得带完整注释的模板。要点如下：

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

## 兼容性

- Python 3.8+
- Linux（systemd 发行版是最理想的运行环境；当缺少
  `systemctl` / `journalctl` / `psutil` 时，工具会优雅降级）
- 核心 CLI 无需网络访问
- 可选网络功能：`wtf explain --llm claude/openai`、`wtf doctor --check-updates`

## 从源码安装

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
# or test without installing:
python3 wtf.py audit
```

## 许可证

MIT
