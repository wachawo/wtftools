# wtftools — 5-minute quickstart

## Install

```bash
pip install wtftools           # core
pip install wtftools[full]     # + psutil (recommended)
```

Or `apt install wtftools` (see README for the .deb workflow).

## First 60 seconds

```bash
wtf                # default audit — green/yellow/red checklist
wtf audit --brief  # one-line summary, MOTD-friendly
wtf info           # host snapshot (top procs, disks, mem)
wtf doctor         # which tools are actually available
```

## Incident triage flow

Something is broken — start here:

```bash
wtf                                     # any FAIL/WARN? what?
wtf audit --only problem -v             # detail on every problem
wtf events --since 6                    # last 6h: reboots, OOMs, …
wtf services <unit>                     # drill into one systemd service
wtf logs --since '2 hours ago'          # ERROR+ journal entries
wtf explain                             # actionable suggestions per finding
wtf explain --llm ollama                # or pipe through an LLM
```

## Per-host configuration

Override thresholds for this server:

```bash
sudo mkdir -p /etc/wtftools
wtf config --example | sudo tee /etc/wtftools/config.ini
sudo nano /etc/wtftools/config.ini      # raise/lower swap_warn, disk_fail, etc.
```

## SSH login banner

```bash
sudo wtf motd-install                   # one line at each ssh login
# or full setup:
sudo wtf init                           # interactive: config + motd + cron
```

## Fleet / multi-host

On each host:

```bash
sudo cp scripts/wtfd.service /etc/systemd/system/
sudo systemctl enable --now wtfd
```

Then anywhere on your network:

```bash
wtf fleet --hosts h1:8765,h2:8765,h3:8765
wtf fleet --hosts ... --problem-only       # hide healthy hosts
wtf fleet --hosts ... --run-now            # kick a fresh audit on each peer first
wtf fleet --hosts ... --watch 30           # auto-refresh
wtf compare h1:8765 h2:8765 --only-drift   # config-drift between two boxes
```

For Prometheus / Grafana:

```bash
wtf audit --format prometheus > /var/lib/node_exporter/wtf.prom
# or scrape wtfd directly:
#   scrape_configs:
#     - job_name: wtfd
#       static_configs: [{ targets: ['host1:8765', 'host2:8765'] }]
#       metrics_path: /audit.prom
```

## Custom checks

Drop an executable script at `/etc/wtf/checks.d/<name>.sh`:

```bash
#!/bin/sh
set -e
if [ -f /var/run/my-flag ]; then
    echo "/var/run/my-flag still present"
    exit 1     # warn
fi
echo "flag absent"
exit 0         # ok
```

Exit codes: `0=ok / 1=warn / 2=fail / 77=skip`. stdout becomes the message.

See `examples/plugins/` for four production-ready examples
(TLS cert probe, PostgreSQL connection count, Redis memory, disk-write
latency).

## Cheat sheet

| I want to…                                | Command                                   |
|-------------------------------------------|-------------------------------------------|
| Quick health check                        | `wtf`                                     |
| Only show problems                        | `wtf audit --only problem`                |
| Run one check                             | `wtf audit --check disks`                 |
| List all checks                           | `wtf audit --list-checks`                 |
| What's screaming in the logs?             | `wtf logs --since '2 hours ago'`          |
| Timeline of recent events                 | `wtf events --since 12`                   |
| Drill into one service                    | `wtf services nginx`                      |
| Save current state for later diff         | `wtf audit --save`                        |
| What changed since the last snapshot?     | `wtf diff`                                |
| Fleet status, one screen                  | `wtf fleet --hosts h1,h2,h3 --problem-only` |
| Live fleet dashboard                      | `wtf fleet --hosts ... --watch 30`        |
| Diff two hosts                            | `wtf compare a:8765 b:8765 --only-drift`  |
| MOTD setup                                | `sudo wtf motd-install`                   |
| Alert on failure                          | `wtf audit --alert 'mail ...'`            |
| Email-ready report                        | `wtf audit --format html -o report.html`  |
| Run as service for fleet API              | `wtfd --listen 0.0.0.0:8765 --save`       |

## Next steps

- Full reference: `wtf --help` and `README.md`
- Architecture / configuration: `README.md` sections «Config», «Plugins», «Daemon mode»
- Contribute: `CONTRIBUTING.md`
