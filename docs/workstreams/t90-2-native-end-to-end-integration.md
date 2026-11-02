# T90-2 six blocked formats — full code path and acceptance gate (2026-11-01)

**Status: IMPLEMENTED FOR EXPERIMENTAL USE IN DEVELOPMENT BRANCH, NOT PASSED OR RELEASED.**
Do **not** mark any format verified until the target host and real-format acceptance matrix pass.

## State of the development branch

- New independently gated native input/dispatch map:
  `apps/api/app/staged_to_pdf_adapters.py:NATIVE_DEV_TO_PDF_INPUTS`
  deliberately separate from the existing 38 STAGED operation variants.
- Uploaded file preflight in `app/filetypes.py` rejects all five native suffixes
  unless `PDFHUB_TO_PDF_TOOLS_ENABLED=true` **and** the matching per-format
  `PDFHUB_*_NATIVE_DEV_ENABLED=true`. Basic HEIF/DWG/CHM/Works header+size
  validation happens at upload. Microsoft Works detection is **not** inferred
  from extension: the native writerperfect parser and validated nonblank ODT
  must accept the source before a PDF can be completed.
- Explicit, opt-in `/api/v1/pdf/to-pdf/{heic,heif,dwg,chm,wps}` routes accept
  only existing, nonexpired owner files of the matching MIME and suffix; require
  `pdf:convert` scope; and use the standard audited `_create_job` path.
  Routes remain absent from the default public API/OpenAPI registry.
- Queue dispatch sends separately gated native operations only to the
  `heavy` RQ queue. Worker independently rechecks active feature flags,
  file owner, expiry, single source file, original MIME and source signature.
- Only after these gates do the corresponding sandboxed native engines run.
  CHM, Works, DWG and HEIF/HEIC retain their existing restricted subsets and
  resource caps. The patched HEIF lib version is **probed inside a separate
  no-network Bubblewrap subprocess**; the privileged RQ worker no longer
  calls `ctypes.CDLL` on the native library.
- URL remains a separate, fileless `/to-pdf/url` route and isolated HMAC
  sidecar with public-only egress policy and second independent HTML parser.
  It is not in the native upload map.
- Tests added (source only, not executed):
  `apps/api/tests/test_t90_2_native_dev_integrations.py` and
  `apps/api/tests/test_t90_2_url_offline_boundaries.py`.

## Exact outstanding gates

| Format | Code path | Genuine acceptance still required |
| --- | --- | --- |
| T09 HEIC | .heic upload → heavy → patched HEIF runtime/Bubblewrap → real PNG page inventory → checked PDF | Independently provision **libheif >=1.23.7** and matching decoder/plugins; verify sample variants, colors/orientation, multi-image completeness, sandbox capabilities and resource budgets |
| T25 HEIF | .heif upload → same HEIF isolated engine | Rights-cleared genuine HEIF primary/auxiliary/multi-frame samples; color profiles, image count and lossiness; version/provenance |
| T20 DWG | .dwg upload → external LibreDWG → ASCII DXF → strict 2D LINE/CIRCLE vector PDF | Externally licensed/pinned audited LibreDWG binary; review **GPLv3** distribution; confirm real 2D samples and reject layers/blocks/3D/styles without silently losing meaning; not a full CAD renderer |
| T30 CHM | .chm upload → isolated libchm LZX → offline chapter HTML → checked PDF | Genuine Windows CHM corpora (UTF-8, Thai cp874 and other legacy encodings), TOC, local references, image and LZX fidelity; malformed archives and sandbox behavior |
| T34 WPS | .wps upload → restricted writerperfect wps2odt → nonblank validated ODT → LibreOffice checked PDF | Actual Microsoft Works .wps files of multiple generations; Kingsoft WPS intentionally not supported; no blank or truncated pages; typography/layout review |
| T33 URL | fileless HTTPS URL job → signed private fetcher → sanitized text HTML → second HTML boundary → Gotenberg PDF | Host iptables egress interception/renewable lease, SSRF, DNS rebinding, network graph, credential isolation, HMAC replay, timeouts, Thai URL corpus and print fidelity; nftables alternative not implemented |

## Required final acceptance procedure (NOT EXECUTED)

1. On a suitable staging clone with the required external runtimes, **do not
   activate flags in production**. Inspect the native sandbox's unprivileged
   namespace compatibility without relaxing AppArmor/seccomp or granting
   broad capabilities.
2. Run existing T90-2 unit/integration suite and the two new regression modules
   in the repository's locked environment. Record actual command output,
   platform and dependency versions. The existence of tests is not a PASS.
3. For each format, compare at least one success case with authoritative source
   and PDF page count, readable text, nonblank visual content, correct owner and
   retention; exercise unsupported-but-valid variants and intentionally
   malformed files, timeouts and size limits. Document known lost fidelity.
4. Audit URL host firewall via packet-level negative tests; reject all private
   IPv4 destinations, metadata endpoints, DNS rebinding, special URL forms,
   alternative service routes, lease expiry and spoofed signed responses.
5. Review third-party binaries, hashes, codec/plugin vulnerabilities and
   LibreDWG redistribution obligations. Capture build images, provenance and
   actual native version before promoting any format.
6. **Only after all relevant gates PASS**, separately approve catalog status,
   explicit operator feature flag, PR/merge and deployment.

**This branch is still 34 STAGED / 6 BLOCKED / 0 independently VERIFIED
or RELEASED; T90-2 issue #237 / parent #172 remain OPEN.**
