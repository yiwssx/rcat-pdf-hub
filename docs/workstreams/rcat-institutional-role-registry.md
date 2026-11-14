# RCAT PDF HUB — Institutional Super Admin & Role Registry

Status: GitHub source feature; **disabled by default**. Does not authorize Production changes.

## Existing and new roles

- Viewer: owner-scoped read access.
- Operator: standard owner-scoped document work.
- Admin: authorized operational console access; cannot assign human roles.
- Super Admin: manages institutional user roles, and retains Admin console access.
- Even a Super Admin does **not** bypass institutional document ownership.

Authentication remains existing Google Workspace OIDC with signed `hd=rcat.ac.th`, verified `@rcat.ac.th` email and issuer-scoped stable Google `sub`. No new local password, service key, first-visitor privilege, or external IdP. Email is an invitation and display attribute; roles bind to the stable OIDC owner identity.

## Initial authorization, at operator-controlled release only

The repository deliberately contains **no real owner email**. The owner must explicitly supply/confirm their *exact* Google Workspace `@rcat.ac.th` email privately at deployment time:

```env
PDFHUB_RCAT_INSTITUTIONAL_ONLY=true
PDFHUB_RCAT_ROLE_REGISTRY_ENABLED=true
PDFHUB_RCAT_BOOTSTRAP_SUPER_ADMIN_EMAIL=<owner-approved-exact-email@rcat.ac.th>
```

These settings must be placed in the host-protected `.env` by an authorized operator; do not commit them or echo secrets. Do not enable without a reviewed deployment, fresh verified backup and normal guarded cutover. Database migration `0007_institutional_roles` is additive.

Only the exact approved, Google-verified member can complete initial bootstrap, and only after authenticating with the expected signed domain and immutable OIDC `sub`. Bootstrap creates an irreversible marker `institutional-super-admin` and an owner-bound database assignment. **No other first login obtains Super Admin**. Reassigning that mailbox to a different Google Subject does not transfer its privileges. Audit persistence failure prevents bootstrap. Once bootstrap is marked, changing the environment email cannot create a second owner; use the Super Admin UI to delegate privileges.

The new role registry is gated OFF by default, so existing institutional users and old admin allowlists remain unchanged on mere source merge. With registry enabled, already allowed Admins receive the same role on first registration, except where subsequently modified by a Super Admin.

## User management

After verified owner sign-in, visit `/admin?section=users`. The Super Admin can:

- View up to 1000 account/role entries.
- Assign Admin/Operator/Viewer by exact RCAT email, pending first login to bind immutable Google Subject.
- Promote to Super Admin **only when that account already has a bound verified Google Subject**.
- Disable/re-enable other users. Revocation is enforced at the next authenticated API request even with a valid prior session cookie.
- Audit all administrative changes. Admins, local admin, service keys, API keys and spoofed wildcard roles cannot manage the role registry; attempts fail closed.

Protect against self-demotion/disable and disabling the last active Super Admin; manage an authorized transfer with a second verified Super Admin. No access to other users' private file bodies is granted by privilege level.

## Owner acceptance before Production

1. Owner explicitly confirms exact email; authorization is not inferred from repository ownership or displayed name.
2. Review migration rollback and fresh backup; guarded deploy only when separately authorized.
3. Sign in from owner Google Workspace account and confirm `/api/v1/auth/me` returns `roles: ["super_admin"]`.
4. Verify non-allowlisted login remains Operator; new Admin can be invited and promoted only by Super Admin.
5. Confirm cross-user file access stays denied; audit records role changes; revoke an Admin and confirm next-request downgrade.
6. Never claim code merge = enabled Production.

Do not use `PDFHUB_RCAT_ADMIN_EMAILS` to designate the first Super Admin; it grants the pre-existing **Admin** role only. Production credentials and recipient identities belong on the RCAT host, not in GitHub.
