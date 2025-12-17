.PHONY: help start stop restart logs clean setup-localstack test

help:
	@echo "PSP Reconciliation Platform - Local Development Commands"
	@echo ""
	@echo "Available commands:"
	@echo "  make start          - Start all services"
	@echo "  make stop           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make logs           - View logs from all services"
	@echo "  make logs-api       - View API service logs"
	@echo "  make setup-localstack - Setup LocalStack for AWS services"
	@echo "  make test           - Run tests"
	@echo "  make clean          - Stop and remove all containers and volumes"
	@echo "  make shell-api      - Open shell in API container"
	@echo "  make shell-db       - Open PostgreSQL shell"
	@echo "  make migrate        - Run database migrations"

start:
	@./scripts/start_local.sh

stop:
	@./scripts/stop_local.sh

restart: stop start

logs:
	@docker-compose logs -f

logs-api:
	@docker-compose logs -f api

setup-localstack:
	@./scripts/setup_localstack.sh

test:
	@docker-compose exec api pytest backend/tests/ -v

clean:
	@docker-compose down -v
	@echo "✅ All containers and volumes removed"

shell-api:
	@docker-compose exec api /bin/bash

shell-db:
	@docker-compose exec postgres psql -U postgres -d psp_reconciliation

migrate:
	@docker-compose exec api python -m alembic upgrade head

status:
	@docker-compose ps
