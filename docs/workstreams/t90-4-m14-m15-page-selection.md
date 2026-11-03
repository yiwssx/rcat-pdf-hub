# T90-4 M14/M15 — Delete and rearrange real PDF page contents

**Code scope:** Two independently addressable, default-disabled tools:

- M14: \`POST /api/v1/pdf/manage-pages/delete\` with \`file_id\` and
  1-based \`pages\` list to delete. Output contains all *other* PDF pages,
  in their original order. Deleting every page is rejected.
- M15: \`POST /api/v1/pdf/manage-pages/reorder\` with \`file_id\` and
  complete 1-based \`order\` permutation. Every input page appears
  exactly once, in the specified output order. No missing or duplicate
  page indices.
- Both create **actual PDF output pages with unchanged source content
  streams**, not placeholder page lists, screenshots or renamed files.
  The engine also verifies content stream equality and output page count
  after writing a new PDF using pypdf.

Access and safety: new \`PDFHUB_MANAGE_PAGE_TOOLS_ENABLED=false\` by default;
new routes omitted from default OpenAPI; user must have \`pdf:split\` scope.
API and worker check the persisted PDF owner, source-system, MIME, original
filename extension, expiry, original signature and exact job parameters.
Existing user-scoped job audit, quota, output malware scan, expiry and
retention are reused. Default PDFs and flags are unchanged.

Bounds: strict source PDF <=24 MiB, <=120 pages; output <=48 MiB;
no encrypted files, source symlinks, destination replacement, noninteger,
duplicate, out-of-range or ambiguous page selections. Private temporary
staging and exclusive destination creation prevent partial PDF downloads.

Automated tests build original 4-page PDFs with distinct text on every
page and assert actual output text order, source immutability, page content
and size constraints. Negative cases cover deleting all pages, invalid
permutations, encrypted source, owner, expiry, MIME and disabled feature.

**Scope caveats:** This is page selection and reconstruction, not
cryptographic erasure/redaction or certified removal of sensitive content.
It does not promise visual editing, embedded document hyperlinks/
bookmarks preservation or authenticated digital signature retention.
Original RCAT Thai/large/complex documents, signed PDF effects, target-host
isolation/AV and live school-only Workspace OIDC must pass independent
T90-5 QA before VERIFIED/RELEASED or deployment. No feature flag activation.
