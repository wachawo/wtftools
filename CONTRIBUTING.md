# Contributing to wtftools

## Local setup

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,full]"
pre-commit install --hook-type pre-commit --hook-type pre-push
```

The last line wires up `.pre-commit-config.yaml`:
- **on `git commit`** — fast checks (ruff, trailing whitespace, YAML/TOML/JSON
  syntax, merge-conflict markers, large files, mixed line endings).
- **on `git push`** — full `pytest` suite with the 80 % coverage gate.

Both must pass before code reaches GitHub, so CI never sees a broken commit.
The venv must be active so `pytest` is on `PATH` when the pre-push hook
fires.

## Running tests

```bash
pytest                              # full suite with coverage gate (≥80%)
pytest tests/test_audit.py          # one file
pytest -k "test_check_swap"         # one pattern
pytest -m "not integration"         # skip host-dependent tests (faster, deterministic)
```

Tests marked `@pytest.mark.integration` shell out to real host tools
(`docker`/`systemctl`/`smartctl`/`journalctl`) or read real `/proc`. They run
by default (and in CI); use `-m "not integration"` for a fast, host-independent
local run.

The suite includes ~620 tests and runs in ~20 seconds. Coverage report shows
in the pytest summary; HTML report via `pytest --cov-report=html htmlcov/`.

## Lint

```bash
ruff check wtftools tests
```

Configured rules: `E, F, I, UP, B, SIM, C4`, line length 180, `E501` ignored.

## Style

See `rules/python.md` in the parent `~/.claude` repo for the canonical
Python style this project follows (Flask/FastAPI lineage; functional
preferred over OO; logger-per-module; `f"{type(exc).__name__}: {exc}"` for
error logging).

Short summary applicable here:
- **No decorative comment dividers** (no `# ---- foo ----`).
- **Comments only when WHY is non-obvious** — no `# loop over items`.
- **No emoji** unless explicitly requested.
- **No AI footers** in commits, PRs, or code comments.

## Adding a new built-in check

1. Add the data-gathering function to `wtftools/sysinfo.py` (return
   `None` when the underlying tool isn't available — never raise out).
2. Add a `_check_<name>()` wrapper in `wtftools/audit.py` returning a
   `CheckResult` (or `List[CheckResult]` for fan-out checks like `_check_disks`).
3. Register a stable short name in `CHECK_REGISTRY`.
4. Add tests:
   - sysinfo function: real-content parsing + each failure path
   - audit wrapper: each status (ok/warn/fail/skip)
5. Update `wtf audit --list-checks` (automatic via the registry).
6. Add advice for the new check to `wtftools/explain.py` `_RULES`.
7. Append to `completions/wtf` `--check` autocompletion list.

## Adding a new subcommand

1. Define `cmd_<name>(args)` in `wtftools/main.py` returning an exit code.
2. Register the subparser inside `build_parser()`.
3. Add tests in the matching `tests/test_<module>.py`.
4. Update README's subcommand table.
5. Append to `completions/wtf`'s `subcommands` list + a handler.

## Releasing (maintainer-only)

A tagged push triggers the publish and release workflows:

```bash
git tag -a v0.0.2 -m 'v0.0.2'
git push origin v0.0.2
```

`publish.yml` builds the sdist + wheel and publishes to PyPI via OIDC trusted
publishing (no API token stored in the repo); `release.yml` runs the test
suite, builds the `.deb`, and attaches it to the GitHub Release.

## Pull requests

- Branch off `main`.
- Add tests for new behavior. Coverage must stay ≥80%.
- Keep PR focused; one feature/fix per PR.
- Update CHANGELOG.md under `## [Unreleased]`.

## Reporting bugs / feature requests

GitHub issues: https://github.com/wachawo/wtftools/issues

Please include `wtf doctor --format json` output — it gives us a baseline
of the host's capabilities (psutil, systemctl, journalctl, /proc, ...).
