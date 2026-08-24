# Phase 3 — Production & Enterprise Integration

RCAT PDF Hub **0.3.0** is the completed Phase 3 baseline. It extends the Phase 2 API-key service model into a production-oriented, fully self-hosted platform while preserving zero-cost deployment and validation requirements.

## Delivered capabilities

- OIDC Authorization Code + PKCE SSO and validated OIDC bearer tokens
- LDAP / Active Directory credential login with short-lived HttpOnly PDF Hub sessions
- Admin-group mapping to privileged `*` scope; normal human identities receive configured scopes
- Local/NAS storage and S3-compatible binary storage with an explicit self-hosted endpoint
- ClamAV streaming malware scanning for uploads and processed outputs
- Configurable RQ queue and horizontally scalable stateless workers
- Prometheus metrics and optional OTLP HTTP tracing export
- Paperless-ngx manual and automatic downstream archive integration
- Alembic schema migrations with safe adoption of Phase 2 databases
- Production readiness endpoint at `/readyz`
- Optional Docker Compose profiles for S3, malware scanning, observability and Paperless-ngx
- Zero-cost local validation and optional always-on local CI executor

## Zero-cost rule

The project must not require paid runners, paid CI/CD, paid cloud storage, paid monitoring or paid build services. Bundled/default deployment paths use institution-owned hardware and free/open-source software.

S3 mode requires an explicit `PDFHUB_S3_ENDPOINT_URL`. The application refuses S3 mode without that endpoint so it cannot silently fall back to a commercial cloud object-storage endpoint.

## Deployment modes

### Local volume

```bash
make up
```

### NAS

Set `PDFHUB_NAS_PATH=/srv/pdfhub-data` then:

```bash
make up-nas
```

The same NAS path must be mounted on every host when workers are distributed across hosts.

### Self-hosted S3-compatible storage

The bundled target is SeaweedFS:

```bash
make up-s3
```

Then set:

```env
PDFHUB_STORAGE_BACKEND=s3
PDFHUB_S3_ENDPOINT_URL=http://seaweedfs:8333
PDFHUB_S3_BUCKET=pdfhub
PDFHUB_S3_ACCESS_KEY=<random>
PDFHUB_S3_SECRET_KEY=<random>
PDFHUB_S3_AUTO_CREATE_BUCKET=true
```

Other self-hosted S3-compatible endpoints such as Ceph RGW can be used. An endpoint URL is mandatory.

### Horizontal workers

On a single Compose host:

```bash
WORKERS=4 make scale-workers
```

For multiple worker hosts, all workers must share PostgreSQL and Valkey and use either the same shared NAS or the same self-hosted S3-compatible storage.

## OIDC SSO

Use an existing institutional OIDC provider or a free self-hosted identity provider such as Keycloak/Authentik. Configure callback:

```text
https://pdf.example.org/api/v1/auth/oidc/callback
```

Then set:

```env
PDFHUB_PUBLIC_BASE_URL=https://pdf.example.org
PDFHUB_SESSION_COOKIE_SECURE=true
PDFHUB_OIDC_ENABLED=true
PDFHUB_OIDC_ISSUER=https://id.example.org/realms/rcat
PDFHUB_OIDC_CLIENT_ID=pdf-hub
PDFHUB_OIDC_CLIENT_SECRET=<secret-if-confidential-client>
PDFHUB_OIDC_GROUP_CLAIM=groups
PDFHUB_ADMIN_GROUPS=pdfhub-admins
```

Start login at:

```text
GET /api/v1/auth/oidc/login
```

The implementation uses state, nonce and PKCE, validates issuer, audience, expiration and asymmetric signatures, and stores only a short-lived signed PDF Hub session in an HttpOnly cookie.

## LDAP / Active Directory

Prefer LDAPS:

```env
PDFHUB_LDAP_ENABLED=true
PDFHUB_LDAP_URL=ldaps://directory.example.org:636
PDFHUB_LDAP_BASE_DN=ou=People,dc=example,dc=org
PDFHUB_LDAP_BIND_DN=cn=lookup,dc=example,dc=org
PDFHUB_LDAP_BIND_PASSWORD=<secret>
PDFHUB_LDAP_USER_FILTER=(uid={username})
PDFHUB_LDAP_GROUP_BASE_DN=ou=Groups,dc=example,dc=org
PDFHUB_LDAP_GROUP_FILTER=(member={user_dn})
```

Login API:

```text
POST /api/v1/auth/ldap/login
```

with JSON `{"username":"...","password":"..."}`. Passwords are used only for the bind and are never stored.

## ClamAV

```bash
make up-security
```

Then enable:

```env
PDFHUB_CLAMAV_ENABLED=true
PDFHUB_CLAMAV_FAIL_CLOSED=true
```

Uploads are staged locally, streamed to `clamd`, and committed to storage only after a clean result. Processed PDF outputs are scanned before becoming a `FileRecord`.

## Observability

Prometheus metrics are served internally at `api:8000/metrics`. Start the bundled stack:

```bash
make up-observability
```

The main metrics include HTTP request count/duration, job states, file lifecycle, malware outcomes, archive submissions and RQ queue depth.

For traces, set a self-hosted OTLP HTTP traces endpoint:

```env
PDFHUB_OTEL_ENDPOINT=http://otel-collector:4318/v1/traces
```

The bundled collector can feed a self-hosted Jaeger or Tempo-compatible backend. Paid observability services are not part of the supported default deployment path.

## Paperless-ngx

The bundled optional profile can be started with:

```bash
make up-archive
```

Create a Paperless API token and set:

```env
PDFHUB_PAPERLESS_ENABLED=true
PDFHUB_PAPERLESS_URL=http://paperless:8000
PDFHUB_PAPERLESS_TOKEN=<paperless-token>
PDFHUB_PAPERLESS_AUTO_ARCHIVE=false
```

Manual archive:

```text
POST /api/v1/integrations/paperless/{file_id}
```

with scope `archive:paperless`. Set `PDFHUB_PAPERLESS_AUTO_ARCHIVE=true` to submit every successfully processed output without making a Paperless outage fail the PDF job.

## Database migration

Production API startup runs Alembic before Uvicorn. Existing Phase 2 databases are detected, stamped at the Phase 2 baseline, and upgraded without replaying table creation.

Manual migration:

```bash
make migrate
```

Back up PostgreSQL and file/object storage together before release upgrades.

## Readiness and operational checks

- `/healthz` verifies the database/Valkey health contract.
- `/readyz` additionally verifies configured storage, Gotenberg and ClamAV; optional Paperless status is reported separately.
- `/api/v1/integrations/status` shows enabled integrations to authenticated callers.
- `make validate-free` performs warning-free backend, frontend, Compose and runtime validation on institution-owned hardware.
- `make install-local-ci` installs the optional zero-cost local polling executor for continuous validation.

## Security checklist before Internet exposure

- Use a real domain and TLS at Caddy or an upstream reverse proxy.
- Set `PDFHUB_SESSION_COOKIE_SECURE=true` behind HTTPS.
- Generate all values printed by `make secrets`; never keep example secrets.
- Prefer OIDC SSO over LDAP password exchange when an IdP is available.
- Prefer LDAPS when LDAP is enabled.
- Keep bootstrap admin as a break-glass credential, not an application credential.
- Use encrypted NAS volumes or self-hosted S3 encryption when supported.
- Enable ClamAV fail-closed for untrusted uploads.
- Restrict direct access to PostgreSQL, Valkey, Gotenberg, ClamAV and object storage.
- Back up PostgreSQL and storage together according to the same recovery point objective.

## Completion status

Phase 3 functionality is delivered in `0.3.0`. Remaining items after this baseline are enhancements rather than Phase 3 blockers.
