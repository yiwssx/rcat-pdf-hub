# T90-2 / T33 URL → PDF: isolated HTTPS fetch service

**Development-only. NOT TESTED, VERIFIED, MERGED, DEPLOYED OR RELEASED.**
The `url-to-pdf` feature and overall T90-2 conversion flag default to **OFF**.
This is an operator runbook for a **future** QA/activation phase, not a
directive to turn the feature on now.

## What was implemented

```text
Authenticated caller -> PDF Hub API /to-pdf/url (flag-gated, quota-checked)
    -> Heavy RQ Job (file_ids=[], params={"url": "<public-https-url>"})
    -> apps/api/app/services/to_pdf_url.py
       - validates the URL and requires >=40-character shared HMAC secret
       - signs timestamp + random nonce + the original independently validated URL body (including Unicode paths)
       - connects ONLY to http://url-fetcher:8099 on private Docker bridge
       - checks sidecar's signed response, MIME and content bounds
    -> ops/url-fetcher/server.py (minimal, separate container)
       - verifies HMAC, timestamp and replay nonce; caps request/concurrency
       - strict public FQDN + HTTPS/443 only; no userinfo/query/redirects
       - resolves A/AAAA, rejects ANY non-global DNS answer
       - chooses verified public IPv4; pins TCP to numeric address
       - validates TLS SNI/certificate against original hostname
       - no proxy/cookies/external CSS/JS/images, capped HTML/UTF-8 output
    -> HTML sanitized content returned over signed private response
    -> Gotenberg Chromium processes ONLY offline sanitized HTML -> PDF
```

The browser never visits the remote page. This produces a **content transcript**,
not an exact screenshot or fully styled/JavaScript-rendered page.

## Network trust boundary

- Default `docker-compose.yml` is unchanged. The opt-in overlay is
  `compose.url-fetcher.yaml`.
- `url-fetcher` is NOT on the main API/DB/Redis network; it joins
  `url_fetch_internal` (internal, shared only with `worker-heavy`) and
  `url_fetch_egress` (outbound, IPv4-only). It does **not** mount
  `pdf_data`, NAS or any application credential. Its only shared secret
  authenticates fetch jobs, never DB access.
- `url_fetch_egress` has a fixed CIDR `172.30.243.0/28`, fixed fetcher
  IP `172.30.243.2`, and host bridge name `br-pdfhub-url` to give firewall
  rules an interface match independent of the sidecar's selected source IP.
  `gw_priority: 100` selects the egress network as its default route.
- **Requires Docker Compose >= 2.33.1** for `gw_priority`; earlier Compose
  versions MUST NOT be used. Check for address/bridge conflicts against the
  existing RCAT networks before building or enabling the overlay.
- The **manual** host script
  `ops/url-fetcher/install-host-egress-firewall.sh` requires Docker's
  **iptables backend**, a reachable `DOCKER-USER` hook from FORWARD, and
  creates restrictive rules on `br-pdfhub-url` for FORWARD and INPUT:
  reject private, reserved, link-local, metadata and multicast destinations,
  allow outbound TCP/443 to otherwise public IPv4, reject all other egress.
  It refuses missing/ineffective DOCKER-USER hooks; on Docker's nftables
  backend a **separately audited nftables policy** is required (not provided).
- No packet filtering is executed from the container or repository. The host
  installer is **not auto-run** by CI, Compose, Docker build or API startup.
- After successful host installation the script writes
  `/etc/pdfhub/url-egress.attested` with an exact sentinel and this host
  boot's kernel `boot_id`. The fetcher refuses startup if this file is
  absent, mismatched or stale after reboot. The marker is an **operator
  attestation, not cryptographic proof** that rules are still in force.
  Host firewall persistence and re-auditing after Docker/network reload
  remain mandatory before a trusted deployment.

**Important:** Docker `internal: true` alone is not an outbound firewall
when a service is also attached to an external bridge. Similarly, application
DNS filtering alone is not a complete SSRF defense. Both layers matter.

## Planned operator activation (NOT EXECUTED)

1. Review network subnet conflicts, iptables vs nftables backend, Compose
   version and host firewall policy. If unsupported, keep feature disabled.
2. Generate a unique strong `PDFHUB_URL_FETCHER_SHARED_SECRET` (e.g., a
   locally generated 32-byte random hex token), store it outside Git with
   restrictive file permissions. Do not reuse the API admin key.
3. On a suitable **non-production host** review and manually invoke the
   installer using `sudo bash ops/url-fetcher/install-host-egress-firewall.sh`.
   Verify the FORWARD/INPUT rules actually intercept traffic from the fetcher,
   including source-address spoofing, and that firewall restoration/renewed
   attestation after restart is managed. No `privileged: true`, broad
   capabilities, or disabled host security controls.
4. **Only during an approved QA window**, bring up the explicit overlay and
   the optional `url-import-dev` profile using Docker Compose; never copy
   the sidecar onto the default network or publish port 8099. Start with both
   `PDFHUB_TO_PDF_TOOLS_ENABLED=false` and
   `PDFHUB_URL_TO_PDF_DEV_ENABLED=false`.
5. Execute an independent, written QA plan covering HMAC forgery/replay,
   truncated responses, malformed charsets/HTML, URL forms, DNS rebinding,
   private/metadata/host egress, IPv6 fallback, low/high concurrency,
   service restart and firewall removal, timeout/cancellation, and Thai PDF
   visual comparisons. Check existing worker jobs remain unaffected.
6. Independently approve security and print fidelity before considering a
   feature-flag change, staged route activation, merge, or production rollout.

## Explicit limitations

- No arbitrary ports, HTTP, credentials, URL query strings/fragments,
  redirects, IPv6-only destinations, remote images/fonts/CSS/JS, PDFs or
  non-HTML downloadable assets. No full website screenshot/pagination fidelity.
- URL source and timestamp are stored with the job in the database; keep
  existing job-retention and access-control policies in force. Fetcher never
  logs source URLs by default.
- Windows/macOS Docker Desktop and Docker's experimental nftables backend
  need a different host network policy; this iptables installer must fail
  closed and **must not be adapted by removing safeguards**.
- The static egress interface/IP/subnet are security-critical configuration
  and must stay aligned with firewall rules. Changing them without renewing
  network protection may leave a dangerous gap.

**T90-2 remains 34 STAGED / 6 BLOCKED / 0 independently VERIFIED/RELEASED
on main; tracker #237 and parent #172 remain OPEN.**

## 2026-11-01 security follow-up — independent offline HTML boundary and expiring firewall lease

**Development source only. Not run or tested on the host, no deployment.**

1. The privileged heavy worker now calls `app.services.url_html_boundary.validate_offline_url_html` **after** verifying the signed fetcher response and **before** giving any HTML to Gotenberg Chromium. The strict second-stage parser permits only an attribute-free subset of headings/paragraphs/tables/lists/plain formatting, counts tags and text, matches open/close tags, escapes every text node, and **rejects** script, iframe, img, CSS, SVG, arbitrary href/src attributes, comments and unsupported declarations. HMAC authenticates the sidecar but does not establish the HTML is safe after a lower-trust sidecar compromise; this validation is a separate trust boundary. Gotenberg also uses a static CSP in its established local HTML template.
2. The host no longer issues a boot-only permanent marker. `ops/url-fetcher/verify-host-egress-firewall.sh` rechecks that `DOCKER-USER` is the **first FORWARD rule**, that the dedicated bridge is the **first DOCKER-USER and INPUT rule**, and that the custom chain matches the exact ordered list of non-public destination rejects, public TCP/443 exception and final reject. If checks fail it attempts to overwrite the existing marker as `DISABLED`. Successful verification writes a 3-line `V2` marker containing the running host's `boot_id` and timestamp. Updating *in place* is required because the sidecar bind-mounts the marker file.
3. The fetcher now checks this **expiring, host-verified 120-second lease on startup and at least twice before each new Internet fetch**, and health returns 503 when it has expired. When the verifier/timer fails or stops, new URL fetch requests are rejected after expiry. This is a limited-time operational tripwire, **not proof of firewall security or instantaneous prevention** if host rules are changed between verifications.
4. Added opt-in `ops/url-fetcher/systemd/pdfhub-url-firewall-guard.service` and `.timer` for a **30-second host-side verification cadence**. These are repository source files only. The administrator must separately install the reviewed verification script at `/usr/local/libexec/pdfhub/verify-host-egress-firewall.sh`, install/enable systemd units, ensure host iptables rules persist or are restored after reboot, and perform an explicit verification before starting the optional fetcher. **Nothing runs or changes on the host as a result of committing these files.**
5. The manual installer `ops/url-fetcher/install-host-egress-firewall.sh` now calls the separate verifier after constructing firewall rules. If no rules, wrong chain ordering, nftables-only backend, unavailable host identity or a stale marker is encountered, the opt-in importer must remain disabled until independent acceptance.

### Remaining security concerns (NOT accepted)

- The base PDF/DB/Redis/worker network must still be inspected against the actual Docker network graph, policy routing and local INPUT/FORWARD counters. The included installer is **iptables-backend-specific** and deliberately does not claim native Docker nftables compatibility.
- A host administrator or firewall manager can change the rules **between 30-second audits**. The expiring lease reduces stale-policy exposure but cannot replace OS-enforced egress rules. A correctly configured persistent host firewall and independent SSRF/egress negative tests are mandatory.
- Unknown Compose version/subnet/bridge conflicts and availability of host `/proc/sys/kernel/random/boot_id` inside the sidecar still require acceptance.
- `T33 URL` remains **BLOCKED**. No tests, CI, PR, merge, deployment or feature flag activation; main counts are unchanged.
