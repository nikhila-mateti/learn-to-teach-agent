.PHONY: install lint test build up down logs smoke k8s-validate

install:
	python3 -m pip install -r requirements-dev.txt

lint:
	ruff check app tests

test:
	pytest -q

build:
	docker compose build

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f app

smoke:
	bash scripts/smoke_test.sh

k8s-validate:
	bash scripts/validate_k8s.sh
