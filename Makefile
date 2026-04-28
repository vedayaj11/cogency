.PHONY: help install up down logs api worker web migrate fmt lint test

help:
	@echo "Targets:"
	@echo "  install   - install python (uv sync) and node (pnpm install) deps"
	@echo "  up        - docker compose up infra (postgres, temporal, langfuse)"
	@echo "  down      - stop infra"
	@echo "  api       - run FastAPI dev server"
	@echo "  worker    - run Temporal worker"
	@echo "  web       - run Next.js dev server"
	@echo "  migrate   - apply alembic migrations"
	@echo "  fmt       - ruff format + ruff check --fix"
	@echo "  lint      - ruff check + mypy"
	@echo "  test      - pytest"

install:
	uv sync --all-packages
	pnpm install

up:
	docker compose -f infra/docker/docker-compose.yml up -d

down:
	docker compose -f infra/docker/docker-compose.yml down

api:
	cd apps/api && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	cd apps/worker && uv run python -m worker.main

web:
	pnpm --filter @cogency/web dev

migrate:
	cd db && uv run alembic upgrade head

migrate-revision:
	cd db && uv run alembic revision --autogenerate -m "$(MSG)"

fmt:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff check .
	uv run mypy apps packages

test:
	uv run pytest -q
