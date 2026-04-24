.PHONY: help up down build dev-api dev-web dev-worker migrate reset logs clean

help:
	@echo "OmniNewsFlow - Available commands:"
	@echo ""
	@echo "  make up          Start all services (docker compose)"
	@echo "  make down        Stop all services"
	@echo "  make build       Rebuild all Docker images"
	@echo "  make dev-api     Run API server locally"
	@echo "  make dev-web     Run Next.js dev server locally"
	@echo "  make dev-worker  Run Celery worker locally"
	@echo "  make migrate     Run database migrations"
	@echo "  make reset       Reset database (drop & recreate)"
	@echo "  make logs        Follow all service logs"
	@echo "  make clean       Remove containers, volumes, and build artifacts"

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build --no-cache

dev-api:
	cd apps/api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-web:
	cd apps/web && npm run dev

dev-worker:
	cd apps/worker && celery -A app.worker worker --loglevel=info --concurrency=4

migrate:
	cd apps/api && alembic upgrade head

reset:
	docker compose down -v
	docker compose up -d postgres redis
	sleep 3
	cd apps/api && alembic upgrade head

logs:
	docker compose logs -f

clean:
	docker compose down -v --remove-orphans
	rm -rf apps/web/node_modules apps/web/.next
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
