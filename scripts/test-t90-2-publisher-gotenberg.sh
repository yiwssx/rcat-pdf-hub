#!/usr/bin/env bash
# T90-2 real Microsoft Publisher import acceptance using pinned upstream fixture.
# This runs ONLY inside disposable CI Gotenberg on localhost; never prod networking.
set -euxo pipefail

port="$1"
work="$2"
test -n "$port"
test -d "$work"
command -v git >/dev/null
command -v pdftoppm >/dev/null

# Licensed upstream LibreOffice writerperfect/libmspub QA corpus. Immutable git
# revision and git blob object SHA protect against silent fixture substitution.
upstream_commit="fac2bcb8ce6c81bda79b624e000c293fcdf1e7e4"
fixture_sha="607a07ae2d362e4a1f6e779dfff88726fe74f910"
fixture_url="https://raw.githubusercontent.com/LibreOffice/core/$upstream_commit/writerperfect/qa/unit/data/draw/libmspub/pass/fdo59355-1.pub"
fixture="$work/fdo59355-1.pub"

curl --fail --silent --show-error --location --retry 3 --max-time 45 \
  --proto '=https' --proto-redir '=https' "$fixture_url" -o "$fixture"
test "$(git hash-object "$fixture")" = "$fixture_sha"
test "$(wc -c < "$fixture")" -eq 10752
test "$(head -c 8 "$fixture" | od -An -tx1 | tr -d ' \n')" = "d0cf11e0a1b11ae1"

# Validate the exact upstream binary through the same stdlib-only OLE preflight
# the application applies during upload and worker execution.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONPATH="$repo_root/apps/api" python3 - "$fixture" <<'PY'
from pathlib import Path
import sys
from app.services.to_pdf_publisher import validate_publisher_ole
names = validate_publisher_ole(Path(sys.argv[1]))
print("PASS: real Publisher CFB bounded header and streams:", names)
PY

sha_before="$(sha256sum "$fixture" | cut -d' ' -f1)"
curl --fail --silent --show-error --max-time 100 \
  -F "files=@$fixture;filename=fdo59355-1.pub;type=application/octet-stream" \
  "http://127.0.0.1:$port/forms/libreoffice/convert" > "$work/publisher.pdf"

test "$(head -c 5 "$work/publisher.pdf")" = "%PDF-"
pdfinfo "$work/publisher.pdf" > "$work/pub-info.txt"
pdftotext -enc UTF-8 "$work/publisher.pdf" "$work/pub-text.txt"
pdftoppm -f 1 -l 2 -scale-to 450 -gray \
  "$work/publisher.pdf" "$work/pub-preview"
python3 - "$work/publisher.pdf" "$work/pub-info.txt" \
  "$work/pub-preview-1.pgm" "$work/pub-preview-2.pgm" <<'PY'
from pathlib import Path
import re
import sys
pdf, info, page1, page2 = map(Path, sys.argv[1:])
metadata = info.read_text(encoding="utf-8")
pages = re.search(r"^Pages:\s*(\d+)$", metadata, re.M)
size = re.search(r"^Page size:\s*([\d.]+) x ([\d.]+) pts", metadata, re.M)
if not pages or not size:
    raise SystemExit("Publisher: converter returned unreadable PDF metadata")
width, height = map(float, size.groups())
if (int(pages.group(1)) != 2
        or abs(width - 595.28) > 3 or abs(height - 841.89) > 3
        or pdf.stat().st_size <= 1000):
    raise SystemExit(f"Publisher: unexpected PDF result: {metadata}")
# Rendered first page must contain meaningful nonwhite pixels. This detects
# format misclassification that technically yields a blank/empty PDF.
blank_pages = []
for page_no, pgm in enumerate((page1, page2), start=1):
    data = pgm.read_bytes()
    if not data.startswith(b"P5\n"):
        raise SystemExit(f"Publisher: Poppler failed to rasterize page {page_no}")
    header_end = data.find(b"\n255\n")
    if header_end < 0:
        raise SystemExit(f"Publisher: page {page_no} has invalid raster preview header")
    pixels = data[header_end + 5:]
    if len(pixels) < 3000:
        raise SystemExit(f"Publisher: page {page_no} rendered incomplete raster")
    foreground = sum(pixel < 240 for pixel in pixels)
    if foreground < 100:
        blank_pages.append(page_no)
        print(f"T21_PAGE_OBSERVATION page={page_no} visibly_blank=true "
              f"note=source-layout-comparison-pending")
    else:
        print(f"T21_PAGE_OBSERVATION page={page_no} visibly_blank=false "
              f"dark_pixels={foreground}")
if 1 in blank_pages:
    raise SystemExit("Publisher: confirmed first page of source fixture rendered blank")
# A genuinely blank second source page can be intentional. Without a
# reference raster of the original Publisher document, FAILing all conversion
# tests or claiming full fidelity would both be unjustified. Track it honestly.
print(f"T21_PAGE_INVENTORY rasterized=2 blank_pages="
      f"{','.join(map(str, blank_pages)) or 'none'} "
      f"source_visual_reference=pending")
print(f"PASS: pinned real LibreOffice .pub: 2 A4 PDF pages, "
      f"first page nonblank, both pages rasterizable, visual fidelity UNVERIFIED")
PY
test "$(sha256sum "$fixture" | cut -d' ' -f1)" = "$sha_before"

# Generate machine-readable, public-fixture-only provenance on stdout; never
# upload original institutional documents or claim a T90-5 release.
# Two pages and page-1 raster were checked above. This records precisely that
# narrow claim, not full Thai font/layout fidelity or an authenticated job.
output_sha="$(sha256sum "$work/publisher.pdf" | cut -d' ' -f1)"
test "${#output_sha}" -eq 64
printf 'T90_2_T21_REAL_PUBLISHER_EVIDENCE source_sha256=%s output_sha256=%s pages=2 pages_rasterized=2 first_page_nonblank=true page2_source_visual_reference=pending original_unchanged=true corpus=LibreOffice-writerperfect-fdo59355-1.pub\n' \
  "$sha_before" "$output_sha"
