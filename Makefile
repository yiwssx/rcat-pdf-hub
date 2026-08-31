.PHONY: up up-nas down logs ps test build config secrets cleanup migrate scale-workers up-s3 up-security up-observability up-archive validate-free validate-policy validate-ops validate-backend validate-frontend validate-e2e validate-compose validate-runtime validate-dependency install-e2e-browser local-ci-cycle local-ci-doctor install-local-ci uninstall-local-ci local-ci-status backup backup-verify restore dr-drill load-smoke install-backup uninstall-backup backup-status release-readiness

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

validate-ops:
	bash scripts/validate-free.sh operations

validate-backend:
	bash scripts/validate-free.sh backend

validate-frontend:
	bash scripts/validate-free.sh frontend

validate-e2e:
	bash scripts/validate-free.sh e2e

validate-compose:
	bash scripts/validate-free.sh compose

validate-runtime:
	bash scripts/validate-free.sh runtime

validate-dependency:
	bash scripts/validate-direct-dependency.sh "$${BASE_REF:-origin/main}"

install-e2e-browser:
	cd apps/web && npx playwright install --only-shell chromium

local-ci-cycle:
	bash scripts/local-ci-cycle.sh

local-ci-doctor:
	bash scripts/local-ci-doctor.sh

install-local-ci:
	bash scripts/install-local-ci-user.sh

uninstall-local-ci:
	bash scripts/uninstall-local-ci-user.sh

local-ci-status:
	@systemctl --user status rcat-pdf-hub-local-ci.timer --no-pager || true
	@systemctl --user status rcat-pdf-hub-local-ci.service --no-pager || true

backup:
	bash scripts/backup.sh "$${BACKUP:-}"

backup-verify:
	bash scripts/verify-backup.sh "$${BACKUP:?set BACKUP=/path/to/backup}"

restore:
	bash scripts/restore.sh "$${BACKUP:?set BACKUP=/path/to/backup}"

dr-drill:
	bash scripts/dr-drill.sh "$${BACKUP:?set BACKUP=/path/to/backup}"

load-smoke:
	python3 scripts/load-smoke.py --url "$${URL:?set URL=http://host:port}" --path "$${LOAD_PATH:-/healthz}" --requests "$${REQUESTS:-100}" --concurrency "$${CONCURRENCY:-10}" --max-error-rate "$${MAX_ERROR_RATE:-0.01}" --max-p95-ms "$${MAX_P95_MS:-1500}"

install-backup:
	bash scripts/install-backup-user.sh

uninstall-backup:
	bash scripts/uninstall-backup-user.sh

backup-status:
	@systemctl --user status rcat-pdf-hub-backup.timer --no-pager || true
	@systemctl --user status rcat-pdf-hub-backup.service --no-pager || true

release-readiness:
	bash scripts/release-readiness.sh

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
	@echo "PDFHUB_DOWNLOAD_SIGNING_SECRET=$$(openssl rand -hex 48)"
	@echo "PDFHUB_S3_ACCESS_KEY=pdfhub_$$(openssl rand -hex 12)"
	@echo "PDFHUB_S3_SECRET_KEY=$$(openssl rand -hex 32)"
	@echo "PAPERLESS_DB_PASSWORD=$$(openssl rand -hex 24)"
	@echo "PAPERLESS_SECRET_KEY=$$(openssl rand -hex 48)"
