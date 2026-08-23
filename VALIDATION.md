# Validation Status

Validated in the build workspace on 2026-08-23:

- Python source syntax: `python -m compileall` — PASS
- Backend unit tests: `python -m pytest -q` — **2 passed**
- `docker-compose.yml` YAML parsing — PASS (7 services)
- Git whitespace check: `git diff --cached --check` — PASS
- Manual review of API-key scope checks and per-service file ownership checks — PASS

Not fully executable in the build workspace:

- Docker Compose runtime build/start: Docker Compose is not available in the workspace.
- Fresh `pip install` / `npm install`: outbound package-network access is blocked in the workspace.
- Next.js production build: dependencies could not be fetched for the reason above.
- End-to-end qpdf/OCRmyPDF/Gotenberg processing: worker dependencies/services are installed during Docker build, which could not be run here.

Recommended first deployment verification:

```bash
cp .env.example .env
make secrets
# Put generated secrets into .env
make config
make up
make ps
curl http://localhost:8080/healthz
```

Then use `/docs` to create/upload a test PDF and execute merge/OCR/compress before exposing the service beyond the local network.
