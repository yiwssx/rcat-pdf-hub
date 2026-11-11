# RCAT T90 — Full Native, URL and AEAD Production Runtime

**Owner directive 2026-11-11:** Deploy the existing 90/90 bounded Engineering-MAC source to the private RCAT Ubuntu Production host **before per-tool QA**. Operational authentication, backup, actual URL firewall and isolation remain non-waivable; code proof is not live-tool fidelity or complete release certification.

## What this package actually provisions

- **M08/M09 PDF unlock/protect:** two **distinct** canonical 32-byte AES-GCM handoff secrets (base64url), created or reused only inside the existing Production `.env` with owner/group preserved and 0600 mode. No values are printed or sent to GitHub.
- **Native HEIC/HEIF/DWG/CHM/Works:** one **private HMAC** key; isolated read-only non-root Native Decoder with dedicated internal-only network and separate native Gotenberg. Runtime builds patched pinned libheif v1.23.7 and pinned GNU LibreDWG 0.14 on this host. Built-in libchm and writerperfect remain inside decoder only. Restricted MAC subsets only, not general CAD/image/Works fidelity. **GNU GPL-3.0-or-later LibreDWG**: intended for institution-internal execution. Distribution of images/binaries later requires corresponding GPL licensing/source compliance; do not publish these images to third parties without review.
- **T33 public HTTPS URL:** different **private HMAC** key; independent nonroot read-only fetcher with `url_fetch_internal` and **fixed egress bridge `br-pdfhub-url`**. Privileged reviewed host `iptables DOCKER-USER` / `INPUT` policy denies internal/metadata/host and non-HTTPS ports. Fail-closed 120-second firewall lease is verified/refreshed by root-owned systemd guard every 30 seconds. A separate systemd service restores exact policy on Docker-host reboot, or refuses when unexpected rules/backends exist. URL import is text-content only, no full-site screenshot or remote Chromium.
- **Core T90 UI/API/worker:** all existing staged Web routes, scoped RQ operations and flags enabled by explicit `compose.t90-code-first.yaml`, followed by Native/URL overlays and **`compose.t90-full-runtime.yaml` LAST**. The last overlay explicitly retains worker-heavy's Production `data,management,egress` networks as well as the two private sidecar bridges. Does not expose either sidecar port publicly.

Everything stays **@rcat.ac.th Google OIDC institutional-only**, with HTTPS/Secure cookie, no anonymous auto-login, owner isolation, fail-closed ClamAV. No Vercel, DNS change or paid runner.

## One-time manual commands — run on RCAT's actual Ubuntu Production Host

The admin account must already have its normal local GitHub `gh` authentication, Docker Compose permission and `sudo` for installing the host firewall. The existing `/opt/rcat-pdf-hub/.env` must be the **real institution's current Production configuration**, not a template. Retain the same Docker project/volumes. No credentials need be pasted into chat.

```bash
cd /opt/rcat-pdf-hub || exit 1
git fetch origin main &&
git merge --ff-only origin/main &&
sudo bash scripts/provision-t90-full-runtime.sh &&
bash scripts/deploy-t90-full-runtime.sh
```

**What happens in order:**
1. Git fast-forward retains existing local changes. If blocked by non-Caddy tracked changes, stop rather than force-reset. Preserve custom Caddy through the reviewed `migrate-site-caddy.py` process.
2. Root provisioning generates/reuses 4 independent secrets only in local `.env`; installs the known exact URL firewall rules and root systemd boot/lease units. Existing conflicting firewall policy or unsupported Docker backend must **fail closed**, not be overridden. It never changes database, DNS or containers.
3. Host-only full release selects existing Production Compose mode (with NAS if already used), requires `PDFHUB_T90_CODE_ROLLOUT_ENABLED=true` and `PDFHUB_T90_FULL_RUNTIME_ENABLED=true`, validates real institutional configuration and sidecar/network/secret shapes. It reuses protected-main CI evidence, creates/verifies a private **live database/storage backup**, builds all existing app and isolated native/URL images, starts the lower-trust sidecars and confirms their health **before stopping existing writers**; then performs guarded migration/cutover and probes `/healthz`+`/readyz`. It refuses to run from GitHub Actions and never skips the core safety checks.
4. Production URL egress is **not** certified by disposable CI alone. Only the real root firewall guard + container's live fresh-lease check can allow actual URL requests. Full independent document/Thai/source-output quality QA #262 remains deferred as requested.

## Expected outputs and truthful status

The host command should end with `one-command-release: DEPLOYED SHA=<40-char commit> ... healthz/readyz=PASS`, and the Native + URL sidecars should show `healthy`. If the script says `BLOCKED`, if a codec download fails, if the host lacks the required Docker firewall backend, if a sidecar is not healthy, if OIDC/security/backup fails, or if the main web/API is not ready, **deployment has not succeeded**. Do not infer all 90 conversions actually work merely from successful startup.

Run a status query without printing credentials:
```bash
cd /opt/rcat-pdf-hub
git rev-parse HEAD
systemctl is-active pdfhub-url-firewall-guard.timer
sudo bash /usr/local/libexec/pdfhub/verify-host-egress-firewall.sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  -f compose.t90-code-first.yaml -f compose.native-sidecar.yaml \
  -f compose.url-fetcher.yaml -f compose.t90-full-runtime.yaml \
  --profile native-dev --profile url-import-dev ps
```
If the existing active Production uses NAS, add `-f docker-compose.nas.yml` **after** `docker-compose.prod.yml` to the status query. Do not print `docker compose config` to public logs: it expands secret environment values.

## Safety and remaining limitations

- Never run `docker compose down -v` or `git reset --hard` against this Production instance.
- Host firewall installer is deliberately idempotent **only for an exact matching existing policy**; unfamiliar chains/IPv6/alternate Docker nftables backend require a separate reviewed host-specific policy, not a bypass.
- Existing owner/tenant identity and authorization, file quota/retention, ClamAV and live backup are mandatory; independent QA reports of all 90 specific formats and Thai visual goldens are explicitly **not** required before this owner-approved code-first deployment.
- Offline translation models, environment-specific third-party runtime prerequisites and unsupported format variants can still prevent individual user operations from succeeding. Record live failures as operational defects; do not label 90/90 independently VERIFIED until proven.
- The GitHub-connected assistant cannot execute Docker on `rcatiotserver`; repository merge + CI success proves **deployment configuration prepared**, not a live Production cutover.

Tracker: [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172). Independent QA (deferred): [#262](https://github.com/yiwssx/rcat-pdf-hub/issues/262).
