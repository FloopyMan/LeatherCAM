PYTHON ?= python3

.PHONY: help run test test-headless lint format check dev-install clean

help:
	@echo "LeatherCAM — common targets:"
	@echo "  make run          — launch the GUI"
	@echo "  make test         — run unit tests"
	@echo "  make test-headless— run tests under offscreen Qt (CI mode)"
	@echo "  make lint         — ruff check ."
	@echo "  make format       — ruff format ."
	@echo "  make check        — lint + format check + headless tests"
	@echo "  make dev-install  — create .venv (with system-site-packages) and install -e .[dev]"
	@echo "  make clean        — remove caches and build artifacts"

run:
	$(PYTHON) -m leathercam

test:
	$(PYTHON) -m pytest -q

test-headless:
	QT_QPA_PLATFORM=offscreen $(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

check:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	QT_QPA_PLATFORM=offscreen $(PYTHON) -m pytest -q

.venv:
	$(PYTHON) -m venv --system-site-packages .venv

dev-install: .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -e ".[dev]"
	@echo
	@echo "Done. Activate with:  source .venv/bin/activate"

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
