# wtf — output for scripts

Machine-readable output and scripting recipes for the `wtf` CLI. Part of [wtftools](../README.md).

## Formats

Every command renders in one of three core formats; pick one with `-f` / `--format`:

- `text` — the default human view: colored, aligned, with section headers. Colors
  are auto-disabled when stdout is not a TTY (e.g. piped into `grep`/`less`) or
  with `--no-color`, so piping `text` always yields clean ASCII.
- `plain` — tab-separated rows, no headers, no decoration. One record per line,
  fields split on a single `\t`. This is the format to feed `awk -F'\t'` / `cut`.
- `json` — structured output. Resource commands (`disk`, `net`, `ports`, …) carry
  a top-level `schema_version` so scripts can detect layout changes across upgrades.

The flag is global and works **before** the subcommand:

```bash
wtf -f json disk            # same as: wtf disk --format json
wtf -f plain audit          # same as: wtf audit --format plain
```

A `--format` placed **after** the subcommand wins over the global one:

```bash
wtf -f plain disk --format json    # JSON: the later --format takes precedence
```

Every command supports `text` and `json`. `plain` (tab-separated) is available
on the resource views (`disk`, `cpu`, `mem`, `net`, `io`, `who`, `temp`, `top`,
`ports`, `docker`, `info`) and on `audit`. The extra formats `csv`, `html` and
`prometheus` are audit-only (`wtf audit --format csv|html|prometheus`).

### Field layouts (plain)

The `plain` rows are positional. The ones you script against most:

- `disk PATH` — `bytes<TAB>percent<TAB>path<TAB>depth`
  (depth `0` = direct children of PATH; deeper rows appear with `--tree`)
- `audit` — `status<TAB>name<TAB>message` (status is `ok` / `warn` / `fail` / `skip`)
- `ports` — `port<TAB>proto<TAB>address<TAB>pid<TAB>user<TAB>command`
  (unknown owner fields show `-`)

## grep / awk / jq cookbook

Practical one-liners. Examples use generic paths (`/var`) and names (`nginx`).

```bash
# Mounts above 80% used, target path only:
wtf -f json disk | jq -r '.mounts[] | select(.percent > 80) | .target'

# Same, read-only mounts above threshold (often the real problem):
wtf -f json disk | jq -r '.mounts[] | select(.readonly) | .target'

# Failed audit checks only, names column:
wtf audit --format plain | awk -F'\t' '$1 == "fail" {print $2}'

# Any problem (warn or fail), as "STATUS  name":
wtf audit --format plain | awk -F'\t' '$1 == "warn" || $1 == "fail" {print $1, $2}'

# Count results by status:
wtf audit --format plain | cut -f1 | sort | uniq -c

# Biggest folder directly under /var (path + bytes):
wtf disk /var --format plain | awk -F'\t' '$NF == 0' | sort -t$'\t' -k1 -nr | head -1 | awk -F'\t' '{print $3, $1}'

# Top-level entries only (skip the --tree drill-down rows):
wtf disk /var --tree --format plain | awk -F'\t' '$NF == 0'

# Folders over 1 GB under /var (depth 0), human-ish:
wtf disk /var --format plain | awk -F'\t' '$4 == 0 && $1 > 1e9 {print $3, $1}'

# Who owns a listening port — command per port:
wtf ports --format plain | awk -F'\t' '{print $1, $6}'

# Ports owned by a specific service:
wtf ports --format plain | awk -F'\t' '$6 == "nginx" {print $1}'

# Listening ports as a plain sorted list:
wtf -f json ports | jq -r '.ports[].port' | sort -un

# Default gateway interface, from net plain:
wtf net --format plain | awk -F'\t' '$1 == "gateway" {print $3}'

# Interfaces reporting receive/transmit errors:
wtf net --format plain | awk -F'\t' '$1 == "errors" && ($3 > 0 || $4 > 0) {print $2}'

# Audit fails as JSON objects (for a webhook payload):
wtf -f json audit | jq '[.results[] | select(.status == "fail")]'
```

## Exit codes

`wtf` returns CI/cron-friendly exit codes (`0` OK, `2` on a `[FAIL]`, etc.).
See the full table in [AUDIT.md](AUDIT.md#exit-codes).
