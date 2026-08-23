# Security notes

RCAT PDF Hub processes untrusted document uploads. Treat the processing plane as a security boundary.

## Production requirements

- Keep Gotenberg, PostgreSQL and Valkey on the internal Docker network only.
- Use a long random `PDFHUB_API_KEY_PEPPER`, bootstrap admin key and webhook master secret.
- Use scoped service API keys; do not share one service key across unrelated systems.
- Keep `PDFHUB_WEBHOOK_ALLOWED_HOSTS` narrow. Prefer exact hostnames over `*` and restrict worker egress at the network layer.
- Put the public endpoint behind TLS and an edge rate limiter/WAF.
- Back up PostgreSQL and the PDF volume according to institutional retention policy.
- Add malware scanning before accepting documents from untrusted public users.

## Secret handling

- Plaintext service API keys are returned once and are never written to the audit log.
- Database stores a peppered SHA-256 digest of service API keys.
- Webhook signing keys are derived per service from a master secret and are not stored in the database.
- The browser console keeps the entered API key in in-memory React state only; it does not use localStorage.

## Webhook SSRF controls

Webhook URLs are administrator-controlled and must match `PDFHUB_WEBHOOK_ALLOWED_HOSTS`. URLs containing credentials are rejected. Network-level egress filtering is still recommended because DNS can change after validation.

## Reporting

For a private institutional deployment, report suspected vulnerabilities to the repository owner through a private channel rather than opening an issue containing secrets, exploit payloads or sensitive document samples.
