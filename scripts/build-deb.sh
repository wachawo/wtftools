#!/usr/bin/env bash
# Build a .deb for wtftools using stdeb (no debhelper toolchain needed on host).
# Usage:  scripts/build-deb.sh
# Output: deb_dist/python3-wtftools_<version>_all.deb
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found" >&2
    exit 1
fi

python3 -m pip install --user --upgrade build stdeb >/dev/null

python3 -m build --sdist
TARBALL=$(ls -1t dist/wtftools-*.tar.gz | head -n1)
python3 -m stdeb.cli --command-packages=stdeb.command bdist_deb --copyright-file LICENSE -i wtftools --suite stable \
    --debian-version 1 < /dev/null > /dev/null || true

# Fallback: stdeb expects setup.py; auto-generate one from pyproject for compatibility.
if [ ! -f setup.py ]; then
    cat > setup.py <<'PY'
from setuptools import setup
setup()
PY
fi

python3 setup.py --command-packages=stdeb.command sdist_dsc bdist_deb

echo
echo "Built artifacts:"
ls -1 deb_dist/*.deb 2>/dev/null || echo "(no .deb produced — check stdeb output above)"
