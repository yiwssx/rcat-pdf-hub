# T90-1 / M08 — Unlock PDF (secure password handoff)

Tracker: #225, #172 and independent acceptance #262.

## Security model

- This is **authorized password-based decryption only**; no cracking, bypass,
  removal of unknown credentials, or authorization circumvention.
- Existing `app.services.pdf_access_control.unlock_pdf` engine is reused
  unchanged. True decrypted PDF content is verified; original encrypted file
  remains untouched.
- `POST /api/v1/pdf/unlock-pdf` requires **pdf:unlock** scope, strict
  owner-bound `file_id` and an explicitly supplied current PDF password.
- API bounds JSON request to 4096 bytes, password length to 1–256 Unicode
  characters and password UTF-8 length to 1024 bytes; schema/HTTP validation
  returns **fixed, redacted** errors, never echoes input values.
- **No passwords, tokens, AEAD ciphertext or secret references in**
  `JobRecord.params_json`, `JobRecord.error`, RQ args/kwargs, audit events,
  telemetry, URLs, file names or response bodies. Queue receives only job ID.
- A separate operator-provided 256-bit base64url key encrypts password using
  AES-256-GCM, with random 96-bit nonce and associated data binding
  **job ID + principal name + source file ID**.
- The `Valkey 8` key `pdfhub:m08:password:<uuid>` contains **only
  ciphertext**, is created atomically with NX and EX=300 seconds, and is
  **consumed once** using atomic GETDEL before any decryption. Expired,
  duplicated, wrong-owner/file, disabled feature or malformed secrets fail
  closed, never fall back to plaintext.
- On queue failure, delete ephemeral ciphertext and mark Job failed without
  exposing the secret. Queued cancellation deletes ciphertext. Expired keys
  remain bounded by Valkey TTL even if a Worker crashes.
- Ordinary Job retry is disabled for unlock. A user must submit a **new**
  password each time. Worker errors are sanitized before DB, webhook, audit
  and RQ traceback persistence.
- Decrypted results are **never automatically archived into Paperless**.
  Download still uses the authenticated owner-scoped FileRecord route.
- A five-minute queue backlog can intentionally cause M08 failure: fail closed
  and require new password rather than extending secret lifetime.

## Feature gates and operations

- `PDFHUB_UNLOCK_PDF_TOOLS_ENABLED=false` (default), route hidden when OFF.
- `PDFHUB_UNLOCK_PDF_HANDOFF_KEY` **blank by default**; when enabled,
  configuration fails without a valid 32-byte base64url key. Both API and PDF
  Workers must receive the exact same key; rotate through a controlled deploy.
- Generate an independent key on a secure operator machine:

  `python3 -c 'import secrets,base64;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'`

- Do **not** commit the key, print it in CI, or reuse download-signing,
  session, webhooks or API-key pepper secrets. For production, use a secret
  manager or host-protected environment injection; control Docker access.
- Frontend `NEXT_PUBLIC_PDFHUB_M08_UNLOCK_ENABLED=true` at build time enables
  the separate Unlock PDF tool and password UI. Default build hides it.
- `pdf:unlock` is explicitly grantable through Admin/Service Key RBAC. It is
  deliberately omitted from newly created service-key default privileges.
- Source and output currently bounded to **16 MiB source** and existing
  engine's 1000-page limit. Password-protected PDFs with unknown passwords,
  signatures/permissions requiring independent preservation, corrupt PDFs,
  external DRM and archive-encryption formats are outside this source scope.

## Verification

- Real AES-256 PDF roundtrip, Unicode user passwords and decrypted page content.
- DB-backed Worker and FileRecord acceptance and ciphertext-only in-memory
  Valkey mock, one-time consumption, TTL, AAD binding, idempotency.
- Wrong password, malicious/oversized JSON, cross-owner, scope denial,
  source MIME, worker/queue failure, feature revocation, retry refusal and
  ciphertext cleanup.
- PR exact-head **Core API CI, Web CI, CodeQL, Dependency Review** must pass
  before merge; real Valkey/Compose, Google Workspace and Thai
  institutional acceptance still required before VERIFIED / RELEASED.

## Known hard limitations

- Python strings and third-party cryptographic libraries can retain password
  bytes in ephemeral process memory; **no guarantee of zeroization**.
- Redis/Valkey memory/RDB/AOF may retain **ciphertext**, not plaintext, until
  TTL or snapshot retention. A separate AEAD key and host security are mandatory.
- A user who knows the password intentionally gets a decrypted PDF copy,
  whose downstream handling requires ordinary institutional privacy controls.
- No deployment or production flag activation is part of this PR.
