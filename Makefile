VENV ?= .venv
PYTHON ?= $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)

.PHONY: help run test test-headless lint format check dev-install dist-install build appimage clean

help:
	@echo "LeatherCAM — common targets:"
	@echo "  make run          — launch the GUI"
	@echo "  make test         — run unit tests"
	@echo "  make test-headless— run tests under offscreen Qt (CI mode)"
	@echo "  make lint         — ruff check ."
	@echo "  make format       — ruff format ."
	@echo "  make check        — lint + format check + headless tests"
	@echo "  make dev-install  — create .venv (with system-site-packages) and install -e .[dev]"
	@echo "  make dist-install — install the [dist] extra (PyInstaller) into .venv"
	@echo "  make build        — PyInstaller onedir build into dist/leathercam/"
	@echo "  make appimage     — wrap dist/leathercam/ into a Linux AppImage (needs appimagetool)"
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

dist-install: .venv
	.venv/bin/python -m pip install ".[dist]"

# Isolated venv WITHOUT --system-site-packages so PyInstaller only sees
# the runtime deps declared in pyproject.toml — the dev .venv inherits
# whatever the user has installed system-wide (torch, tensorflow, ...),
# which would otherwise get bundled into the binary.
.venv-dist:
	python3 -m venv .venv-dist
	.venv-dist/bin/python -m pip install --upgrade pip
	.venv-dist/bin/python -m pip install ".[dist]"

build: .venv-dist
	.venv-dist/bin/python -m PyInstaller --noconfirm packaging/leathercam.spec
	@echo
	@echo "Built dist/leathercam/. Launch: ./dist/leathercam/leathercam"

appimage: .venv-dist
	PYTHON=.venv-dist/bin/python bash packaging/build-appimage.sh

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache .venv-dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
