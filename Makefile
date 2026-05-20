PY ?= python3

.PHONY: help install dev test lint build deb clean demo

help:
	@echo "wtftools — make targets"
	@echo "  make install      Install into the current Python environment (pip)"
	@echo "  make dev          Editable install with dev extras"
	@echo "  make test         Run the test suite"
	@echo "  make lint         Run ruff lint"
	@echo "  make build        Build sdist + wheel into dist/"
	@echo "  make deb          Build a .deb via stdeb (output: deb_dist/)"
	@echo "  make demo         Show a quick wtf demo against the local host"
	@echo "  make clean        Remove build artifacts"

install:
	$(PY) -m pip install .

dev:
	$(PY) -m pip install -e ".[dev,full]"

test:
	$(PY) -m pytest

lint:
	ruff check wtftools tests

build:
	$(PY) -m pip install --upgrade build
	$(PY) -m build

deb:
	bash scripts/build-deb.sh

demo:
	$(PY) -m wtftools info
	@echo
	$(PY) -m wtftools audit

clean:
	rm -rf build dist deb_dist *.egg-info wtftools/__pycache__ wtftools/checks/__pycache__ \
		tests/__pycache__ .pytest_cache .ruff_cache .coverage htmlcov
