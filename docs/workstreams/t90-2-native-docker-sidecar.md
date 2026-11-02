# T90-2 Native Decoder Sidecar — 2026-11-02

**Status: DEV IMPLEMENTED, infrastructure tested, real format acceptance INCOMPLETE.**
Tracks #237 / parent #172 / Draft PR #259. No Production activation.

## Why a separate service

The earlier nested Bubblewrap isolation failed repeatedly under non-root Docker
default AppArmor, including `bwrap: Failed to make / slave: Permission denied`.
Granting Docker `--privileged`, AppArmor unconfined or broad host SYS_ADMIN
would reduce security for a worker that has database credentials, owner files
and NAS access. That is not an acceptable way to mark a format PASS.

Instead use an **entirely separate decoder container** with no database, Redis,
NAS or Docker socket volume or credentials. All native code is executed there,
never in the privileged RQ worker. Its root is read-only, user 10001, all Linux
capabilities dropped, no new privileges, pids/memory/CPU bound, temporary input
and output only on private tmpfs, port 8098 unexposed on internal Docker bridge.
It can reach Gotenberg's document-render endpoint on that internal bridge;
the host/container network graph still needs production-grade review.

```text
API (owner/MIME/expiry guard) → heavy RQ (DB/Redis/data)
   → HMAC-authenticated request + bounded source bytes
   → native-decoder:8098 [internal bridge, zero public ports]
      → CHM / Works / DWG / HEIC / HEIF native reader
      → Gotenberg only for PDF rendering
   → HMAC-authenticated bounded PDF
   → RQ second strict PDF parsing/visible content check
   → owner-scoped artifact persistence
```

This removes the runtime dependency on nested Bubblewrap for the *native*
decoder. `isolated_native_command` remains Bubblewrap-only in ordinary code
and uses a fixed direct argv with no shell **only** in a non-root, read-only
`PDFHUB_NATIVE_ISOLATED_CONTAINER=1` container with no capabilities and
no-new-privileges; in any other environment the direct mode is refused.

## Source files

- `compose.native-sidecar.yaml`: opt-in service; normal API/worker flags OFF,
  internal bridge, dedicated secret, narrowed resources and no shared storage.
- `apps/api/app/services/native_sidecar_client.py`: no local codec fallback,
  limits, request/response HMAC bound to operation+nonce+timestamp+bytes,
  strict PDF validation before worker storage.
- `apps/api/app/services/native_sidecar_server.py`: 1 concurrent request,
  short nonce cache, fixed allowlist, no file paths or sensitive fields in logs.
- `apps/api/app/services/native_sandbox.py`: direct source/destination argv
  only under independently checked Docker restrictions; original bwrap mode
  preserved elsewhere.
- `apps/api/Dockerfile`: native-only build variant omits `/data`.
- `apps/api/build-pinned-heif.sh`: builds decoder-only libheif **v1.23.7**,
  validates immutable upstream commit
  `12a259a5882dd99d45ec5fc77e296a3b620d1e2e` before build; uses
  libde265 + AOM, no x265 HEVC encoder and removes build toolchain.
- `apps/api/tests/test_t90_2_native_sidecar*.py`: signed protocol,
  malformed operation, nonce replay, PDF response, no direct-worker fallback.
- `.github/workflows/t90-2-native-sandbox.yml`: real non-root Docker with
  no network/caps/privileges and pinned libheif runtime Build/QA.

## Existing confirmed CI evidence

- Non-root native Docker source/output + `--network none`, cap-drop-all,
  no-new-privileges, read-only root: PASS (GitHub Actions).
- Pinned libheif v1.23.7 built and `heif-dec --version` run in offline,
  non-root Docker image: PASS.
- Real T25 HEIF functional smoke **PASS** (GitHub CI run #41386179585):
  a real generated uncompressed HEIF 128×80 image passed through the
  app's own `heif_to_pdf()` in non-root/no-network/cap-dropped Docker,
  producing one strictly parsed, nonblank PDF page. The earlier
  version-probe path mismatch was fixed in `0f4763d9`.
  **This tests one generated lossless HEIF subset only**, not camera HEIC,
  user-provided images, the signed API transport or production fidelity.
  T25 remains BLOCKED for full-format acceptance.
- Original Core API/Web/CodeQL/Dependency workflows passed on a prior branch
  commit, including 725 backend PASS / 4 skipped. Later commits require
  fresh status confirmation; prior green CI does not certify new source.

## Remaining before any format is VERIFIED

1. Run real API/worker/container HMAC transport end-to-end against staging
   (localhost test with mocked codec is not full integration).
2. Supply/generate real-format positive/negative fixture corpora, compare source
   and PDF for every format, record per-format supported subset. Never claim
   restricted DWG LINE/CIRCLE drawings represent full AutoCAD semantics.
3. CHM Thai/cp874 TOC and inline assets; genuine MS Works .wps and source
   fidelity; pinned libheif genuine HEVC HEIC + uncompressed HEIF corpora.
4. Install/audit a compatible LibreDWG reader and review GPLv3+ redistribution
   obligations. External DWG runtime is not yet provisioned by default.
5. Audit Gotenberg/sidecar network boundaries, malformed native inputs,
   process cleanup, cross-job confidentiality, timeouts and in-flight crashes.
   One-at-a-time requests and tmpfs do NOT themselves provide per-document
   ephemeral container isolation.
6. Independently test the separate T33 URL Fetcher host firewall, DNS rebinding,
   lease refresh, negative SSRF cases and real HTTPS page fidelity.
7. Only then decide whether each row moves BLOCKED → STAGED → VERIFIED; T90-5
   controls RELEASED after independent approval.

**main stays 34 STAGED / 6 BLOCKED / 0 VERIFIED or RELEASED for T90-2.**
Other engineering phases may proceed independently: T90-3 #260, T90-4 #261,
T90-5 #262. Draft PR #259 must remain unmerged pending acceptance.

## Network segregation tightened

The optional native overlay also creates an independent `native-gotenberg`
instance attached only to `native_converter_internal`; the ordinary
Gotenberg, PostgreSQL and Valkey application network are not on this bridge.
The codec sidecar can reach its dedicated renderer only. A real-host Docker
graph/SSRF audit remains mandatory.
