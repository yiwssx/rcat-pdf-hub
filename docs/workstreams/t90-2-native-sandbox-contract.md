# T90-2 native decoder sandbox — development contract (2026-11-01)

**Status:** code implemented on a feature branch, **NOT VERIFIED**, NOT STAGED and NOT RELEASED. This is a design/implementation contract, not a claim that namespaces work in the running Compose deployment.

## Applies to

- T09/T25: HEIC/HEIF via externally pinned patched libheif and heif-dec
- T20: native DWG reader + strict DXF LINE/CIRCLE projection
- T30: CHM via libchm read-only LZX member parsing
- T34: Microsoft Works WPS via writerperfect wps2odt

All use `apps/api/app/services/native_sandbox.py` and **must** invoke the native binary with `isolated_native_command`, not directly via `subprocess.run([binary, ...])`. If `/usr/bin/bwrap` is absent, namespace creation fails, or the binary fails, the native job must fail without an unsandboxed fallback. Their individual development flags and the global T90-2 flag remain **OFF**.

## Isolation boundary implemented in source

`bubblewrap` starts the decoder with separate user, network, PID, IPC and UTS namespaces, no DNS/network connectivity, a fresh private `/tmp`, new `/proc`, minimal `/dev` and a cleared environment. Read-only mounts of packaged runtime/code provide the decoder executable and shared libraries. One input file is bound as `/input/source` read-only, and a per-job empty task directory is mounted at `/output` read-write. CHM uses bounded stdout and no output directory. **No shared `/data`, NAS, Docker socket, host secrets or other job source files are exposed as mounts.**

The *outer* Python worker imposes native CPU, memory, output file size, file-descriptor and wall-clock limits, checks return codes and verifies renderer products before writing final PDFs. These are defense-in-depth caps, **not a substitute for container isolation, vulnerability patches or real acceptance tests**.

## Host/Compose constraints — NO configuration changes deployed

Rootless user namespaces, mount namespaces and Bubblewrap's syscalls may be blocked by Docker's default seccomp, AppArmor or the host kernel. The implementation intentionally fails closed if blocked. **Do not use `privileged: true`, broad `CAP_SYS_ADMIN`, `seccomp=unconfined`, or disable AppArmor as a shortcut.** A separately reviewed least-privilege policy is required before the flags can be enabled.

The development API Dockerfile installs Debian `bubblewrap`, `libchm1`, `wps2odt`. For HEIC/HEIF and DWG the externally provisioned native binaries are **not** bundled into the image, pending provenance/hash and licensing/codec audits. Sandbox mounting of `/opt` is read-only for vetted tool distributions. No outside binaries are fetched dynamically by the converter.

## Independent acceptance gates — pending, not executed

1. Verify a decoder cannot connect to HTTP, DNS, loopback metadata endpoints or the Docker/host gateway, even if the input contains malicious URLs.
2. Verify a decoder cannot open API credentials, another user's upload, the database socket, NAS, or sibling job temp paths.
3. Verify the sandbox starts under non-root PDF Hub UID in the actual deployment without privileged container settings; verify setup failure causes job failure, not fallback.
4. Verify OOM/CPU timeout, process group cleanup, decompression bombs, malformed images, symlink races, output byte caps and nonblank exact-page PDF acceptance.
5. Verify **actual** CHM LZX content, Works 3/4/5/6 variations, HEIC/HEIF multiple images/orientation/colors and DWG limited 2D geometry against known, rights-cleared reference files. Review GPL terms for LibreDWG and proprietary codec plugin licenses separately.
6. Verify no change to existing upload/worker/queue paths and `PDFHUB_TO_PDF_TOOLS_ENABLED=false` default; separately approve each format and any public endpoint or migration.
7. T33 URL uses a **different threat model**: it requires *controlled outbound HTTPS to vetted public IPs*, so the no-network native sandbox **cannot** be reused unchanged. Its in-process DNS-pinned HTTPS fetcher remains BLOCKED until a separate egress-enforced fetch service is accepted.

**Until these gates complete:** main remains **34 STAGED / 6 BLOCKED / 38 guarded endpoint variants / 0 independently VERIFIED or RELEASED**. Keep T90-2 tracker #237 open; no tests, CI, PR, merge or deployment have occurred in this development-only increment.
