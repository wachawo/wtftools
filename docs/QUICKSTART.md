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
wtf problems       # only WARN+FAIL rows
wtf info           # host snapshot (top procs, disks, mem)
wtf doctor         # which tools are actually available
```

## Incident triage flow

Something is broken — start here:

```bash
wtf                                     # any FAIL/WARN? what?
wtf problems -v                         # detail on every problem
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

Drop a 3-line script into `/etc/update-motd.d/99-wtf-brief`:

```bash
sudo tee /etc/update-motd.d/99-wtf-brief <<'EOF' >/dev/null
#!/bin/sh
exec /usr/bin/env wtf audit --brief --no-color 2>/dev/null || true
EOF
sudo chmod +x /etc/update-motd.d/99-wtf-brief
```

## Save / diff state over time

```bash
wtf audit --save          # save snapshot under ~/.cache/wtftools/
wtf history               # list saved snapshots
wtf diff                  # what's changed since the last save?
wtf diff --snapshot 5     # vs 5 snapshots ago
```

## Custom checks (plugins)

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

See `examples/plugins/` for five production-ready examples (TLS cert probe,
PostgreSQL connection count, Redis memory, disk-write latency, HTTP health).
Full guide in [PLUGIN_GUIDE.md](PLUGIN_GUIDE.md).

## Cheat sheet

| I want to…                                | Command                                   |
|-------------------------------------------|-------------------------------------------|
| Quick health check                        | `wtf`                                     |
| Only show problems                        | `wtf problems`                            |
| Run one check                             | `wtf audit --check disks`                 |
| List all checks                           | `wtf audit --list-checks`                 |
| What's screaming in the logs?             | `wtf logs --since '2 hours ago'`          |
| Timeline of recent events                 | `wtf events --since 12`                   |
| Drill into one service                    | `wtf services nginx`                      |
| Save current state for later diff         | `wtf audit --save`                        |
| What changed since the last snapshot?     | `wtf diff`                                |
| Alert on failure                          | `wtf audit --alert 'mail ...'`            |
| Email-ready report                        | `wtf audit --format html -o report.html`  |

## Next steps

- Full reference: `wtf --help` and the project `README.md`
- Architecture / configuration: `README.md` sections «Config», «Plugins»
- Contribute: `CONTRIBUTING.md`
