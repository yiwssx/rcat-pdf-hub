.PHONY: up up-nas down logs ps test build config secrets cleanup migrate scale-workers up-s3 up-security up-observability up-archive validate-free validate-policy validate-backend validate-frontend validate-compose validate-runtime validate-dependency local-ci-cycle install-local-ci uninstall-local-ci local-ci-status

up:
	docker compose up -d --build

up-nas:
	docker compose -f docker-compose.yml -f docker-compose.nas.yml up -d --build

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

validate-free:
	python3 scripts/validate-release-policy.py
	bash scripts/validate-free.sh all

validate-policy:
	python3 scripts/validate-release-policy.py
	bash scripts/validate-free.sh policy

validate-backend:
	bash scripts/validate-free.sh backend

validate-frontend:
	bash scripts/validate-free.sh frontend

validate-compose:
	bash scripts/validate-free.sh compose

validate-runtime:
	bash scripts/validate-free.sh runtime

validate-dependency:
	bash scripts/validate-direct-dependency.sh "$${BASE_REF:-origin/main}"

local-ci-cycle:
	bash scripts/local-ci-cycle.sh

install-local-ci:
	bash scripts/install-local-ci-user.sh

uninstall-local-ci:
	bash scripts/uninstall-local-ci-user.sh

local-ci-status:
	@systemctl --user status rcat-pdf-hub-local-ci.timer --no-pager || true
	@systemctl --user status rcat-pdf-hub-local-ci.service --no-pager || true

cleanup:
	docker compose run --rm cleanup python -m app.cleanup

migrate:
	docker compose run --rm api python -c 'from app.migrate import run_migrations; run_migrations()'

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
