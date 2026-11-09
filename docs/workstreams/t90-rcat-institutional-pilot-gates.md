# T90 Institutional RCAT Pilot — Scoped acceptance gates

> **Live-status correction — 2026-11-09:** the nine-tool R1 application is deployed and RCAT Google Login was operator-confirmed working; this supersedes historical statements below that no initial OAuth/Production deployment had occurred. Independent R1 negative security and Thai QA remain pending in [#308](https://github.com/yiwssx/rcat-pdf-hub/issues/308). **All 90-tool T90 capabilities are still subject to separate per-tool certification in [#262](https://github.com/yiwssx/rcat-pdf-hub/issues/262).** See [hashed report schema](t90-qa-hashed-report-contract.md): a truthy text claim is no longer sufficient for VERIFIED/RELEASED.


**Decision date:** 2026-11-02. **Scope:** only staff/students with a *verified*
`@rcat.ac.th` identity. An institutional deployment is not a public anonymous
PDF conversion service, but it still processes untrusted files and potentially
personal or sensitive content. This fact changes the release strategy, **not**
the minimum parser isolation, access control, SSRF and content-integrity gates.

## Authentication hard boundary

When `PDFHUB_RCAT_INSTITUTIONAL_ONLY=true`:

1. Human sign-in requires OIDC Authorization Code + PKCE from a preconfigured
   issuer whose signed ID token contains an **email** claim matching exactly
   `*@rcat.ac.th` and boolean `email_verified=true`. For Google's issuer,
   the signed `hd` claim must also equal `rcat.ac.th`, confirming current
   Google Workspace membership. Email verification alone is insufficient to
   establish organization membership. The signed `sub` identifies a user.
2. The API checks the claims when the OIDC callback completes, when converting
   a validated OIDC bearer into a principal, and **every time** it decodes an
   HttpOnly session cookie. Sessions minted before activation without the
   verified email are rejected; untrusted email suffixes and aliases are denied.
3. This mode fails closed unless OIDC is configured and Secure cookies are
   enabled. Direct LDAP login is disallowed because the current LDAP
   template-bind path cannot universally attest a directory-controlled
   `mail` attribute after authentication.
4. Anonymous Web Console bootstrap, local username/password admin, bootstrap
   administrator API key, service API keys, unverified OIDC identities and
   shareable signed download URLs are disabled. Authenticated **owner-scoped**
   download still works. Separate machine integrations will need an explicitly
   designed service-identity policy before being reenabled.
5. A verified `@rcat.ac.th` account receives the **operator** role by default,
   including conversion/upload, because ordinary Google ID tokens do not contain
   Workspace group claims. An explicitly mapped viewer group remains read-only;
   administrator privileges require a trusted IdP admin group or an exact
   `PDFHUB_RCAT_ADMIN_EMAILS` allowlist entry. The API re-evaluates
   roles whenever sessions are decoded, so removing an admin email revokes its
   elevated privileges. Ownership uses an issuer-scoped digest of the stable
   OIDC `sub`, not a changeable email or non-unique display name. Existing job/file isolation, expiration, quotas,
   malware scanning and audit remain unchanged.
6. Authentication is an application access boundary, not a network firewall.
   Browser login pages and operational health endpoints can remain reachable
   without exposing user documents. Restrict network ingress independently
   if the deployment must be accessible only on campus or through VPN.

**Google sign-in:** register an OAuth 2.0 Web application in the Google Cloud
project approved for the school's use; use issuer `https://accounts.google.com`
and register exact callback `https://pdf.rcat.ac.th/api/v1/auth/oidc/callback`.
A Google OAuth `hd` request parameter is only an account-selection hint;
**the signed `hd` claim within the validated ID token** must match `rcat.ac.th`
in addition to a verified matching email. Accounts without Google's Workspace
`hd` claim are rejected, even if Google previously verified their email. Configure an explicit admin email
allowlist because ordinary Google ID tokens omit group claims. A free-text
email field or a hard-coded `@rcat.ac.th` suffix in the UI is NOT authentication.

### Required pilot environment (not enabled automatically)

```dotenv
PDFHUB_RCAT_INSTITUTIONAL_ONLY=true
PDFHUB_OIDC_ENABLED=true
PDFHUB_LDAP_ENABLED=false
PDFHUB_SESSION_COOKIE_SECURE=true
PDFHUB_PUBLIC_BASE_URL=https://pdf.rcat.ac.th
PDFHUB_OIDC_ISSUER=https://accounts.google.com
PDFHUB_OIDC_CLIENT_ID=<registered-google-oauth-web-client-id>
PDFHUB_OIDC_CLIENT_SECRET=<registered-google-oauth-client-secret>
PDFHUB_RCAT_ADMIN_EMAILS=<school-admin@rcat.ac.th>
PDFHUB_WEB_CONSOLE_AUTO_LOGIN=false
```

Values in angle brackets are placeholders, **not existing configured secrets**.
Complete the provider and `oidc_redirect_uri` registration before activating
the feature flag. Existing deployments use `false` and remain unchanged.

## Engineering ≠ Pilot verified ≠ Released

Keep **three independent statuses per tool** with observable evidence:

| Gate | Meaning | Evidence required |
| --- | --- | --- |
| IMPLEMENTED | Complete source implementation and typed route/adapter | Code, parser constraints, unit tests, negative input tests |
| STAGED | Actual converter and storage flow succeeds in isolated CI | Real synthetically generated file, PDF structure/pages/text checks, constrained resource budgets |
| VERIFIED | Institutional acceptance for supported real-world inputs | Genuine sample corpus, Thai fidelity, owner/auth audit, runtime/network isolation, negative SSRF/malware tests |
| RELEASED | Available to the intended school users | Verified, reviewed rollout flag, operator approval, monitoring and rollback recorded |

For the 6 T90-2 blockers, **do not** convert a partial-subset HEIF smoke or
green CI to `VERIFIED` for all variants. Record separate supported subsets:
T09 HEIC HEVC, T25 HEIF, T20 restricted DWG, T30 CHM, T34 Microsoft Works WPS,
T33 HTTPS URL. Unsupported variants must fail closed with clear messages.

A school-only user base allows smaller launch load assumptions and staged
cohort testing. It does **not** justify disabling request size quotas,
virus scanning, network isolation, secure cookie/SSO controls or PDF-content
verification because malicious document content can still enter the system.

## Parallel execution — no dependency between engineering tracks

- **T90-2 #237 / PR #259**: isolate native runtime and record separate smoke
  results. Finish/merge only with branch CI and approved cohort gates;
  any native format not ready remains off, not a global blocker.
- **T90-3 #260**: 17 From-PDF capabilities. Start engineering and CI in an
  independent branch. Require actual page/text output verification, not
  placeholder images marked as editable documents.
- **T90-4 #261**: forms, annotations, redact/content removal and specialized
  workflows, independent branch. Redaction must actually remove content,
  not overlay opaque boxes. AI-dependent features stay isolated and optional.
- **T90-5 #262**: per-tool evidence/release checklist. It is a continuously
  updated certification ledger, **not** a phase blocking development of
  previous workstreams. Pilot release can happen per verified tool/subset.

### Immediate policy tests

- Wrong/missing/unverified mail; lookalike domains; upper-case domains;
  Google ID tokens with no group claim; shared display names from different
  mailboxes; viewer vs operator scopes; exact admin-email allowlist and
  immediate revocation; invalid/expired sessions; replayed sessions issued
  before the policy was enabled; local/Web Console/API-key bypass attempts.
- Signed download URLs issued before/after RCAT-only activation must not
  bypass the OIDC account boundary.
- Per-format safety stays distinct from human identity: restricted Docker
  decoders; negative SSRF and DNS rebinding; no credential/NAS volume
  access in native workers; real source-vs-output checks.

**Rollout state as authored:** source and QA on a dedicated dev branch only;
no OIDC issuer/secret was configured and no production flag was enabled.

## Follow-up: identity integrity and OAuth redirects

- File/job owner fields are limited to 120 characters. The trusted issuer and
  Google/OIDC `sub` are hashed to a stable `user:oidc:` owner name; emails may
  change or be reassigned, so they are unsuitable ownership identifiers.
- Institutional session decode recalculates the owner from signed `sub` and
  rejects Google sessions missing provider-attested Workspace `hd`.
- OAuth return paths reject cross-origin URLs, browser backslash normalization,
  and control-character injection before and after authorization.

## Compose configuration delivery

The base `docker-compose.yml` API environment mapping is shared with queue
workers and schedulers. Both `PDFHUB_RCAT_INSTITUTIONAL_ONLY` and
`PDFHUB_RCAT_ADMIN_EMAILS` must be interpolated there; declaring them only
in `.env` is not sufficient for container visibility. Production Compose
inherits the base environment and adds secure-cookie defaults. The release
policy validator explicitly checks both mappings.

## Google provider account-authority guidance

Google's official ID-token verification guidance requires the signed `hd`
claim when restricting access to a Google Workspace organization. If RCAT
emails are not provisioned as managed Google Workspace accounts, consumer
Google IDs cannot be accepted solely on `email_verified`; an authoritative
institutional OIDC provider or a fresh independent mailbox-verification
mechanism would be needed.

Official references:
- https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
- https://developers.google.com/identity/openid-connect/openid-connect
