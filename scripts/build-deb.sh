#!/usr/bin/env bash
# Build a .deb for wtftools using stdeb.
# Usage:  scripts/build-deb.sh
# Output: deb_dist/python3-wtftools_<version>_all.deb
#
# Requires `build`, `setuptools`, and `stdeb` available to the running
# python3 — the calling environment (CI workflow or developer venv) must
# install them, e.g.:
#   pip install build stdeb
# OS-side, stdeb shells out to `dpkg-buildpackage`, which needs
# `dh-python debhelper fakeroot build-essential`.
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found" >&2
    exit 1
fi

for mod in build setuptools stdeb; do
    if ! python3 -c "import $mod" 2>/dev/null; then
        echo "Missing Python module '$mod'. Run: pip install build setuptools stdeb" >&2
        exit 1
    fi
done

python3 -m build --sdist

# stdeb still expects a classic `setup.py`. Auto-generate a thin shim that
# delegates to pyproject.toml so we don't keep two source-of-truth files.
if [ ! -f setup.py ]; then
    cat > setup.py <<'PY'
from setuptools import setup
setup()
PY
fi

# Two-step (instead of `bdist_deb`):
#   1. sdist_dsc    — produce the unpacked source-package under deb_dist/
#   2. dpkg-buildpackage — build the actual .deb
# Why split: between (1) and (2) we have to monkey-patch the generated
# debian/rules. stdeb hard-codes `python3 setup.py install --install-layout=deb`,
# but modern setuptools (>=70) drops `--install-layout`. Strip it so the
# install step succeeds.
python3 setup.py --command-packages=stdeb.command sdist_dsc

# Locate the unpacked source dir, e.g. deb_dist/wtftools-0.0.0/
SRCDIR=$(ls -1d deb_dist/wtftools-*/ | head -n1)
if [ -z "$SRCDIR" ]; then
    echo "stdeb did not produce a source dir under deb_dist/" >&2
    exit 1
fi

if [ -f "$SRCDIR/debian/rules" ]; then
    sed -i 's| --install-layout=deb||g' "$SRCDIR/debian/rules"
fi

(cd "$SRCDIR" && dpkg-buildpackage -us -uc -b)

echo
echo "Built artifacts:"
ls -1 deb_dist/*.deb 2>/dev/null || { echo "(no .deb produced)"; exit 1; }
