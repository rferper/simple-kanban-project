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

# The container is one process serving both, so it has one port of its own.
APP_PORT ?= 8000
IMAGE    ?= nextlane

# The local Postgres is the `db` service in docker-compose.yaml, and there is
# deliberately only one of it: `make run` and `docker compose up` look at the
# same database, because two would mean work disappearing when you switched
# between them (`_docs/decisions.md` #26). Two databases on it — `nextlane` for
# the app, `nextlane_test` for the store contract.
#
# DEV_DSN has to match DEFAULT_DB in backend/app/dependencies.py.
DB_PORT  ?= 55432
DEV_DSN  ?= postgresql://nextlane:nextlane@localhost:$(DB_PORT)/nextlane
TEST_DSN ?= postgresql://nextlane:nextlane@localhost:$(DB_PORT)/nextlane_test

BACKEND  := backend
FRONTEND := frontend
UV       ?= uv

# Linux and macOS have `python3`; Windows has `python`. Hardcoding either one
# breaks the other, so find whichever exists. Override: make run PY=python3.12
PY ?= $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)

.DEFAULT_GOAL := help
.PHONY: help install run api web test test-one lint types check clean open require-python
.PHONY: docker-build docker-run compose-up compose-down
.PHONY: test-postgres test-integration postgres postgres-stop

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
	@echo '  make postgres   start the local Postgres (before make run)'
	@echo '  make test-postgres  run the suite against Postgres as well'
	@echo '  make test-integration  run the compose stack and test against it'
	@echo '  make open       open the app in a browser'
	@echo '  make clean      remove caches'
	@echo ''
	@echo '  make docker-build   build the container image'
	@echo '  make docker-run     run it — the whole app on one port'
	@echo '  make compose-up     run it with Postgres, through docker compose'
	@echo '  make compose-down   stop those (docker compose down -v drops the data)'
	@echo ''
	@echo '  frontend  http://localhost:$(WEB_PORT)'
	@echo '  API       http://localhost:$(API_PORT)   docs at /docs'
	@echo '  sign in   researcher@example.com / nextlane'
	@echo ''

install: ## Install backend dependencies (the frontend has none)
	cd $(BACKEND) && $(UV) sync

run: require-python ## Run the whole app — API and frontend together (Ctrl-C stops both)
	@echo 'NextLane'
	@echo '  database  $(DEV_DSN)'
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

test-postgres: ## Run the suite against Postgres as well (needs `make postgres`)
	cd $(BACKEND) && NEXTLANE_TEST_POSTGRES='$(TEST_DSN)' $(UV) run pytest

test-integration: ## Build and run the compose stack, and test against it
	@# Its own compose project and its own ports, so this cannot touch — or be
	@# confused with — a development stack that is already running.
	cd $(BACKEND) && $(UV) run pytest -m integration

postgres: ## Start the local Postgres — the one `make run` expects
	docker compose up -d --wait db
	@# `POSTGRES_DB` creates the app's database, but only the first time the
	@# volume is built, and this target has to be right for an existing one too.
	@# "already exists" is the success case, hence the `|| true`.
	@docker compose exec -T db createdb -U nextlane nextlane_test 2>/dev/null || true
	@echo ''
	@echo 'Postgres is up.'
	@echo '  app    $(DEV_DSN)'
	@echo '  tests  $(TEST_DSN)'

postgres-stop: ## Stop it, keeping the board (docker compose down -v drops it)
	docker compose stop db

lint: ## Lint and format-check the backend, and check the frontend
	cd $(BACKEND) && $(UV) run ruff check .
	cd $(BACKEND) && $(UV) run ruff format --check .
	@$(PY) -c "import shutil,sys; sys.exit(0 if shutil.which('node') else 1)" \
		&& node $(FRONTEND)/check.mjs \
		|| echo 'frontend: skipped (node not on PATH)'

types: ## Type-check the backend
	cd $(BACKEND) && $(UV) run ty check

check: lint types test ## Everything that has to pass before a commit
	@echo ''
	@echo 'lint, types and tests all pass.'

open: require-python ## Open the app in a browser
	@$(PY) -c "import webbrowser; webbrowser.open('http://localhost:$(WEB_PORT)')"

docker-build: ## Build the container image (the API serves the frontend)
	docker build -t $(IMAGE) .

docker-run: ## Run that image — the whole app on http://localhost:$(APP_PORT)
	@echo 'NextLane  http://localhost:$(APP_PORT)  (docs at /docs)'
	@echo 'sign in   researcher@example.com / nextlane'
	@echo ''
	docker run --rm -it -p $(APP_PORT):8000 -v nextlane-data:/data -e ANTHROPIC_API_KEY $(IMAGE)

compose-up: ## Run the app and Postgres together (docker-compose.yaml)
	docker compose up --build -d
	@echo ''
	@echo 'NextLane  http://localhost:$(APP_PORT)  (docs at /docs)'
	@echo 'sign in   researcher@example.com / nextlane'
	@echo 'logs      docker compose logs -f'

compose-down: ## Stop them, keeping the data (docker compose down -v drops it)
	docker compose down

clean: ## Remove caches
	@find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -prune -exec rm -rf {} + 2>/dev/null || true
	@echo 'cleaned'
