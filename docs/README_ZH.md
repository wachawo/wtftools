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
[FAIL] failed systemd units    1 failed unit(s)

  Summary: 12 ok · 1 warn · 1 fail · 2 skip
```

绿色表示正常，黄色需要留意，红色需要修复。`wtftools` 是一个
**只读、无依赖的 CLI**（仅依赖 Python 标准库；`psutil` 为可选），
它把一大堆诊断命令变成一个可读的答案——当你用管道时，还会给出
一个机器可读的答案。

## 它能做什么

- **健康审计** —— 40 多项检查（磁盘、内存、swap、负载、PSI、OOM kill、
  失败的单元、证书过期、SMART、温度、DNS ……），以
  绿 / 黄 / 红 检查清单的形式呈现。
- **按资源查看** —— 一次只问一件事，就像交换机上的 `show` 命令：
  `wtf disk`、`wtf cpu`、`wtf mem`、`wtf net`、`wtf docker` ……
- **故障分诊** —— `wtf problems`、`wtf events`、`wtf logs`、
  `wtf services <unit>`、`wtf explain`（可选择经由本地或托管的 LLM）。
- **趋势与告警** —— `wtf daily`、快照 + `wtf diff`、cron 告警 ——
  无需任何监控栈。
- **可脚本化** —— 每条命令都支持 `-f json`，而 `-f plain`（制表符分隔）仅用于资源和审计视图；
  JSON 带有 `schema_version`，使脚本在升级后仍可用 —— 可用于 grep / awk / jq。
- **新手友好** —— `--show-commands` 会打印每个视图所替代的经典命令，
  方便你自己动手学习。

## 安装

```bash
pipx install wtftools          # recommended — works on any modern distro
pip install wtftools           # or classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i python3-wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

安装后你就拥有了 `wtf` 命令。在你的 shell rc 中加上一行即可启用
`<Tab>` 自动补全：

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

第一次使用？从 [5 分钟快速入门](QUICKSTART.md) 开始。

## 命令

运行 `wtf <command> --help` 查看各项标志。每条命令都链接到带示例的
参考页面。

### 健康与监控 —— [docs/AUDIT.md](AUDIT.md)

| command | 作用 |
|---------|--------------|
| [`wtf` / `wtf audit`](AUDIT.md#wtf-audit) | 绿/黄/红检查清单：什么正常、什么不正常 |
| [`wtf problems`](AUDIT.md#wtf-problems) | 仅显示 WARN+FAIL 行 |
| [`wtf daily`](AUDIT.md#wtf-daily) | 早晨检查：审计 + 与上次运行的差异 + 事件 |
| [`wtf explain`](AUDIT.md#wtf-explain) | 针对每项检查给出可操作建议；用 `--llm` 传给 LLM |
| [`wtf events`](AUDIT.md#wtf-events) | 时间线：重启、OOM kill、失败的单元…… |
| [`wtf logs`](AUDIT.md#wtf-logs) | 按服务分组的近期 ERROR+ 日志条目 |
| [`wtf services`](AUDIT.md#wtf-services) | 深入查看某个单元：状态、重启、端口、日志 |
| [`wtf diff`](AUDIT.md#wtf-diff) | 将当前状态与已保存的快照进行比较 |
| [`wtf history`](AUDIT.md#wtf-history) | 列出已保存的审计快照 |
| [`wtf crontab`](AUDIT.md#wtf-crontab) | 校验系统级 + 每个用户的 crontab |
| [`wtf doctor`](AUDIT.md#wtf-doctor) | 自我诊断：wtf 实际能使用哪些工具/文件 |

### 资源视图 —— [docs/RESOURCES.md](RESOURCES.md)

| command | 作用 |
|---------|--------------|
| [`wtf disk [PATH]`](RESOURCES.md#wtf-disk) | 挂载点概览；带 PATH 时显示最大的文件夹；`--tree` 逐层深入 |
| [`wtf cpu`](RESOURCES.md#wtf-cpu) | 负载、iowait、压力、CPU 占用最高的进程 |
| [`wtf mem`](RESOURCES.md#wtf-mem) | RAM/swap、OOM kill、内存占用最高的进程 |
| [`wtf net`](RESOURCES.md#wtf-net) | 网络接口、网关、DNS、错误、监听端口 |
| [`wtf io`](RESOURCES.md#wtf-io) | 各设备的 IO 速率、压力、卡住的进程 |
| [`wtf who`](RESOURCES.md#wtf-who) | 已登录用户、近期登录、失败的认证 |
| [`wtf temp`](RESOURCES.md#wtf-temp) | 来自 /sys/class/hwmon 的硬件温度 |
| [`wtf info`](RESOURCES.md#wtf-info) | 一页式快照：以上全部一次性呈现 |
| [`wtf top`](RESOURCES.md#wtf-top) | 聚焦的进程 top：按 cpu/rss 排序，按用户/名称过滤 |
| [`wtf ports` / `wtf port N`](RESOURCES.md#wtf-ports) | 监听套接字；深入查看某个端口，得到 PID、exe、cwd |
| [`wtf docker [NAME]`](RESOURCES.md#wtf-docker) | 容器 compose 目录 + 镜像/容器/日志大小 |

### 输出与配置

| command | 作用 |
|---------|--------------|
| [`wtf config`](CONFIG.md#wtf-config) | 显示生效的配置 / 打印带注释的示例 |
| [`wtf completion`](#install) | 打印 bash/zsh `<Tab>` 自动补全脚本 |
| [machine output](OUTPUT.md) | `plain`/`json` 格式以及 grep·awk·jq 实用手册 |

`wtftools` 吸收并取代了
[`checkcrontab`](https://github.com/wachawo/checkcrontab) —— 同一个 cron
校验器现在位于 `wtf crontab`。

## 文档

- [QUICKSTART.md](QUICKSTART.md) —— 5 分钟上手与速查表
- [AUDIT.md](AUDIT.md) —— 健康检查、监控、退出码、完整检查列表
- [RESOURCES.md](RESOURCES.md) —— 带示例的按资源视图
- [OUTPUT.md](OUTPUT.md) —— `plain`/`json` 格式与脚本实用手册
- [CONFIG.md](CONFIG.md) —— 配置文件、阈值、忽略检查

## 兼容性

- Python 3.8+
- Linux（systemd 发行版是最理想的运行环境；当缺少
  `systemctl` / `journalctl` / `psutil` 时，工具会优雅降级）
- 核心 CLI 无需网络访问；仅 `wtf explain --llm …` 和
  `wtf doctor --check-updates` 需要可选的网络

## 从源码安装

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
python3 wtf.py audit       # or run it without installing
```

## 许可证

MIT
