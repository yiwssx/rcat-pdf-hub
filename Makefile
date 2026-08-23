.PHONY: up down logs ps test build config secrets cleanup migrate scale-workers up-s3 up-security up-observability up-archive

up:
	docker compose up -d --build

down:
	docker compose --profile s3 --profile security --profile observability --profile archive down

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

build:
	docker compose build

config:
	docker compose config

test:
	docker compose run --rm api python -m pytest -q

cleanup:
	docker compose run --rm cleanup python -m app.cleanup

migrate:
	docker compose run --rm api python -m app.migrate

scale-workers:
	docker compose up -d --scale worker=$${WORKERS:-4} worker

up-s3:
	docker compose --profile s3 up -d seaweedfs

up-security:
	docker compose --profile security up -d clamav

up-observability:
	docker compose --profile observability up -d prometheus otel-collector

up-archive:
	docker compose --profile archive up -d paperless-db paperless

secrets:
	@echo "POSTGRES_PASSWORD=$$(openssl rand -hex 24)"
	@echo "PDFHUB_API_KEY_PEPPER=$$(openssl rand -hex 32)"
	@echo "PDFHUB_ADMIN_API_KEY=pdfh_admin_$$(openssl rand -hex 32)"
	@echo "PDFHUB_WEBHOOK_MASTER_SECRET=$$(openssl rand -hex 32)"
	@echo "PDFHUB_AUTH_TOKEN_SECRET=$$(openssl rand -hex 48)"
	@echo "PDFHUB_S3_ACCESS_KEY=pdfhub_$$(openssl rand -hex 12)"
	@echo "PDFHUB_S3_SECRET_KEY=$$(openssl rand -hex 32)"
	@echo "PAPERLESS_DB_PASSWORD=$$(openssl rand -hex 24)"
	@echo "PAPERLESS_SECRET_KEY=$$(openssl rand -hex 48)"
