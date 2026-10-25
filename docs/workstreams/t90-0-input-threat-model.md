# T90-0.14 — Input signature and Office archive threat-model gate

**Workstream:** [T90 Master Tracker #172](https://github.com/yiwssx/rcat-pdf-hub/issues/172) · **Stacked on:** [T90-0.13 Draft PR #190](https://github.com/yiwssx/rcat-pdf-hub/pull/190)

## Assessment and bounded remediation

The existing upload pipeline already stages files, scans for malware, checks a filename-selected magic signature and normalizes MIME, then persists `FileRecord.content_type`. However, `_valid_zip_member` accepted any ZIP with `[Content_Types].xml` and an arbitrary `word/`/`xl/`/`ppt/` prefix, without validating member paths, duplicates, symlinks, entry count, declared uncompressed sizes or decompression ratios. ODF validation read `mimetype` without checking its size. Separately `_is_pdf` treated a `.pdf` **display filename** as PDF even when persisted MIME said otherwise; several PDF-only routes had no prequeue MIME gate.

| Input hazard | Existing mitigation | T90-0.14 hardening | Residual risk |
| --- | --- | --- | --- |
| Misleading extension/MIME | Upload signature normalization | Every PDF-only queue route requires persisted PDF MIME; Office converter accepts only known Office MIME; image converter retains explicit MIME allowlist | Old files with corrupted MIME need repair/reupload |
| Spoofed OOXML structure | ZIP + some prefix check | Require explicit `[Content_Types].xml` and format-specific document/workbook/presentation main part | Not a full XML OPC validator |
| ZIP traversal, absolute paths and symlink | Not fully guarded on Office uploads | Reject unsafe member paths, duplicate names (case-insensitive), symlink/special Unix types, encrypted entries and uncommon compression | Converter still needs its own OS sandbox |
| ZIP bomb, large hidden mimetype | Raw ZIP open and ODF mimetype read | Reject >2,048 members, >64 MiB per entry, >256 MiB total declared uncompressed bytes, >1,000:1 expansion (with a 1 KiB compressed-size grace), and ODF mimetype >256 B *before reading* | Incorrectly declared sizes, malicious parsers, memory/time still demand converter sandbox/resource limits |
| Active payload in macro-free OOXML | No explicit ZIP preflight | Reject `vbaProject.bin` and ActiveX paths in `.docx/.xlsx/.pptx` | Not a full macro/content malware scan; ClamAV remains mandatory |
| PDF polyglots/abusive PDFs | `%PDF-` magic and AV scanner | Existing upload policy retained; no filename bypass at enqueue | Requires stricter PDF parser validation, encrypted-file policy, qpdf sandbox limits in separately reviewed scope |
| SSRF, XML entities and document external relationships | Server process isolation and upload restrictions | No URL converters added; no remote-resource fetching capability enabled | Before adding URL/HTML/XML/SVG tools, add egress/DNS-rebinding checks and XXE-disabled parsers |

## Conservative limits and compatibility

- The archive preflight only inspects ZIP central-directory metadata and reads **at most 256 declared bytes** of the ODF `mimetype` entry; it does not extract files.
- For OOXML, the required main part is `word/document.xml`, `xl/workbook.xml`, or `ppt/presentation.xml`. This deliberately rejects fake/malformed archives previously accepted into the conversion queue.
- `.doc/.xls/.ppt` binary OLE and RTF still use existing header checks. PNG/JPEG/WebP/TIFF/BMP input rules are unchanged.
- The individual original upload remains owner-scoped, scanned, quota-limited and encrypted/unsupported formats may fail closed. **No new MIME type, converter, operation, database schema, feature enablement or storage deletion** is introduced.
- Legacy `.pdf`-named records with non-PDF stored MIME now fail PDF-only enqueue instead of overriding the normalized server MIME. This change is intentional.

## Validation

- Direct standalone regression suite `apps/api/tests/test_t90_input_security.py`: valid OOXML/ODF, ZIP traversal, symlinks, duplicate names, fake root, macros, oversized declared sizes/ratio/mimetype, PDF name spoofing and every PDF operation.
- Existing Backend, PostgreSQL 18 migration, Valkey/RQ/SeaweedFS crash tests, host Python, converter font build and OpenAPI regression must remain green.

## Deferred work (T90-0.15/0.16 and Production acceptance)

1. Shared executable adapter/dispatcher seam and centralized operation→MIME/param guard with retained backward compatibility.
2. Independent threat-model review and license/engine decision log; explicit unsupported formats.
3. Full semantic/structural parser validation for PDF and complex Office packages; attachment/relationship processing constraints; actual conversion sandbox and time/memory enforcement; authenticated full-system E2E plus golden Thai file corpus.
4. Redis partition, S3 network cut, multi-host load and live sanitized backup rehearsal remain **T90-5 pre-release gates**, not prerequisites for starting T90-1.

**Release controls:** Draft/unmerged, no Production migrations/deploys, journal/multi-output flags stay OFF. CI success is not permission to enable or deploy.
