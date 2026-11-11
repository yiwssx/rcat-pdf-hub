# T90 Code-First Production Rollout (RCAT Ubuntu)

## Decision and scope

The owner has approved shipping the **90/90 Engineering-MAC source code** to the existing institutional RCAT Production environment **before** independent 90-tool QA. Engineering-MAC does not mean all formats and goldens are verified, all runtime codecs are licensed and installed, or all 90 operations are live. Existing [QA #262](https://github.com/yiwssx/rcat-pdf-hub/issues/262) remains deferred; no per-tool QA is a prerequisite to deploying existing code.

This opt-in Compose overlay exposes standard staged T90 UI/API workflows on the existing **OIDC-restricted @rcat.ac.th** deployment while leaving risky/native/credential-dependent capabilities OFF. It does not create public/anonymous users, alter DNS, bypass institutional role/owner checks, change Caddy, create secrets, install GNU GPL native CAD binaries, or install a host URL firewall.

## Host-only manual release

On the actual **RCAT Ubuntu PDF HUB Production Host** (not a GitHub Actions runner), using the preexisting checkout containing the user's Production `.env`:

1. Preserve existing tracked host customizations. The reviewed release tool can preserve the one authorized site Caddyfile override. **Do not use `git reset --hard`**, force merge, or `docker compose down -v`. If the existing tracked Caddyfile differs from HEAD, reconcile it using the reviewed `scripts/migrate-site-caddy.py` rules before trying to fast-forward; the tool intentionally preserves the original bind mount.
2. Fetch and fast-forward the protected release checkout to reviewed `main` (do not use arbitrary branches or tags):
   ```sh
   cd /opt/rcat-pdf-hub
   git fetch origin main
   git merge --ff-only origin/main
   ```
3. To deploy the entire current T90 **codebase** and enable the ordinary core staged routes, run exactly:
   ```sh
   bash scripts/deploy-t90-code-first.sh
   ```
   It delegates to `scripts/one-command-release.py`, which refuses CI execution, checks actual running production Compose mode (including NAS), verifies the exact current protected-`main` Lean CI, validates institutional Google OIDC, ClamAV and the **explicit** T90 overlay (not the old R1-only false-flag policy), creates and verifies a new private live backup, rebuilds the existing application containers, migrates schema only after stopping writer pools, starts updated API/workers/Web/Caddy, then verifies live `/healthz` and `/readyz`. The script retains the T90 overlay on subsequent standard releases if currently active, so an ordinary update does not silently hide every staged route.
4. If it prints `BLOCKED` or fails a safety check, treat the rollout as **not deployed**. Do not bypass OIDC, backup, migration, exact-SHA CI or health checks. Do not print `.env`, credentials or private files in logs.

## Distinguish deploy from tool readiness

- **Code deployed:** application containers actually run the requested source SHA with the T90 overlay; the core staged Web/API feature flags may be visible to institutional users. It is acceptable that independent Thai/visual QA remains deferred.
- **Restrictions that remain OFF:** M08/M09 unlock/protect (distinct, non-repo one-time AEAD secrets required); T09 HEIC, T20 DWG, T25 HEIF, T30 CHM, T34 Microsoft Works WPS (separate isolated native runtime and licence/dependency boundaries); T33 public HTTPS URL (signed independent fetcher plus actual RCAT-host firewall/lease). The default runtime cannot truthfully guarantee these six formats are usable merely by setting a Boolean. These opt-in sidecars have their own dedicated Compose files and cannot be safely started from a normal public runner.
- **Further operational dependencies:** M05 translation may need actual offline model files; other formats are bounded to their documented MAC subsets. A visible button is not an assertion of successful document processing.
- **Evidence required to claim a real deploy:** on-host `one-command-release: DEPLOYED SHA=...` output, actual running Compose overlay, `healthz/readyz=PASS`; otherwise remain `EXECUTION_PENDING`. This is a **host-cutover result**, not 90 tool-by-tool QA.

## Rollback and future updates

The reviewed release already retains a freshly verified backup, database metadata and historical image/revision. It does not erase Docker volumes. No automatic DR runner or full independent QA is required for this **standard code-first release**. Do not manually remove the T90 overlay from live services or use a raw unguarded Compose restart; an incident rollback needs the existing approved restore/change procedure and explicit recovery evidence.

Related: [Issue #172](https://github.com/yiwssx/rcat-pdf-hub/issues/172) source/deploy tracker; [QA #262](https://github.com/yiwssx/rcat-pdf-hub/issues/262) independent QA only.
