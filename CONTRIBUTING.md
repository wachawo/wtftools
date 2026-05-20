# Contributing to wtftools

## Local setup

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,full]"
```

## Running tests

```bash
pytest                              # full suite with coverage gate (≥80%)
pytest tests/test_iteration5.py     # one file
pytest -k "test_check_swap"         # one pattern
```

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

1. Add the data-gathering function to `wtftools/checks/sysinfo.py` (return
   `None` when the underlying tool isn't available — never raise out).
2. Add a `_check_<name>()` wrapper in `wtftools/audit.py` returning a
   `CheckResult` (or `List[CheckResult]` for fan-out checks like `_check_disks`).
3. Register a stable short name in `CHECK_REGISTRY`.
4. Add tests:
   - sysinfo function: real-content parsing + each failure path
   - audit wrapper: each status (ok/warn/fail/skip)
5. Update `wtf audit --list-checks` (automatic via the registry).
6. Add advice for the new check to `wtftools/explain.py` `_RULES`.
7. Append to `scripts/wtf.bash-completion` `--check` autocompletion list.

## Adding a new subcommand

1. Define `cmd_<name>(args)` in `wtftools/main.py` returning an exit code.
2. Register the subparser inside `build_parser()`.
3. Add tests in `tests/test_iterationN.py`.
4. Update README's subcommand table.
5. Append to `scripts/wtf.bash-completion`'s `subcommands` list + a handler.

## Releasing (maintainer-only)

A tagged push triggers `.github/workflows/release.yml`:

```bash
git tag -a v0.2.0 -m 'v0.2.0'
git push origin v0.2.0
```

CI then runs the test suite, builds the sdist + wheel, and publishes to PyPI
(needs `PYPI_API_TOKEN` repo secret) plus pushes a Docker image to GHCR.

## Pull requests

- Branch off `main`.
- Add tests for new behavior. Coverage must stay ≥80%.
- Keep PR focused; one feature/fix per PR.
- Update CHANGELOG.md under `## [Unreleased]`.

## Reporting bugs / feature requests

GitHub issues: https://github.com/wachawo/wtftools/issues

Please include `wtf doctor --format json` output — it gives us a baseline
of the host's capabilities (psutil, systemctl, journalctl, /proc, ...).
