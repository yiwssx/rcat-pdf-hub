# RCAT PDF HUB — Release 1 shipping gate

**Scope frozen 2026-11-05. Current status 2026-11-09: R1 deployed and operator-confirmed institutional login; independent Thai, negative authorization and restore acceptance still OPEN (see [#308](https://github.com/yiwssx/rcat-pdf-hub/issues/308)).** Historical code-candidate statements below do not override this status.

Release 1 is a separate, small institution-only release. It does **not** depend
on completing 90 PDF Candy capabilities. Existing tagged \`v0.6.0\` and Phase 7
release history are preserved.

## What must work

Exactly nine existing end-user processing entries:
OCR, merge, organize/split/rotate, compress, PDF-to-images, images-to-PDF,
watermark, page numbering, Office-to-PDF. Use the actual legacy queue handlers.
These are **candidate functions**, not independently certified for RCAT host.

Do not expand R1 to include native/URL/eBook conversion, AI, new editor tools,
Paperless archive or signed link sharing. The existing 13-card catalog remains
unchanged in this PR; the two support cards are not Release 1 acceptance items.
Note: in institutional-only mode signed-link creation is prohibited by the
existing backend policy; the Web UX must communicate unsupported operations
before live pilot signoff.

## Engineering completion versus release acceptance

1. **CODE**: Run \`make release1-check\` on PR and exact candidate commit;
   verify current Core API/Web/CodeQL/Dependency Review, build and genuine
   binary tests. Source scope PASS is not a real conversion or deployment PASS.
2. **STAGING**: Configure Google Workspace client (signed \`hd=rcat.ac.th\`,
   verified \`@rcat.ac.th\`, secure cookies). Explicitly test unauthorized
   identities, local/API-key/signed-link bypass, and separate user ownership.
   Produce source/output SHA256, original Thai layout checks, user download and
   failures for **each of nine** tools.
3. **SECURITY/OPERATIONS**: Validate image/PDF parsing with AV and isolated
   workers, quota/retention/audit, browser E2E, backup checksum, DR and
   non-destructive rollback rehearsal. Archive original test logs, not secrets.
4. **APPROVAL**: Operator records exact candidate SHA, approved cohort, time,
   rollback owner and artifact hashes. The script's evidence-manifest check only
   verifies the references and hashes; it does not replace an independent
   review of logs or actual runtime.
5. **DEPLOY**: Only after separately approved Production release window,
   use existing \`PDFHUB_RELEASE_MODE=production make release-readiness\`
   (including verified backup and target URL). Pilot on limited school users
   before institution-wide release. Never run a destructive restore here.

## Commands

\`\`\`bash
make release1-check
python3 scripts/validate-release1.py --mode source
# Only on the operator's test host with an independently collected evidence file:
python3 scripts/validate-release1.py --mode pilot \
  --expected-sha "$(git rev-parse HEAD)" \
  --evidence /secure/release1/acceptance.json
\`\`\`

Pilot evidence JSON keys: \`release\`, \`candidate_sha\`, \`tools\` (one record
per frozen slug containing \`slug\`, original \`source_sha256\`,
real converted \`output_sha256\`, and \`checks\`), \`gates\`, and \`approval\`
(\`approved_by\`, \`approved_at\`, \`cohort\`, \`rollback_owner\`).
Each individual check and global gate must reference a nonempty, local,
hashed artifact via \`{"result":"PASS","file":"relative/path","sha256":"..."}\`.
The evidence directory and files stay out of Git and contain no credentials.

**Stop conditions:** any converter returning only mocked outputs, visual Thai
regression, cross-user data exposure, bypass of Workspace membership, missing
AV/isolation, missing real logs/backup/rollback, or absent operator approval.
Do not infer RELEASED from \`make release1-check\`, green GitHub CI, or this file.

90-tool tracker #172, independent T90 gate #262 and R1 institution acceptance #308 remain open for the
later expansion. No automatic T90 state promotions or feature flag changes.

## RCAT institutional file ownership boundary (source hardening)

In institutional-only mode, a verified `@rcat.ac.th` administrator still has the ordinary file owner's privacy boundary. Wildcard `*` grants permission **scope**, not ownership of every user's uploaded documents. The file library, individual download/preview/delete/retention, legacy PDF conversion input and Paperless archive paths must filter by stable signed OIDC subject-derived owner for **every** human principal, including Admin.

The reviewed non-institutional legacy service/bootstrap wildcard path remains available in other deployments. The institutional path remains fail-closed and does not add hidden support impersonation or cross-user file rescue. Audited admin triage should remain a separate least-privilege interface rather than a general document download.

Code review and mock-cookie negative tests are not real RCAT Workspace/host acceptance. #308 still needs independent SSO denial, two-real-account owner checks, actual nine-tool original/output and recovery evidence. **No production change should be made on the strength of a green source test alone.**

## Non-mutating host configuration preflight

On a test/target host with actual operator-owned environment values present:

```bash
make release1-host-preflight
```

This runs `docker compose ... config --format json` through a read-only checker.
It never displays the source configuration or credentials; only failing setting
names are printed. Required: verified RCAT-only OIDC/HTTPS session policy,
nonempty Google client credentials, `PDFHUB_CLAMAV_ENABLED=true` and fail-closed
AV, all three worker configurations consistent with API, and experimental
conversion backends OFF. Passing only proves the *rendered configuration*
contract, not a working Google account or AV daemon. Then perform the
independent pilot checks before requesting any deployment approval.

## One-command RCAT Google Workspace operator setup

After creating the **Web application** OAuth Client in the approved school's
Google Cloud project, ensure the existing host `.env` is present, and run:

```bash
make rcat-workspace-setup    # prompts only for missing Google Client ID / Secret
make rcat-workspace-check    # prints only READY/INCOMPLETE, no credentials
make release1-host-preflight
```

Unlike copying a fresh `.env.example`, this setup preserves existing DB/API
credentials, network bind/ports, comments and unrelated settings. It backs up
old `.env` values privately and writes atomically at mode `0600`. Re-running
is safe and avoids duplicate keys; credential replacement is opt-in via
`python3 scripts/setup-rcat-workspace.py --rotate-client`. It sets the exact
OAuth callback base to `https://pdf.rcat.ac.th` and explicitly denies
non-institutional sign-ins. A successful settings check alone does not make
HTTPS, ClamAV, Google Workspace, or a Production release ready.
