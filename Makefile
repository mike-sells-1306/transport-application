.PHONY: build up up-build down restart logs open run test install podman-install check-compose

# Podman / container commands
# Uses `podman-compose` when available, falls back to `podman compose`.
COMPOSE := $(shell if command -v podman-compose >/dev/null 2>&1; then echo "podman-compose"; elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then echo "podman compose"; elif command -v docker-compose >/dev/null 2>&1; then echo "docker-compose"; elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then echo "docker compose"; fi)
PROJECT_NAME := $(shell basename "$(CURDIR)")
CONTAINERS := $(PROJECT_NAME)_mysql_1 $(PROJECT_NAME)_backend_1 $(PROJECT_NAME)_frontend_1

check-compose:
	@if [ -z "$(COMPOSE)" ]; then \
		echo "No Podman compose command found."; \
		echo "Install Podman (v4+) for 'podman compose' or install 'podman-compose'."; \
		exit 1; \
	fi
	@echo "Using compose command: $(COMPOSE)"

podman-install:
	pip install --user podman-compose

build: check-compose
	$(COMPOSE) build

up: check-compose
	@if podman container exists $(PROJECT_NAME)_mysql_1 \
		&& podman container exists $(PROJECT_NAME)_backend_1 \
		&& podman container exists $(PROJECT_NAME)_frontend_1; then \
		echo "Starting existing containers..."; \
		podman start $(CONTAINERS); \
	else \
		echo "Creating stack with $(COMPOSE)..."; \
		$(COMPOSE) up -d --remove-orphans; \
	fi

up-build: check-compose
	$(COMPOSE) down
	$(COMPOSE) up -d --build --remove-orphans

logs: check-compose
	$(COMPOSE) logs -f

open: up
	@echo "Opening http://localhost:3000 ..."
	@sh -c 'if command -v xdg-open >/dev/null 2>&1; then xdg-open http://localhost:3000 >/dev/null 2>&1 & \
	elif command -v gio >/dev/null 2>&1; then gio open http://localhost:3000 >/dev/null 2>&1 & \
	elif command -v sensible-browser >/dev/null 2>&1; then sensible-browser http://localhost:3000 >/dev/null 2>&1 & \
	else echo "Could not find a browser opener. Open http://localhost:3000 manually."; fi'

down: check-compose
	$(COMPOSE) down

restart: down up

# Local development (Linux/macOS)
install:
	@if [ ! -d "backend/.venv" ]; then cd backend && python3 -m venv .venv; fi
	cd backend && . .venv/bin/activate && pip install -r requirements.txt

run:
	cd backend && . .venv/bin/activate && DATABASE_URL="sqlite:////tmp/transport.db" python3 app.py

test:
	cd backend && . .venv/bin/activate && DATABASE_URL="sqlite://" python3 -m pytest tests/ -v

# Windows commands (use these in PowerShell)
install-win:
	cd backend && python -m venv .venv && .\.venv\Scripts\activate && pip install -r requirements.txt

run-win:
	cd backend && .\.venv\Scripts\activate && set DATABASE_URL=sqlite:///transport.db && python app.py

test-win:
	cd backend && .\.venv\Scripts\activate && set DATABASE_URL=sqlite:// && python -m pytest tests/ -v


