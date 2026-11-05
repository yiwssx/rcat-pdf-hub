# M09 Protect PDF — engineering and acceptance

M09 creates encrypted PDFs using an existing pypdf AES-256 Revision 6 engine. It accepts a PDF belonging to the submitting principal, with distinct user and owner passwords. The engine reopens the new file to validate encryption revision, both credentials and page count. The source stays unchanged. Encrypted inputs and signed PDFs are outside this stage.

## One-time credential exchange

Passwords appear only in a bounded JSON request and temporary application memory. The API encrypts both values into one authenticated payload using a dedicated operator-provided M09 key and binds it to the job ID, user and source ID. Valkey holds ciphertext for at most five minutes, consumed once by the worker. The JobRecord and RQ carry no password or ciphertext. Failed submissions and cancellation attempt immediate cleanup, and the worker reports only generic errors. Retrying needs an entirely new request with both passwords. Protected outputs are not automatically archived.

## Feature gates

Backend flag `PDFHUB_PROTECT_PDF_TOOLS_ENABLED=false` and browser build flag `NEXT_PUBLIC_PDFHUB_M09_PROTECT_ENABLED=false` remain OFF by default. The dedicated `PDFHUB_PROTECT_PDF_HANDOFF_KEY` is blank until securely provisioned and must differ from M08's handoff key. API and PDF workers require the same configured key. The `pdf:protect` scope is independent, and the original 13-card registry is unchanged.

## Limits

Input <=16 MiB and at most 1000 pages; passwords 1–256 characters and <=1024 UTF-8 bytes. PDF permissions are reader-enforced, not DRM. Encrypting PDF/A may invalidate archival conformance. The server process may retain credentials in transient memory and ciphertext may survive in infrastructure snapshots. File quality, Thai typography, real deployment, SSO, secret management and operational security require independent RCAT acceptance.

## Verification contract

Automated coverage must verify real output, owner/user passwords, unchanged input, expiry, cross-tenant denial, invalid requests, no secret exposure in durable records, one-time consumption, queue errors, worker revocation, retry rejection and output security. Merge only after exact-head Core API, Web CI, CodeQL and Dependency Review checks pass. Not independently VERIFIED or RELEASED.
