.PHONY: build up down run test install

# Docker commands
build:
	docker-compose build

up:
	docker-compose up --build

down:
	docker-compose down

# Local development (Linux/macOS)
install:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

run:
	cd backend && . .venv/bin/activate && DATABASE_URL="sqlite:///transport.db" python app.py

test:
	cd backend && . .venv/bin/activate && DATABASE_URL="sqlite://" python -m pytest tests/ -v

# Windows commands (use these in PowerShell)
install-win:
	cd backend && python -m venv .venv && .\.venv\Scripts\activate && pip install -r requirements.txt

run-win:
	cd backend && .\.venv\Scripts\activate && set DATABASE_URL=sqlite:///transport.db && python app.py

test-win:
	cd backend && .\.venv\Scripts\activate && set DATABASE_URL=sqlite:// && python -m pytest tests/ -v
