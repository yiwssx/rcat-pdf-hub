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
pdftoppm -f 1 -l 1 -scale-to 450 -singlefile -gray \
  "$work/publisher.pdf" "$work/pub-preview"
python3 - "$work/publisher.pdf" "$work/pub-info.txt" "$work/pub-preview.pgm" <<'PY'
from pathlib import Path
import re
import sys
pdf, info, pgm = map(Path, sys.argv[1:])
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
data = pgm.read_bytes()
if not data.startswith(b"P5\n"):
    raise SystemExit("Publisher: Poppler failed to rasterize imported page")
header_end = data.find(b"\n255\n")
if header_end < 0:
    raise SystemExit("Publisher: invalid raster preview header")
pixels = data[header_end + 5:]
if len(pixels) < 3000 or sum(pixel < 240 for pixel in pixels) < 100:
    raise SystemExit("Publisher: imported PDF rendered as blank page")
print(f"PASS: pinned real LibreOffice .pub: {pages.group(1)} pages, "
      f"{width}x{height}pt, {len(pixels)} rendered pixels")
PY
test "$(sha256sum "$fixture" | cut -d' ' -f1)" = "$sha_before"
