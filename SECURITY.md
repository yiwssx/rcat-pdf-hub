# Security notes

RCAT PDF Hub processes untrusted document uploads. Treat the processing plane as a security boundary.

## Production requirements

- Keep FastAPI internal-only except through the reviewed Caddy routes; never publish `/internal/*` directly.
- Keep Gotenberg, PostgreSQL and Valkey on the internal Docker network only.
- Use a long random `PDFHUB_API_KEY_PEPPER`, bootstrap admin key and webhook master secret.
- Use scoped service API keys for machine-to-machine clients; do not share one service key across unrelated systems and never ask human users to paste one into the Web Console.
- For Internet-facing Web Console deployments, enable OIDC or LDAP. Enabling either automatically disables anonymous Web Console session bootstrap.
- If automatic Web Console sessions are retained, restrict Caddy access to the intended institutional or trusted network.
- Keep `PDFHUB_WEBHOOK_ALLOWED_HOSTS` narrow. Prefer exact hostnames over `*` and restrict worker egress at the network layer.
- Put the public endpoint behind TLS and an edge rate limiter/WAF.
- Back up PostgreSQL and the PDF volume according to institutional retention policy.
- Add malware scanning before accepting documents from untrusted public users.

## Secret and session handling

- Plaintext service API keys are returned once and are never written to the audit log.
- The database stores a deterministic HMAC-SHA-256 digest of service API keys keyed by `PDFHUB_API_KEY_PEPPER`; plaintext service keys are not stored.
- Webhook signing keys are derived per service from a master secret and are not stored in the database.
- The Web Console does not accept or retain service API keys. Human browser access uses an HttpOnly session cookie.
- When neither OIDC nor LDAP is enabled, Next.js obtains an isolated non-admin Web Console session from the internal FastAPI endpoint over the private Docker network. The resulting principal receives the configured human scopes, never `*` or administrator identity.
- Direct `/api/v1/*` calls remain authenticated and continue to accept scoped service API keys for machine-to-machine use.

## Webhook SSRF controls

Webhook URLs are administrator-controlled and must match `PDFHUB_WEBHOOK_ALLOWED_HOSTS`. URLs containing credentials are rejected. Network-level egress filtering is still recommended because DNS can change after validation.

## Software supply chain

- Frontend dependencies are installed from the committed npm lockfile with `npm ci`.
- Python runtime/test dependencies are installed from a committed hash-pinned lock with `pip --require-hashes`.
- `scripts/supply-chain.sh` uses pinned Trivy `0.75.0` to generate CycloneDX SBOMs and vulnerability reports for source dependencies and production images.
- Fixable CRITICAL dependency/image vulnerabilities block the supply-chain gate. HIGH and unfixed CRITICAL findings remain visible for operator review.
- Generated SBOM/vulnerability artifacts are written under `artifacts/supply-chain/` and are not committed.
- See `docs/security/supply-chain-policy.md` for the exact release policy and commands.

## Reporting

For a private institutional deployment, report suspected vulnerabilities to the repository owner through a private channel rather than opening an issue containing secrets, exploit payloads or sensitive document samples.
