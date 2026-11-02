# T90 Institutional RCAT Pilot — Scoped acceptance gates

**Decision date:** 2026-11-02. **Scope:** only staff/students with a *verified*
`@rcat.ac.th` identity. An institutional deployment is not a public anonymous
PDF conversion service, but it still processes untrusted files and potentially
personal or sensitive content. This fact changes the release strategy, **not**
the minimum parser isolation, access control, SSRF and content-integrity gates.

## Authentication hard boundary

When `PDFHUB_RCAT_INSTITUTIONAL_ONLY=true`:

1. Human sign-in requires OIDC Authorization Code + PKCE from a preconfigured
   issuer whose signed ID token contains an **email** claim matching exactly
   `*@rcat.ac.th` and boolean `email_verified=true`. Name, UI email fields,
   preferred_username, sub and group membership **alone are not evidence**
   of control of an institutional mailbox.
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
5. Institutional group-to-role mapping remains in force: `@rcat.ac.th`
   is **necessary but not sufficient** for files/operator/admin privileges.
   Only mapped groups receive permitted roles. Existing job/file ownership,
   expiration, quotas, malware scanning and audit remain unchanged.
6. Authentication is an application access boundary, not a network firewall.
   Browser login pages and operational health endpoints can remain reachable
   without exposing user documents. Restrict network ingress independently
   if the deployment must be accessible only on campus or through VPN.

**No assumption that the school already has an OIDC provider:** configure a
trusted institutional IdP (e.g. Google Workspace / Microsoft Entra / Keycloak
federated with institutional ownership) with a stable OIDC issuer, client ID,
redirect URI and roles/group claims. A simple email textbox is NOT acceptable.

### Required pilot environment (not enabled automatically)

```dotenv
PDFHUB_RCAT_INSTITUTIONAL_ONLY=true
PDFHUB_OIDC_ENABLED=true
PDFHUB_LDAP_ENABLED=false
PDFHUB_SESSION_COOKIE_SECURE=true
PDFHUB_PUBLIC_BASE_URL=https://pdf.rcat.ac.th
PDFHUB_OIDC_ISSUER=https://<configured-institutional-issuer>
PDFHUB_OIDC_CLIENT_ID=<registered-OIDC-client>
PDFHUB_OIDC_CLIENT_SECRET=<from-IdP-if-confidential-client>
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
  OIDC roles; invalid/expired sessions; replayed sessions issued before
  the policy was enabled; local/Web Console/API-key bypass attempts.
- Signed download URLs issued before/after RCAT-only activation must not
  bypass the OIDC account boundary.
- Per-format safety stays distinct from human identity: restricted Docker
  decoders; negative SSRF and DNS rebinding; no credential/NAS volume
  access in native workers; real source-vs-output checks.

**Rollout state as authored:** source and QA on a dedicated dev branch only;
no OIDC issuer/secret was configured and no production flag was enabled.
