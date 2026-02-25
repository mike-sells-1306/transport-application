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
	cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

run:
	cd backend && . .venv/bin/activate && DATABASE_URL="sqlite:////tmp/transport.db" python app.py

test:
	cd backend && . .venv/bin/activate && DATABASE_URL="sqlite://" python -m pytest tests/ -v
