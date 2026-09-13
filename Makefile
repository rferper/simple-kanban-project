# NextLane — the commands, so nobody has to remember them.
#
#   make            list every target
#   make install    install dependencies
#   make run        run the whole app (API + frontend)
#   make test       run the test suite
#
# Ports are variables. To use a different one:
#
#   make run API_PORT=8091
#
# Changing the API port permanently means changing it in three places, not
# one: this file, `servers:` in openapi.yaml, and API_BASE in
# frontend/src/api/client.js. The frontend has to know where to call.
#
# On Windows use make.ps1 instead: GNU make there runs recipes through cmd.exe,
# and these are POSIX shell. Keep the two in step.
#
# Do not share backend/.venv between WSL and Windows. A Linux venv contains a
# `lib64` symlink that Windows cannot delete, so uv fails to rebuild it and
# every command after that fails. If that happens:  rm -rf backend/.venv

API_PORT ?= 8001
WEB_PORT ?= 8000

BACKEND  := backend
FRONTEND := frontend
UV       ?= uv

# Linux and macOS have `python3`; Windows has `python`. Hardcoding either one
# breaks the other, so find whichever exists. Override: make run PY=python3.12
PY ?= $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)

.DEFAULT_GOAL := help
.PHONY: help install run api web test test-one clean open require-python

require-python:
	@if [ -z "$(PY)" ]; then \
		echo 'No Python on PATH (looked for python3, then python).'; \
		echo 'Install it, or point make at one:  make run PY=/path/to/python'; \
		exit 1; \
	fi

help: ## List the targets
	@echo ''
	@echo '  NextLane'
	@echo ''
	@echo '  make install    install backend dependencies'
	@echo '  make run        run the whole app, API and frontend'
	@echo '  make api        run just the API'
	@echo '  make web        run just the frontend'
	@echo '  make test       run the test suite'
	@echo '  make test-one   one module:  make test-one T=test_auth'
	@echo '  make open       open the app in a browser'
	@echo '  make clean      remove caches'
	@echo ''
	@echo '  frontend  http://localhost:$(WEB_PORT)'
	@echo '  API       http://localhost:$(API_PORT)   docs at /docs'
	@echo '  sign in   researcher@example.com / nextlane'
	@echo ''

install: ## Install backend dependencies (the frontend has none)
	cd $(BACKEND) && $(UV) sync

run: require-python ## Run the whole app — API and frontend together (Ctrl-C stops both)
	@echo 'NextLane'
	@echo '  frontend  http://localhost:$(WEB_PORT)'
	@echo '  API       http://localhost:$(API_PORT)  (docs at /docs)'
	@echo '  sign in   researcher@example.com / nextlane'
	@echo ''
	@trap 'kill 0' EXIT INT TERM; \
		( cd $(BACKEND) && $(UV) run uvicorn app.main:app --reload --port $(API_PORT) || kill 0 ) & \
		( cd $(FRONTEND) && $(PY) -m http.server $(WEB_PORT) || kill 0 ) & \
		wait

api: ## Run just the API
	cd $(BACKEND) && $(UV) run uvicorn app.main:app --reload --port $(API_PORT)

web: require-python ## Run just the frontend (needs the API for anything to load)
	cd $(FRONTEND) && $(PY) -m http.server $(WEB_PORT)

test: ## Run the test suite
	cd $(BACKEND) && $(UV) run pytest

test-one: ## Run one module or pattern: make test-one T=test_auth
	cd $(BACKEND) && $(UV) run pytest -k '$(T)'

open: require-python ## Open the app in a browser
	@$(PY) -c "import webbrowser; webbrowser.open('http://localhost:$(WEB_PORT)')"

clean: ## Remove caches
	@find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -prune -exec rm -rf {} + 2>/dev/null || true
	@echo 'cleaned'
