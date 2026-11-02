# T90-2 — Parallel engineering + real-file evidence (school-only)

Issue [#237](https://github.com/yiwssx/rcat-pdf-hub/issues/237) is the
execution board; [#259](https://github.com/yiwssx/rcat-pdf-hub/pull/259)
contains six **unmerged, experimental** native/URL format paths. Engineering,
artifact QA, security acceptance and T90-5 independent approval can proceed
**in parallel for different tool IDs**. Do not bulk-promote the 40 formats.

## What has actually been checked off

The T90-5 ledger can credit only **IMPLEMENTED** for three already-merged
T90-2 code paths with exact merge commits and CI links:
- **T11 DjVu:** limited to a one-page self-contained raster DJVU subset.
- **T19 MOBI:** limited to unencrypted classic UTF-8 PalmDOC text transcription.
- **T21 Publisher:** bounded OLE CFB publisher sample through pinned libmspub.

Each record has `supported_subset` and `acceptance_pending`. More
implementation evidence can be added one tool at a time, citing its actual
merged code. These entries do **not** become STAGED in the T90-5 ledger without
actual source/output checksums, and are **not** VERIFIED or RELEASED. A prior
engineering **34 STAGED / 6 BLOCKED** rollup is an independent development
inventory, not the same stricter T90-5 evidence ledger.

## Offline sample provenance gate

Keep **rights-cleared source fixtures and resulting PDF files outside Git**,
inside a dedicated local QA directory, never inside API public storage or
tracked docs. Do not upload private institutional files, PDF content, or
student records to GitHub CI.

Put a manifest next to these files, for example:

```json
{
  "schema_version": 1,
  "tool_id": "T21",
  "cases": [
    {
      "case_id": "publisher-internal-a4-001",
      "source": "publisher-example.pub",
      "source_sha256": "<64 lowercase hex from the actual file>",
      "output": "publisher-example.pdf",
      "output_sha256": "<64 lowercase hex from the actual PDF>"
    }
  ]
}
```

The placeholders above are *not* real hashes and will fail validation.
After generating actual files, run:

```bash
sha256sum /opt/rcat-pdfhub-qa/publisher-example.pub /opt/rcat-pdfhub-qa/publisher-example.pdf
python3 scripts/t90_2_fixture_audit.py /opt/rcat-pdfhub-qa/publisher-manifest.json \
  --fixtures-root /opt/rcat-pdfhub-qa \
  > /opt/rcat-pdfhub-qa/publisher-provenance-report.json
```

The audit is stdlib-only and does not fetch URLs, unpack archives or execute
the submitted file. It rejects missing/mismatched hashes, symlink/parent paths,
duplicate cases, wrong tool ID, large inputs, same input/output file and
incorrect PDF header/end marker. It rehashes source and result.

**Crucial:** its result is strictly `PROVENANCE_ONLY`. A PDF header/EOF marker
does **not** prove it is renderable, that its page count is correct or that
Thai text/images/layout are visible. The audit deliberately sets page-count,
visual, isolation and owner checks to `false` and never edits the T90-5
acceptance ledger.

## Independent checklist per tool (continuous signoff)

- [ ] **Provenance:** independently produced rights-cleared original, output,
      SHA-256 for both, exact source version, source immutability and engine
      version; offline manifest audit.
- [ ] **Binary/visual:** isolated renderer reports actual page count and media
      boxes; each rendered page checked against source/golden, Thai
      Sarabun/THSarabunPSK fonts and frame/order/rotation as applicable.
- [ ] **Threat resistance:** malformed/oversized/zip-bomb cases, AV, resource
      limits, nonroot isolated renderer, egress blocked for local documents.
- [ ] **Authenticated lifecycle:** real RCAT OIDC identity, owner/expiry,
      upload → API → queue → worker → signed download; reject another user,
      cancellation, cleanup/rollback/audit.
- [ ] **T90-5:** reviewer-approved per-tool `STAGED` /`VERIFIED` evidence,
      operator signoff and separate `RELEASED` only after actual RCAT SSO
      and safe activation. No anonymous or service-key bypass.

### Six remaining experimental formats

| Tool | Independent blocker | CI smoke is NOT enough |
| --- | --- | --- |
| T09 HEIC | Real camera HEIC, licensed patched codec, orientation / ICC | Generated HEIF is not camera HEIC |
| T25 HEIF | Real external HEIF variants and raster comparison | Generated single-frame codec is only smoke |
| T20 DWG | Authorized CAD source, layers/fonts/scale | ASCII DXF is not DWG |
| T30 CHM | CHM/LZX genuine help books, navigation/charset/sandbox | Synthetic archive passes limited parser only |
| T34 WPS | Genuine Microsoft Works format generation, fonts | Kingsoft WPS is not Microsoft Works |
| T33 URL | Live approved isolated egress, DNS/redirect/SSRF proof | Mock/fail-closed checks cannot prove host firewall |

The main issue stays open until all 40 meet the independently agreed scope.
