#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT_RELEASE = "0.5.0"
NEXT_SECURITY_MIN = (16, 3, 3)
NEXT_SECURITY_MAX_EXCLUSIVE = (16, 4, 0)
PILLOW_MIN = (12, 3, 0)
PILLOW_MAX_EXCLUSIVE = (13, 0, 0)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def pinned_requirement_version(requirements: str, package: str) -> tuple[int, int, int]:
    match = re.search(
        rf"^{re.escape(package)}==(\d+)\.(\d+)\.(\d+)\s*$",
        requirements,
        flags=re.M,
    )
    assert match, f"{package} must be pinned exactly as x.y.z"
    return tuple(int(part) for part in match.groups())


def semver_version(value: str, label: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value)
    assert match, f"{label} must be exact x.y.z: {value}"
    return tuple(int(part) for part in match.groups())


# Zero-cost CI policy: all GitHub-hosted workflows must be explicitly reviewed.
# Dependabot automation is tightly scoped; normal PR validation remains read-only
# apart from CodeQL security-event publishing.
workflow_dir = ROOT / ".github" / "workflows"
workflow_files: list[str] = []
if workflow_dir.exists():
    workflow_files = sorted(
        p.relative_to(ROOT).as_posix()
        for p in workflow_dir.rglob("*")
        if p.suffix in {".yml", ".yaml"}
    )
assert workflow_files == [
    ".github/workflows/codeql.yml",
    ".github/workflows/core-api-ci.yml",
    ".github/workflows/dependabot-patch-automerge.yml",
    ".github/workflows/dependabot-python-security.yml",
    ".github/workflows/dependency-review.yml",
    ".github/workflows/web-ci.yml",
], f"Only explicitly reviewed workflows are allowed: {workflow_files}"

codeql_workflow = read(".github/workflows/codeql.yml")
for required in ("pull_request:", "contents: read", "security-events: write", "github/codeql-action/init@v4", "github/codeql-action/analyze@v4"):
    assert required in codeql_workflow, f"CodeQL workflow missing guard: {required}"
assert "pull_request_target:" not in codeql_workflow

dependency_review_workflow = read(".github/workflows/dependency-review.yml")
for required in ("pull_request:", "contents: read", "actions/dependency-review-action@v4", "fail-on-severity: high"):
    assert required in dependency_review_workflow, f"Dependency Review workflow missing guard: {required}"
assert "contents: write" not in dependency_review_workflow
assert "pull_request_target:" not in dependency_review_workflow

web_ci_workflow = read(".github/workflows/web-ci.yml")
for required in ("pull_request:", "contents: read", "cache-dependency-path: apps/web/package-lock.json", "npm ci --no-audit --no-fund", "npm run typecheck", "npm run build", "npm run test:e2e"):
    assert required in web_ci_workflow, f"Web CI workflow missing guard: {required}"
assert "contents: write" not in web_ci_workflow
assert "pull-requests: write" not in web_ci_workflow
assert "pull_request_target:" not in web_ci_workflow

core_api_ci_workflow = read(".github/workflows/core-api-ci.yml")
for required in ("pull_request:", "contents: read", "python3 scripts/check-python-lock.py", "docker build -t rcat-pdf-hub-api-test apps/api", "python -m pytest -q"):
    assert required in core_api_ci_workflow, f"Core API CI workflow missing guard: {required}"
assert "contents: write" not in core_api_ci_workflow
assert "pull-requests: write" not in core_api_ci_workflow
assert "pull_request_target:" not in core_api_ci_workflow

dependency_workflow = read(".github/workflows/dependabot-patch-automerge.yml")
for required in (
    "pull_request:",
    "paths:\n      - 'apps/web/package.json'\n      - 'apps/web/package-lock.json'",
    "github.event.pull_request.user.login == 'dependabot[bot]'",
    'git show "${HEAD_SHA}:apps/web/package-lock.json" > apps/web/package-lock.json',
    "contents: read",
    "pull-requests: write",
    "check-direct-dependency.py",
    "validate-direct-dependency.sh",
    "merge_method=squash",
):
    assert required in dependency_workflow, f"Dependabot npm workflow missing guard: {required}"
assert "pull_request_target:" not in dependency_workflow, "Dependabot npm workflow must not use pull_request_target"

python_security_workflow = read(".github/workflows/dependabot-python-security.yml")
for required in (
    "pull_request:",
    "paths:\n      - 'apps/api/requirements.txt'\n      - 'apps/api/requirements.lock'",
    "github.event.pull_request.user.login == 'dependabot[bot]'",
    "contents: read",
    "check-python-security-dependency.py",
    "apps/api/requirements.lock",
    "make validate-free",
):
    assert required in python_security_workflow, f"Dependabot Python security workflow missing guard: {required}"
assert "pull_request_target:" not in python_security_workflow, "Python security workflow must not use pull_request_target"
assert "contents: write" not in python_security_workflow, "Python security workflow must stay read-only"
assert "pull-requests: write" not in python_security_workflow, "Python security workflow must not gain PR write permission"
assert "merge_method" not in python_security_workflow, "Python security workflow must never auto-merge"

# Version-update automation remains direct npm patch-only. Security/nonstandard PRs use full validation.
dependabot = read(".github/dependabot.yml")
assert len(re.findall(r"^\s*-\s+package-ecosystem:", dependabot, flags=re.M)) == 1
assert re.search(r"^\s*-\s+package-ecosystem:\s*npm\s*$", dependabot, flags=re.M)
assert re.search(r"^\s+directory:\s*/apps/web\s*$", dependabot, flags=re.M)
assert re.search(r"^\s+-\s+dependency-type:\s*direct\s*$", dependabot, flags=re.M)
assert re.search(r"^\s+open-pull-requests-limit:\s*1\s*$", dependabot, flags=re.M)
assert re.search(r"^\s+interval:\s*daily\s*$", dependabot, flags=re.M)
assert "version-update:semver-minor" in dependabot
assert "version-update:semver-major" in dependabot
for forbidden in ("package-ecosystem: pip", "package-ecosystem: docker", "package-ecosystem: github-actions"):
    assert forbidden not in dependabot, forbidden

package = json.loads(read("apps/web/package.json"))
lock = json.loads(read("apps/web/package-lock.json"))
assert lock.get("lockfileVersion") == 3, "Frontend npm lockfile must use lockfileVersion 3"
lock_root = lock.get("packages", {}).get("")
assert isinstance(lock_root, dict), "Frontend npm lockfile is missing its root package entry"
for key in ("name", "version"):
    assert lock_root.get(key) == package.get(key), f"Frontend lockfile root {key} must match package.json"
for section in ("dependencies", "devDependencies"):
    assert lock_root.get(section, {}) == package.get(section, {}), (
        f"Frontend lockfile root {section} must match package.json"
    )
assert package["version"] == CURRENT_RELEASE
for section in ("dependencies", "devDependencies"):
    for name, version in package.get(section, {}).items():
        assert re.fullmatch(r"\d+\.\d+\.\d+", version), f"{name} must be exact x.y.z: {version}"
next_version = semver_version(package["dependencies"].get("next", ""), "Next.js")
assert NEXT_SECURITY_MIN <= next_version < NEXT_SECURITY_MAX_EXCLUSIVE, (
    "Next.js must stay on the reviewed 16.3.x patch line "
    f">={'.'.join(map(str, NEXT_SECURITY_MIN))}; found {'.'.join(map(str, next_version))}"
)
assert "@playwright/test" in package.get("devDependencies", {}), "Playwright smoke coverage is required"
assert package.get("scripts", {}).get("test:e2e") == "playwright test tests/e2e/pdf-hub.smoke.spec.ts tests/e2e/pdf-hub.ui-regression.spec.ts"
assert package.get("scripts", {}).get("test:e2e:stack") == "playwright test tests/e2e/pdf-hub.stack.spec.ts"
for required in (
    "apps/web/playwright.config.ts",
    "apps/web/tests/e2e/pdf-hub.smoke.spec.ts",
    "apps/web/tests/e2e/pdf-hub.ui-regression.spec.ts",
    "apps/web/tests/e2e/pdf-hub.stack.spec.ts",
    "apps/web/app/web-auth/session/route.ts",
    "apps/api/app/routers/internal.py",
):
    assert (ROOT / required).exists(), f"Missing browser/session component: {required}"

# The mocked browser gate must validate cookie-session propagation across protected calls.
smoke = read("apps/web/tests/e2e/pdf-hub.smoke.spec.ts")
assert "requireSession" in smoke
assert "/web-auth/session" in smoke
assert 'getByLabel("Service API Key")' in smoke and "toHaveCount(0)" in smoke
for protected_flow in ("integrations/status", "files?limit=200&offset=0", "jobs?limit=50", "/preview", "/pdf/compress", "/download"):
    assert protected_flow in smoke, f"Mocked browser smoke is missing protected flow: {protected_flow}"

# Runtime/container baselines are intentionally frozen and changed only by explicit developer review.
requirements = read("apps/api/requirements.txt")
python_lock = read("apps/api/requirements.lock")
assert "--hash=sha256:" in python_lock, "Python dependency lock must include SHA-256 hashes"
for raw in requirements.splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    assert "==" in line, f"Direct Python dependency must be exactly pinned: {line}"
    requirement, version = line.split("==", 1)
    name = requirement.split("[", 1)[0]
    pattern = rf"(?mi)^{re.escape(name)}=={re.escape(version)}(?:\s+\\)?$"
    assert re.search(pattern, python_lock), f"Python lock is missing direct pin {line}"
pillow_version = pinned_requirement_version(requirements, "Pillow")
assert PILLOW_MIN <= pillow_version < PILLOW_MAX_EXCLUSIVE, (
    f"Pillow must remain on the reviewed secure 12.x line >= {'.'.join(map(str, PILLOW_MIN))}; "
    f"found {'.'.join(map(str, pillow_version))}"
)
api_dockerfile = read("apps/api/Dockerfile")
web_dockerfile = read("apps/web/Dockerfile")
assert api_dockerfile.startswith("FROM python:3.12.14-slim-bookworm\n")
assert "COPY requirements.txt requirements.lock ./" in api_dockerfile
assert "pip install --no-cache-dir --require-hashes -r requirements.lock" in api_dockerfile
assert web_dockerfile.count("FROM node:24.19.0-alpine3.24") == 3
assert "COPY package.json package-lock.json ./" in web_dockerfile
assert "RUN npm ci --no-audit --no-fund" in web_dockerfile

compose = read("docker-compose.yml")
expected_images = {
    "postgres:18.6-bookworm",
    "valkey/valkey:8.1.9-alpine3.24",
    "gotenberg/gotenberg:8.34.0",
    "caddy:2.11.4-alpine",
    "chrislusf/seaweedfs:4.44",
    "clamav/clamav:1.5.4",
    "prom/prometheus:v3.13.2",
    "otel/opentelemetry-collector-contrib:0.159.0",
    "ghcr.io/paperless-ngx/paperless-ngx:3.0.5",
}
for image in expected_images:
    assert f"image: {image}" in compose, f"Missing frozen image baseline: {image}"
for floating in ("image: valkey/valkey:8-alpine", "image: caddy:2-alpine", "image: clamav/clamav:stable", ":latest"):
    assert floating not in compose, f"Floating image tag is forbidden: {floating}"
assert 'command: ["python", "-m", "app.webhook_runner"]' in compose
assert "PDFHUB_DOWNLOAD_SIGNING_SECRET" in compose

# Optional management UIs/collectors must not bind to every host interface by default.
management_bind = "${PDFHUB_MANAGEMENT_BIND_HOST:-127.0.0.1}"
for mapping in (
    f'{management_bind}:${{PDFHUB_PROMETHEUS_PORT:-9090}}:9090',
    f'{management_bind}:${{PDFHUB_OTEL_GRPC_PORT:-4317}}:4317',
    f'{management_bind}:${{PDFHUB_OTEL_HTTP_PORT:-4318}}:4318',
    f'{management_bind}:${{PAPERLESS_HTTP_PORT:-8001}}:8000',
):
    assert mapping in compose, f"Management port is not loopback-bound by default: {mapping}"
assert "PDFHUB_MANAGEMENT_BIND_HOST=127.0.0.1" in read(".env.example")

# The internal session-minting endpoint must stay off Caddy's public API matcher.
caddy = read("ops/caddy/Caddyfile")
assert "@api path /api/*" in caddy
assert "/internal/*" not in caddy, "Internal Web Console session endpoint must not be reverse-proxied publicly"

# Phase 5 observability has local alert rules and the Prometheus container actually loads them.
prometheus = read("ops/prometheus/prometheus.yml")
alerts = read("ops/prometheus/alerts.yml")
assert "/etc/prometheus/alerts.yml" in prometheus
assert "./ops/prometheus/alerts.yml:/etc/prometheus/alerts.yml:ro" in compose
for alert in ("PdfHubApiDown", "PdfHubHighServerErrorRate", "PdfHubP95LatencyHigh", "PdfHubQueueBacklog", "PdfHubRepeatedJobFailures"):
    assert f"alert: {alert}" in alerts, f"Missing Phase 5 Prometheus alert: {alert}"

# Frontend human authentication must be session based; service API keys stay M2M-only.
web_app = read("apps/web/app/components/pdf-hub-app.tsx")
web_api = read("apps/web/lib/api.ts")
assert 'aria-label="Service API Key"' not in web_app
assert 'placeholder="Service API Key' not in web_app
assert "apiKeyDraft" not in web_app
assert "connectApiKey" not in web_app
assert "getMe(SESSION_AUTH)" in web_app
assert 'request("/web-auth/session"' in web_api
assert "identity?.is_admin" in web_app
assert not (ROOT / "apps/web/app/components/pdf-hub-console.tsx").exists(), "Superseded console implementation must stay removed"

# Phase 6 workstream state must remain repository-owned and resumable.
phase6_tracker_path = "docs/workstreams/phase6-production-hardening-tracker.md"
assert (ROOT / phase6_tracker_path).exists(), f"Missing Phase 6 tracker: {phase6_tracker_path}"
phase6_tracker = read(phase6_tracker_path)
for marker in (
    "Tracker role: **canonical source of truth for Phase 6 execution status**",
    "Phase 6 target release: `0.6.0`",
    "## Activity log",
    "## Current next action",
):
    assert marker in phase6_tracker, f"Phase 6 tracker missing governance marker: {marker}"

# Release metadata must agree while retaining prior completed baselines.
assert f'version="{CURRENT_RELEASE}"' in read("apps/api/app/main.py")
assert f"{CURRENT_RELEASE} — Phase 5 production maturity" in read("README.md")
assert "completed Phase 4 feature baseline" in read("PHASE4.md")
phase5 = read("PHASE5.md")
for section in ("Phase 5A", "Phase 5B", "Phase 5C"):
    assert section in phase5, f"Missing {section} completion documentation"
assert f"## {CURRENT_RELEASE}" in read("CHANGELOG.md")

# Phase 4 feature components remain part of the production foundation.
for required in (
    "apps/api/app/downloads.py",
    "apps/api/app/webhook_runner.py",
    "apps/api/alembic/versions/0003_phase4_webhook_deliveries.py",
    "apps/api/tests/test_downloads.py",
    "apps/api/tests/test_image_conversion.py",
    "apps/api/tests/test_webhook_delivery.py",
):
    assert (ROOT / required).exists(), f"Missing Phase 4 component: {required}"

# Phase 5 operations must be executable repository components, not documentation-only promises.
phase5_ops = (
    "scripts/backup.sh",
    "scripts/verify-backup.sh",
    "scripts/restore.sh",
    "scripts/dr-drill.sh",
    "scripts/load-smoke.py",
    "scripts/release-readiness.sh",
    "scripts/install-backup-user.sh",
    "scripts/uninstall-backup-user.sh",
    "scripts/local-ci-doctor.sh",
)
for required in phase5_ops:
    assert (ROOT / required).exists(), f"Missing Phase 5 operations component: {required}"

backup = read("scripts/backup.sh")
restore = read("scripts/restore.sh")
verify_backup = read("scripts/verify-backup.sh")
assert "pg_dump" in backup and "SHA256SUMS" in backup and "PDFHUB_STORAGE_BACKEND" in backup
assert "PDFHUB_RESTORE_CONFIRM" in restore and "pg_restore" in restore and "FLUSHDB" in restore
assert "sha256sum -c SHA256SUMS" in verify_backup and "PGDMP" in verify_backup

# Zero-cost validation must cover code, browser behavior, operations and the real Compose stack.
for required in (
    "scripts/check-direct-dependency.py",
    "scripts/check-python-security-dependency.py",
    "scripts/check-python-lock.py",
    "scripts/compile-python-lock.sh",
    "scripts/supply-chain.sh",
    "scripts/validate-free.sh",
    "scripts/validate-direct-dependency.sh",
    "scripts/local-ci-cycle.sh",
    "scripts/local-ci-prs.sh",
    "scripts/local-ci-dependabot.sh",
    "scripts/install-local-ci-user.sh",
    "scripts/uninstall-local-ci-user.sh",
):
    assert (ROOT / required).exists(), f"Missing zero-cost validation component: {required}"
validate_free = read("scripts/validate-free.sh")
assert "python3 scripts/validate-release-policy.py" in validate_free
assert "operations()" in validate_free
assert "npm run test:e2e:stack" in validate_free
assert "npm ci --no-audit --no-fund" in validate_free
assert "check-python-security-dependency.py" in validate_free
assert "check-python-lock.py" in validate_free
assert "--require-hashes -r apps/api/requirements.lock" in validate_free
assert "Pillow==" not in validate_free, "Dependency policy must not be duplicated in validate-free.sh"

makefile = read("Makefile")
assert "lock-python:" in makefile and "scripts/compile-python-lock.sh" in makefile
for target in ("validate-supply-chain-source:", "validate-supply-chain-images:", "validate-supply-chain:"):
    assert target in makefile, f"Missing supply-chain Make target: {target}"

supply_chain = read("scripts/supply-chain.sh")
for marker in (
    "aquasec/trivy:0.75.0",
    "--format cyclonedx",
    "--severity CRITICAL",
    "--ignore-unfixed",
    "--exit-code 1",
    "source.cdx.json",
    "${label}-image.cdx.json",
    "scan_one_image",
):
    assert marker in supply_chain, f"Supply-chain gate missing policy marker: {marker}"
assert "artifacts/" in read(".gitignore"), "Generated supply-chain artifacts must stay untracked"
assert (ROOT / "docs/security/supply-chain-policy.md").exists(), "Missing supply-chain policy documentation"

release_readiness = read("scripts/release-readiness.sh")
assert "make validate-supply-chain-source" in release_readiness
assert "make validate-supply-chain-images" in release_readiness

validate_direct = read("scripts/validate-direct-dependency.sh")
assert 'python3 scripts/check-direct-dependency.py "${BASE_REF}" HEAD' in validate_direct
assert "npm run test:e2e" in validate_direct, "Direct npm patches must pass browser smoke"
assert "npm ci --no-audit --no-fund" in validate_direct, "Direct npm patches must install from the committed lockfile"

local_ci_prs = read("scripts/local-ci-prs.sh")
local_ci_dependabot = read("scripts/local-ci-dependabot.sh")
local_ci_cycle = read("scripts/local-ci-cycle.sh")
local_ci_install = read("scripts/install-local-ci-user.sh")
assert "local-ci/validate-free" in local_ci_prs
assert "base is stale" in local_ci_prs
assert "local-ci/dependency" in local_ci_dependabot
assert "validate-direct-dependency.sh" in local_ci_dependabot
assert "gh auth status" in local_ci_cycle
assert "continuing PR routing" in local_ci_cycle
assert "skipping local dependency auto-merge while current main is failing" in local_ci_cycle
assert "gh auth status" in local_ci_install

# User-facing defaults must not recommend known paid cloud services.
for path in ("README.md", "PHASE3.md", "PHASE4.md", "PHASE5.md", "CHANGELOG.md", "VALIDATION.md", ".env.example", "docker-compose.yml"):
    text = read(path)
    for term in ("AWS S3", "Grafana Cloud", "Entra ID", "Google Workspace OIDC"):
        assert term not in text, f"Paid-cloud reference {term!r} remains in {path}"

storage = read("apps/api/app/storage.py")
assert "_require_self_hosted_s3_endpoint" in storage
assert "explicit self-hosted PDFHUB_S3_ENDPOINT_URL" in storage

print("release policy: PASS")
