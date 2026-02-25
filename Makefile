.PHONY: build up down run test install

# Docker commands
build:
	docker-compose build

up:
	docker-compose up --build

down:
	docker-compose down

# Local development
install:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

run:
	cd backend && . .venv/bin/activate && DATABASE_URL="sqlite:////tmp/transport.db" python3 app.py

test:
	cd backend && . .venv/bin/activate && DATABASE_URL="sqlite://" python3 -m pytest tests/ -v
