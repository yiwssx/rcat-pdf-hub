# Validation — 0.5.1 stabilization / correctness gate

RCAT PDF Hub 0.5.1 ต้องคงนโยบาย **zero-cost software/CI/CD** และต้องผ่าน validation บนเครื่อง Linux ขององค์กรก่อน merge เข้า `main`

## Policy

- ไม่มี GitHub-hosted Actions workflow
- Validation รันบน institution-owned/local Linux hardware
- Human login กับ machine credential แยกจากกันชัดเจน
- Local Admin ใช้เฉพาะ first-run/development และ production gate ต้องปฏิเสธหากยังเปิดอยู่
- Production human login ใช้ OIDC/LDAP ตาม configuration ขององค์กร
- Service API Key ใช้สำหรับ machine-to-machine integration ไม่ใช่หน้า login ของผู้ใช้
- Frontend ต้อง commit `package-lock.json` และใช้ `npm ci`
- Backend ต้อง commit resolved `requirements.lock`
- Direct Dependabot patch lane ต้องเปลี่ยน **`package.json` + `package-lock.json` เท่านั้น** และ lockfile ต้อง resolve version ที่ขอจริง
- Python/Node/container images และ security baselines เป็น explicit versions
- Next.js baseline = `16.3.3`
- Pillow baseline = `>=12.3.0,<13.0.0`
- S3 mode ต้องมี explicit self-hosted `PDFHUB_S3_ENDPOINT_URL`
- Management ports bind loopback โดย default
- Browser regression, backup/restore/DR, observability และ production Compose flow เป็น mandatory gates
- Warning/deprecation ใน validation ถือเป็น failure

## Required host

- Linux
- Python **3.12**
- Node **24** + npm/npx
- Docker Engine + Docker Compose plugin
- Playwright-compatible Chromium runtime
- Git, curl, flock, openssl, make
- GitHub CLI (`gh`) authenticated to repository

สำหรับเครื่องที่ยังไม่เคยรันโปรเจกต์ ให้ใช้:

```bash
git checkout stabilization/0.5.1-correctness
bash scripts/first-local.sh
```

Script นี้สร้าง random Local Admin password, resolve lockfiles, validation, real runtime smoke, backup, DR และ Local CI ตามลำดับ

## Deterministic dependency locks

สร้าง lockfiles ด้วย runtime version ที่ตรง production:

```bash
make generate-locks
```

ต้องได้:

```text
apps/web/package-lock.json
apps/api/requirements.lock
```

หลังจากสร้างแล้ว `make validate-free` จะไม่ยอมให้ dependency install แก้ package/lock metadata ระหว่าง validation

## Validation commands

```bash
make validate-policy
make validate-ops
make validate-backend
make validate-frontend
make validate-e2e
make validate-compose
make validate-observability
make validate-runtime
```

ทั้งหมด:

```bash
make validate-free
```

### สิ่งที่แต่ละ gate พิสูจน์

`validate-policy`
- release metadata 0.5.1
- lockfile policy
- local-auth/production separation
- stable human principal ownership
- runtime image baselines
- management bindings
- observability/Alertmanager
- release/merge tooling

`validate-ops`
- syntax shell scripts
- compile Python operator tooling

`validate-backend`
- Python 3.12 environment
- install จาก `requirements.lock`
- `pip check`
- pytest
- Alembic fresh/adoption migration paths

`validate-frontend`
- `npm ci`
- TypeScript typecheck
- production Next.js build
- package.json/package-lock.json ต้องไม่ mutate

`validate-e2e`
- Playwright mocked browser flow
- หน้า Human Login ไม่มี Service API Key
- Local username/password reject/accept behavior
- session workspace
- preview
- PDF job
- download
- upload
- 4 tool categories

`validate-compose`
- default Compose
- optional profiles
- NAS
- production resource override
- observability override

`validate-observability`
- Prometheus config/rules
- Alertmanager config

`validate-runtime`
- isolated `pdfhub-validation-<pid>` Compose project
- production container builds
- `/healthz`
- `/readyz` รวม worker readiness
- API tests ใน container
- webhook dispatcher
- **real Local Human Login ผ่าน browser**
- upload PNG
- image-to-PDF ผ่าน RQ worker
- download PDF
- preview PDF
- API-key PDF workload smoke แยกต่างหากเพื่อยืนยัน machine-to-machine path

## Direct dependency validation

```bash
BASE_REF=origin/main make validate-dependency
```

Automatic dependency lane ยอมรับเฉพาะ:

```text
apps/web/package.json
apps/web/package-lock.json
```

โดยต้องเป็น direct dependency เพียงตัวเดียว, forward patch ใน major/minor เดิม และ `package-lock.json` ต้อง resolve version ใหม่ตรงกับ `package.json`

จากนั้น validation ใช้ `npm ci`, typecheck, production build และ Playwright smoke โดยห้าม package/lock mutate

## Local CI

ติดตั้ง executor:

```bash
make install-local-ci
make local-ci-status
make local-ci-doctor
```

แต่ละ cycle:

1. fetch `origin/main`
2. validate main ที่เปลี่ยน
3. บันทึก exact validated main SHA
4. ตรวจ open non-draft PR
5. ปฏิเสธ stale PR base
6. normal PR → full `make validate-free`
7. eligible Dependabot package+lock patch → dependency lane
8. post `local-ci/validate-free` หรือ `local-ci/dependency`
9. recheck main/head SHA ก่อนรับผล
10. auto-merge เฉพาะ eligible Dependabot patch

Normal PR **ไม่ auto-merge**

0.5.1 release PR ต้อง merge ผ่าน:

```bash
PR=<number> make merge-pr
```

`merge-pr` จะยอมทำงานเมื่อ `local-ci/validate-free=success` อยู่บน PR head SHA ปัจจุบันและ base ยังเป็น current `main` เท่านั้น

## Backup / restore correctness

### Backup

```bash
make backup
BACKUP=./backups/<timestamp> make backup-verify
```

Production backup ใช้ quiesced mutation-free window เพื่อให้ PostgreSQL metadata และ storage snapshot อยู่ใน consistency boundary เดียวกัน

### Restore

```bash
PDFHUB_RESTORE_CONFIRM=YES \
BACKUP=./backups/<timestamp> \
make restore
```

Restore จะตรวจ checksum, restore DB/storage, migration/readiness และตรวจ DB ↔ storage file SHA/size consistency

### Disaster recovery drill

```bash
BACKUP=./backups/<timestamp> make dr-drill
```

DR drill ใช้ disposable Compose project และต้องทำ real transaction หลัง restore: upload → process PDF → download → preview

## Monitoring

```bash
make up-observability
make validate-observability
```

ประกอบด้วย:

- Prometheus
- alert rules
- self-hosted Alertmanager
- local durable alert sink
- OpenTelemetry Collector

Rules ครอบคลุม API availability, 5xx, p95 latency, worker/queue state และ repeated job failures

## Load validation

Readiness load:

```bash
URL=http://localhost:8080 \
LOAD_PATH=/readyz \
REQUESTS=100 CONCURRENCY=10 \
make load-smoke
```

PDF transaction load:

```bash
URL=http://localhost:8080 \
API_KEY=<service-or-bootstrap-key> \
make pdf-workload-smoke
```

## Release readiness

Code-only:

```bash
PDFHUB_RELEASE_MODE=code make release-readiness
```

Production:

```bash
BACKUP=./backups/<timestamp> \
URL=https://pdf.example.org \
make release-readiness
```

Production mode ต้องผ่าน:

- full repository validation
- Local CI doctor
- HTTPS public URL
- Secure session cookie
- Local Human Login = **off**
- non-placeholder secrets
- backup verification
- DR drill
- readiness load smoke
- real PDF workload smoke

## 0.5.1 acceptance baseline

- Local Development login ใช้ username/password จาก `.env`
- Service API Key ไม่แสดงเป็น human login
- Production gate ปิด local auth
- stable OIDC/LDAP tenant ownership
- deterministic frontend/backend locks
- worker-aware readiness + stale-job reconciliation
- atomic quota protection
- quiesced backup + restore consistency verification
- real DR PDF transaction
- Alertmanager notification path
- production resource isolation
- Desktop/Mobile tool UI แบ่ง 14 เครื่องมือเป็น 4 กลุ่มและใช้ colorful distinguishable icon system
- Local CI required status ก่อน merge
- ไม่มี paid CI/cloud requirement
