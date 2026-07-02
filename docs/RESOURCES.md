# wtf — resource views

Per-resource "show" views — ask about one resource at a time, like `show` commands on a switch.
Part of [wtftools](../README.md).

Every resource command accepts `--format text|plain|json` (or the global `-f`,
e.g. `wtf -f json disk`). `text` is the human view (colors drop automatically
when piped), `plain` is tab-separated with no headers, and `json` is
machine-readable. JSON payloads carry a `schema_version` so scripts survive
upgrades.

Section headers in the examples below use the plain `# DISK` form that the tool
prints.

## `wtf disk`

The mount overview answers "is there space?" — one row per mount with the full
path, used/total, percent, a usage bar, and the filesystem type (read-only and
high-inode mounts are flagged).

```
$ wtf disk
# DISK
  /            42.0GB / 80.0GB   53%  [██████████··········]  ext4
  /boot       216.4MB / 1.0GB    21%  [████················]  ext4
  /var         17.0GB / 20.0GB   85%  [█████████████████···]  ext4
```

Give it a path and it becomes a folder-size breakdown of that directory —
largest first — with columns `path/  size  % of root  depth`. Percentages are a
share of the analysed root's total, so a child is never larger than its parent.

```
$ wtf disk /var
# DISK USAGE /var
  lib/      15.0GB  75%  0
  log/       3.1GB  16%  0
  cache/     1.2GB   6%  0
```

Add `--tree` to drill into the biggest folder level by level. `--tree N` opens
the N largest folders at each level; bare `--tree` is `--tree 1`.

```
$ wtf disk / --tree
# DISK USAGE /
  home/                1021.0GB  70%  0
  home/deploy/         1021.0GB  70%  1
  home/deploy/myapp/    429.7GB  30%  2
  usr/                  207.9GB  14%  0
  var/                  206.5GB  14%  0
```

`wtf disk --tree` with no path drills the fullest mount. Run with `sudo` to read
root-owned directories — without it, unreadable folders are skipped (the
breakdown shows "nothing to show" if the whole root is unreadable).

- `path` (positional) — directory to break down by folder size. Omit it for the mount overview.
- `--tree [N]` — expand the N largest folders at each level. Bare `--tree` = 1; omitted = flat (immediate children only).
- `--depth N` — levels to show when expanding with `--tree` (default: 3).
- `--top N` — cap the number of children shown per level (default: 0 = all).
- `--show-commands` — also print the classic commands this view replaces.
- `--format text|plain|json` — `plain` rows are `bytes<TAB>percent<TAB>path<TAB>depth`; `json` is flat entries each carrying an absolute `path` plus a relative `rel`.

> BREAKING: `--tree` is now a count of folders to expand, not a path. The
> directory to analyse is a positional argument: `wtf disk /var --tree`, not
> `wtf disk --tree /var`.

## `wtf cpu`

Load, iowait, CPU pressure (PSI), and the top CPU consumers.

```
$ wtf cpu
# CPU
  model   : Intel(R) Xeon(R) CPU  (x8)
  load    : 0.42 0.51 0.55  (per-cpu 0.05)
  iowait  : 0.3%
  psi     : some avg10=0.0%

# TOP BY CPU
   12.3%  deploy          1234  nginx
    4.1%  postgres        2345  postgres
```

- `--show-commands` — also print the classic commands this view replaces.
- `--format text|plain|json`.

## `wtf mem`

RAM and swap usage, recent OOM kills, and the top memory consumers.

```
$ wtf mem
# MEMORY
  ram     : [█████···············] 25%  4.1GB / 16.0GB
  swap    : [··················] 0%  0B / 2.0GB
  psi     : some avg10=0.0%
  oom     : 0 kill(s) in last 24h

# TOP BY RAM
    1.2GB  postgres        2345  postgres
  640.0MB  deploy          1234  nginx
```

- `--since HOURS` — look-back window for OOM kills (default: 24).
- `--show-commands` — also print the classic commands this view replaces.
- `--format text|plain|json`.

## `wtf net`

Interfaces and their IPs, default gateway, DNS servers, interface errors, and
listening TCP ports.

```
$ wtf net
# NETWORK
  eth0       up     192.0.2.10
  lo         up     127.0.0.1
  gateway : 192.0.2.1 via eth0
  dns     : 192.0.2.1, 1.1.1.1

  listening tcp: 22, 80, 443, 5432
```

- `--show-commands` — also print the classic commands this view replaces.
- `--format text|plain|json`.

## `wtf io`

Per-device read/write rates and utilisation, IO pressure (PSI), and
processes stuck in uninterruptible (D-state) IO.

```
$ wtf io
# IO
  psi     : some avg10=0.4%
  iowait  : 0.3%
  sda      read    1.2MB/s  write  640.0KB/s  util 7%
  nvme0n1  read    8.0KB/s  write    2.4MB/s  util 3%
```

- `--show-commands` — also print the classic commands this view replaces.
- `--format text|plain|json`.

## `wtf who`

Who is logged in right now, recent successful logins, and the count of failed
authentication attempts.

```
$ wtf who
# WHO
  deploy         pts/0      192.0.2.50           since 2026-06-15 08:12
  failed auth: 3 in last 24h

# RECENT LOGINS
  deploy   pts/0   192.0.2.50   Mon Jun 15 08:12
```

- `--since HOURS` — look-back window for failed auth (default: 24).
- `--show-commands` — also print the classic commands this view replaces.
- `--format text|plain|json`.

## `wtf temp`

Hardware temperatures read from `/sys/class/hwmon` sensors (CPU, disk, board),
hottest first, color-coded against warn/fail thresholds. Aliases: `temps`,
`temperature`. Inside most VMs and containers there are no sensors, so it
reports none.

```
$ wtf temp
# TEMP
   58.0°C  coretemp/Package id 0
   41.0°C  nvme/Composite
  hottest 58.0°C · warn >=75°C · fail >=85°C · 2 sensor(s)
```

- `--format text|plain|json`.

## `wtf info`

A one-page snapshot — disk, cpu, mem, net, io, who and temp at once. Use it when
you want everything in a single screen instead of running each command.

```
$ wtf info
# DISK
  ...
# CPU
  ...
# MEMORY
  ...
```

- `--format text|plain|json`.

## `wtf top`

A focused process top, sorted by CPU or resident memory, optionally filtered by
user or command name.

```
$ wtf top --sort rss --limit 5
# TOP 5 BY RSS
      PID  USER          CPU%       RSS  COMMAND
     2345  postgres       4.1     1.2GB  postgres
     1234  deploy        12.3   640.0MB  nginx
```

- `--sort cpu|rss` — sort key (default: cpu).
- `--limit LIMIT` — number of processes to show (default: 10).
- `--user PREFIX` — filter by username prefix.
- `--name PATTERN` — filter by command-name substring (case-insensitive).
- `--format text|plain|json`.

## `wtf ports`

Listening sockets with the owning PID, user and command. Rich PID/user info
needs `psutil` (`pip install wtftools[full]`); without it the view falls back to
ports and addresses only.

```
$ wtf ports
# LISTENING PORTS
   PORT  PROTO ADDR                 PID  USER           COMMAND
     22  tcp   *                    789  root           sshd
     80  tcp   *                   1234  deploy         nginx
   5060  tcp   *                   4567  asterisk       asterisk
```

Pass a port number to drill into it — the protocol and state, the holding PID
and user, the exact executable file behind it (via `lsof` + `/proc`), and the
directory it runs from. Run with `sudo` to see processes owned by other users.

```
$ wtf port 5060
# PORT 5060
  tcp *:5060 (LISTEN)
    pid     : 4567
    user    : asterisk
    command : asterisk
    exe     : /usr/sbin/asterisk
    cwd     : /var/lib/asterisk
```

- `port` (positional) — drill into one port: which process holds it, its exe file and cwd.
- `--proto tcp|udp|all` — protocol filter for the listing (default: tcp).
- `--public-only` — skip loopback addresses (127.x).
- `--format text|plain|json`.

## `wtf docker`

For a named container: where `docker compose up` ran (read straight from the
container's labels) and how much disk it eats — image layers, the writable
container layer, and the JSON log.

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

With no name it lists every running container with its size columns, working
dir, and a TOTAL row.

```
$ sudo wtf docker
# DOCKER
  NAME         STATUS       IMAGE   CONTNR     LOGS  WORKING DIR
  myapp_web    running      164MB    267MB   53.8MB  /home/deploy/myapp
  myapp_db     running      276MB     63B    4.02MB  /home/deploy/myapp
  TOTAL                     440MB    267MB   57.8MB
  note: IMAGE total is logical (images share layers); real disk via docker system df
```

Sizes use decimal units (1GB = 1000MB), matching `docker container ls --size`.
Per-row IMAGE is the image's full logical (virtual) size. The IMAGE total
dedupes by image id — an image shared by many containers is counted once — but
different images still share base layers on disk, so even that deduped sum
overstates real usage; the true layer-deduplicated disk comes from
`docker system df`. CONTNR (writable layer) and LOGS are per-container, so their
totals are exact. Log sizes need read access under `/var/lib/docker`, so run
with `sudo`, otherwise they show `?`.

- `name` (positional) — container name; omit to list running containers.
- `--format text|plain|json`.

## `--show-commands`

Most resource commands accept `--show-commands`. Add it to any of them and the
view also prints the classic, well-known commands it replaces — so you can learn
what is happening under the hood and run them yourself.

```
$ wtf cpu --show-commands
  ...
  equivalent commands:
    $ uptime
    $ top -bn1 | head
    $ ps aux --sort=-%cpu | head
```
