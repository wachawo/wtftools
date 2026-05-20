# Writing plugins for wtftools

A plugin extends `wtf audit` with a custom check. Drop an executable file
into one of the discovery directories — `wtf` picks it up automatically:

| dir                                       | when to use                  |
|-------------------------------------------|------------------------------|
| `/etc/wtf/checks.d/`                      | system-wide, root-owned      |
| `/etc/wtftools/checks.d/`                 | alternative                  |
| `$XDG_CONFIG_HOME/wtftools/checks.d/`     | per-user (defaults to `~/.config/wtftools/checks.d/`) |

Plugin discovery order: first match by basename wins. `wtf plugins`
prints the active list.

## The two contracts

A plugin must follow **one** of these to be useful:

### Exit-code contract (works in any language)

| exit code | status        | meaning                                   |
|-----------|---------------|-------------------------------------------|
| `0`       | ok            | check passed                              |
| `1`       | warn          | something to watch                        |
| `2`       | fail          | broken                                    |
| `77`      | skip          | not applicable on this host               |
| anything else | fail      | (treated as fail by the loader)           |

Whatever the plugin writes to **stdout** becomes the message line in
`wtf audit`. **stderr** is captured into the result `detail` only when the
status is `warn` or `fail`.

### JSON contract (more control, recommended)

Print a single-line JSON object on stdout — the exit code is ignored:

```json
{"status": "warn", "message": "/var is at 87%", "detail": ["see du -sh /var/*"]}
```

`status` must be one of `ok / warn / fail / skip`. Unknown values become
`skip`. `detail` is optional, a list of strings.

## Quickstart: bash

```bash
#!/usr/bin/env bash
# /etc/wtf/checks.d/check-tmp-size
pct=$(df --output=pcent /tmp | tail -1 | tr -d ' %')
if [ "$pct" -ge 95 ]; then
    echo "/tmp at ${pct}% — clean it up"
    exit 2
fi
if [ "$pct" -ge 80 ]; then
    echo "/tmp at ${pct}%"
    exit 1
fi
echo "/tmp at ${pct}%"
exit 0
```

```bash
chmod +x /etc/wtf/checks.d/check-tmp-size
wtf audit --check plugin:check-tmp-size
```

## Quickstart: Python (with the SDK)

```python
#!/usr/bin/env python3
# /etc/wtf/checks.d/check-http-health.py
from wtftools.plugin_sdk import ok, warn, fail
import urllib.request, time

URL = "http://127.0.0.1:8080/healthz"
started = time.monotonic()
try:
    with urllib.request.urlopen(URL, timeout=2) as r:
        ms = (time.monotonic() - started) * 1000
        if r.status >= 400:
            fail(f"HTTP {r.status}", detail=[f"latency={ms:.0f}ms"])
        if ms > 500:
            warn(f"HTTP {r.status} but slow: {ms:.0f}ms")
        ok(f"HTTP {r.status} in {ms:.0f}ms")
except Exception as exc:
    fail(str(exc))
```

`ok / warn / fail / skip` from `wtftools.plugin_sdk` each print the
right JSON and call `sys.exit` with the matching code. No need to
memorize the contract.

`result(status, message, detail=None)` is the non-terminating variant if
you want to emit a result without exiting (e.g. running multiple checks
from one script and picking the worst).

## Best practices

- **Skip cleanly** (`exit 77` / `skip()`) when the required binary or file
  is missing. Don't try to "succeed when irrelevant" — that hides
  problems on other hosts.
- **Cap your runtime.** The plugin loader gives you 15s by default. If
  you're polling something slow, do the work elsewhere and have the
  plugin read a cached result.
- **Don't crash on bad input.** Wrap external calls with `try/except`
  and convert failures into `skip()` or `fail()`.
- **Be terse in the message.** It shares a line with the marker; keep
  under ~80 characters. Use `detail` for the long stuff.
- **Make config explicit.** Read knobs from env so users can change
  thresholds without editing the script:
  `WARN_PCT=${WARN_PCT:-70}` is idiomatic.
- **No global side effects.** A check should be read-only. Writes,
  network mutations, or `systemctl start` calls are out of scope.

## Examples

Four ready-to-deploy examples live in `examples/plugins/`:

| script                              | what it checks                      |
|-------------------------------------|-------------------------------------|
| `check-cert-domain.sh`              | TLS expiry of a remote domain       |
| `check-postgres-connections.sh`     | Postgres conn count vs `max_connections` |
| `check-redis-memory.sh`             | Redis `used_memory` vs `maxmemory`  |
| `check-disk-write.sh`               | fsync-write latency on /tmp         |
| `check-http-health.py`              | internal HTTP probe (Python SDK)    |

Copy any of them, edit the env-configurable values, drop into a
discovery directory, `chmod +x`, done.

## Testing your plugin

```bash
# 1. Run the file directly and check stdout/exit:
/etc/wtf/checks.d/my-check ; echo "exit=$?"

# 2. Make sure the loader discovers it:
wtf plugins

# 3. Run it via the audit pipeline:
wtf audit --check plugin:my-check -v
```

## Listing & disabling plugins

```bash
wtf plugins                      # what wtf sees
chmod -x /etc/wtf/checks.d/foo   # disable one (loader skips non-executable)
wtf audit --ignore plugin:foo    # one-shot bypass without filesystem changes
```
