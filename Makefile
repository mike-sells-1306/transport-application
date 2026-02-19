.PHONY: build up down

build:
	docker-compose build

up:
	docker-compose up --build

down:
	docker-compose down
