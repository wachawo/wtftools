# wtf — configuration

Thresholds and ignore rules for wtftools live in a simple INI file. Part of [wtftools](../README.md).

## Config file locations

wtftools reads INI files (stdlib `configparser`, no extra dependencies) from
the following paths, in order. Later files override values from earlier ones,
so a per-user file wins over a system-wide one:

- `/etc/wtftools/config.ini`
- `/etc/wtf/config.ini`
- `~/.config/wtftools/config.ini` (honors `$XDG_CONFIG_HOME` if set)

Passing `--config PATH` stacks an extra file on top of the default search
paths, so its values take precedence over everything else.

You only need to set the keys you want to change — anything you omit keeps its
built-in default.

## wtf config

```bash
wtf config              # show effective values and which files were loaded
wtf config --example    # print a fully-commented example config
wtf config --format json
```

`wtf config` prints the configuration as wtftools actually sees it (defaults
overlaid with whatever your INI files set) plus the config paths in play —
useful for confirming a file was found and parsed.

`wtf config --example` prints a ready-to-edit template. Save it to one of the
locations above:

```bash
wtf config --example > ~/.config/wtftools/config.ini
```

## Thresholds

All thresholds live under the `[thresholds]` section. Most come in a
`*_warn` / `*_fail` pair: a check turns yellow at or above the warn level and
red at or above the fail level.

| Key                 | Default            | Meaning                                            |
|---------------------|--------------------|----------------------------------------------------|
| `disk_warn`         | `85`               | Disk usage % warning                               |
| `disk_fail`         | `95`               | Disk usage % failure                               |
| `mem_warn`          | `85`               | Memory usage % warning                             |
| `mem_fail`          | `95`               | Memory usage % failure                             |
| `swap_warn`         | `30`               | Swap usage % warning                               |
| `swap_fail`         | `70`               | Swap usage % failure                               |
| `load_warn`         | `1.0`              | Load average / CPU count ratio, warning            |
| `load_fail`         | `2.0`              | Load average / CPU count ratio, failure            |
| `iowait_warn`       | `10`               | CPU iowait % warning                                |
| `iowait_fail`       | `30`               | CPU iowait % failure                                |
| `psi_warn`          | `10`               | Pressure stall information (PSI) % warning          |
| `psi_fail`          | `30`               | Pressure stall information (PSI) % failure          |
| `fd_warn`           | `60`               | Open file descriptors as % of `fs.file-max`, warn  |
| `fd_fail`           | `80`               | Open file descriptors as % of `fs.file-max`, fail  |
| `pid_warn`          | `50`               | Process count as % of `pid_max`, warning           |
| `pid_fail`          | `80`               | Process count as % of `pid_max`, failure           |
| `tcp_retrans_warn`  | `1.0`              | TCP retransmit % (1 s sample) warning              |
| `tcp_retrans_fail`  | `5.0`              | TCP retransmit % (1 s sample) failure              |
| `conntrack_warn`    | `70`               | Conntrack table usage % warning                    |
| `conntrack_fail`    | `90`               | Conntrack table usage % failure                    |
| `auth_warn`         | `50`               | Failed auth attempts in the look-back window, warn |
| `restart_warn`      | `3`                | Service `NRestarts` warning                        |
| `restart_fail`      | `10`               | Service `NRestarts` failure                        |
| `journal_warn_gb`   | `4.0`              | systemd journal disk usage (GB) warning            |
| `journal_fail_gb`   | `16.0`             | systemd journal disk usage (GB) failure            |
| `temp_warn_c`       | `75.0`             | Hardware temperature (°C) warning                  |
| `temp_fail_c`       | `90.0`             | Hardware temperature (°C) failure                  |
| `cert_warn_days`    | `30`               | TLS certificate expiry warning (days left)         |
| `cert_fail_days`    | `7`                | TLS certificate expiry failure (days left)         |

A few more keys tune probes and execution rather than warn/fail levels:

| Key                 | Default                       | Meaning                                  |
|---------------------|-------------------------------|------------------------------------------|
| `dns_probe_hosts`   | `google.com,cloudflare.com`   | Hosts resolved by the DNS check          |
| `dns_probe_timeout` | `2.0`                         | DNS probe timeout (seconds)              |
| `http_probes`       | (empty)                       | HTTP endpoints to probe                  |
| `tcp_probes`        | (empty)                       | host:port endpoints to probe             |
| `probe_timeout`     | `3.0`                         | HTTP/TCP probe timeout (seconds)         |
| `probe_slow_ms`     | `1000.0`                      | Probe latency considered slow (ms)       |
| `fleet_hosts`       | (empty)                       | Hosts for fleet-wide audits              |
| `check_timeout`     | `10.0`                        | Per-check timeout (seconds)              |
| `parallel_workers`  | `8`                           | Number of checks run in parallel         |

## Ignoring checks

Use the `[ignore]` section to silence checks you do not care about. Values can
be comma- or newline-separated.

```ini
[ignore]
# Skip whole checks by their short-name (see `wtf audit --list-checks`).
checks = swap, updates

# Skip individual results, e.g. one noisy mountpoint.
# Disk results carry a result-name like "disk /mnt/Backup".
result_names =
    disk /mnt/Backup
    disk /mnt/Video
```

- `checks` — drop entire checks by their short-name. Run
  `wtf audit --list-checks` to see every available name.
- `result_names` — drop individual results within a check. This is handy for
  per-mount disk results, where each mountpoint has a name like
  `disk /mnt/Backup`.

The same thing can be done ad hoc from the command line with `--ignore`, which
accepts either a check short-name or a result-name:

```bash
wtf audit --ignore swap --ignore "disk /mnt/Backup"
```

## Example config

A generic starting point — copy it, then edit the keys you need:

```ini
# wtftools config — drop at /etc/wtftools/config.ini
# or ~/.config/wtftools/config.ini

[thresholds]
# Disk usage % thresholds (warn at >= warn, fail at >= fail).
disk_warn = 85
disk_fail = 95

# Memory %
mem_warn = 85
mem_fail = 95

# Swap % (a server that uses swap heavily is doing something wrong)
swap_warn = 30
swap_fail = 70

# Load avg ratio relative to CPU count
load_warn = 1.0
load_fail = 2.0

# CPU iowait %
iowait_warn = 10
iowait_fail = 30

# Open file descriptors % of fs.file-max
fd_warn = 60
fd_fail = 80

# Process count % of pid_max
pid_warn = 50
pid_fail = 80

# Hardware temperature (Celsius)
temp_warn_c = 75
temp_fail_c = 90

[ignore]
# Skip these check short-names entirely (comma- or newline-separated).
# Run `wtf audit --list-checks` to see all names.
checks =

# Skip specific result names (useful for disks: "disk /mnt/Backup")
result_names =
```
