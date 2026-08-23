.PHONY: up down logs ps test build config secrets cleanup

up:
	docker compose up -d --build

down:
	docker compose down

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

secrets:
	@echo "POSTGRES_PASSWORD=$$(openssl rand -hex 24)"
	@echo "PDFHUB_API_KEY_PEPPER=$$(openssl rand -hex 32)"
	@echo "PDFHUB_ADMIN_API_KEY=pdfh_admin_$$(openssl rand -hex 32)"
	@echo "PDFHUB_WEBHOOK_MASTER_SECRET=$$(openssl rand -hex 32)"
