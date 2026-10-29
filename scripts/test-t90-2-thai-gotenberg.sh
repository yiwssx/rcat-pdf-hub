#!/usr/bin/env bash
# Strict, disposable real Chromium/Gotenberg Thai-font smoke, NOT a visual golden.
set -euxo pipefail
image="${1:-rcat-pdf-hub-gotenberg-ci}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture="$repo_root/tests/fixtures/t90-2/thai-smoke.html"
test -s "$fixture"
command -v curl >/dev/null
for cmd in pdfinfo pdffonts pdftotext; do
  if ! command -v "$cmd" >/dev/null; then
    echo "Missing required poppler tool: $cmd" >&2
    exit 1
  fi
done
tmp="$(mktemp -d)"
container="pdfhub-t90-thai-smoke-$$"
cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  rm -rf "$tmp"
}
trap cleanup EXIT
docker run -d --rm --name "$container" -p 127.0.0.1::3000 "$image" > /dev/null
port="$(docker port "$container" 3000/tcp | awk -F: 'END {print $NF}')"
if [[ ! "$port" =~ ^[0-9]+$ ]]; then
  echo "Gotenberg did not publish an isolated port" >&2
  exit 1
fi
healthy=0
for attempt in $(seq 1 45); do
  if curl --silent --show-error --fail --max-time 2 "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep 1
done
if [[ "$healthy" != 1 ]]; then
  echo "Disposable Gotenberg container did not become healthy" >&2
  docker logs "$container" >&2 || true
  exit 1
fi
curl --fail --silent --show-error --max-time 75 \
  -F "files=@$fixture;filename=index.html;type=text/html" \
  -F "preferCssPageSize=true" \
  "http://127.0.0.1:$port/forms/chromium/convert/html" > "$tmp/converted.pdf"
test "$(head -c 5 "$tmp/converted.pdf")" = "%PDF-"
pdfinfo "$tmp/converted.pdf" > "$tmp/pdfinfo.txt"
test "$(awk '/^Pages:/ { print $2 }' "$tmp/pdfinfo.txt")" = 1
grep '^Page size:' "$tmp/pdfinfo.txt" || true
python3 - "$tmp/pdfinfo.txt" <<'PY'
import re
import sys
from pathlib import Path
info = Path(sys.argv[1]).read_text(encoding="utf-8")
match = re.search(r"^Page size:\s*([0-9.]+) x ([0-9.]+) pts", info, re.M)
if not match:
    raise SystemExit("No PDF page size found in real converter output")
width, height = map(float, match.groups())
if abs(width - 595.28) > 2 or abs(height - 841.89) > 2:
    raise SystemExit(f"Expected A4 (595.28 x 841.89pt), got {width} x {height}pt")
PY
pdftotext -enc UTF-8 "$tmp/converted.pdf" "$tmp/extracted.txt"
python3 - "$tmp/extracted.txt" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding="utf-8")
for phrase in ("ทดสอบภาษาไทย", "วิทยาลัยเกษตร", "ร้อยเอ็ด"):
    if phrase not in text:
        raise SystemExit(f"Gotenberg Thai extraction failed for: {phrase!r}")
if "\ufffd" in text:
    raise SystemExit("Gotenberg Thai extraction contained replacement glyphs")
PY
pdffonts "$tmp/converted.pdf" > "$tmp/fonts.txt"
if ! grep -Eiq '(Garuda|Kinnari|Loma|Norasi|Waree)' "$tmp/fonts.txt"; then
  echo "PDF did not embed a known installed Thai font" >&2
  cat "$tmp/fonts.txt" >&2
  exit 1
fi
echo "PASS: real pinned Gotenberg Chromium Thai text, A4 page, embedded Thai font"

# Live LibreOffice conversion follows the Chromium check in the same disposable
# Gotenberg container. No extra dependencies, container network or prod credentials.
python3 "$repo_root/scripts/make-t90-2-office-fixtures.py" "$tmp/office"
python3 "$repo_root/scripts/make-t90-2-odf-fixtures.py" "$tmp/office"
for format in docx xlsx pptx odt ods odp rtf; do
  file="$tmp/office/thai.$format"
  result="$tmp/$format.pdf"
  original_hash="$(sha256sum "$file" | cut -d' ' -f1)"
  curl --fail --silent --show-error --max-time 90 \
    -F "files=@$file;filename=thai.$format;type=application/octet-stream" \
    "http://127.0.0.1:$port/forms/libreoffice/convert" > "$result"
  test "$(head -c 5 "$result")" = "%PDF-"
  pdfinfo "$result" > "$tmp/$format.info"
  pdftotext -enc UTF-8 -layout "$result" "$tmp/$format.txt"
  pdffonts "$result" > "$tmp/$format.fonts"
  test "$(sha256sum "$file" | cut -d' ' -f1)" = "$original_hash"
  python3 - "$format" "$tmp/$format.info" "$tmp/$format.txt" "$tmp/$format.fonts" <<'PY'
from pathlib import Path
import re
import sys

kind = sys.argv[1]
info = Path(sys.argv[2]).read_text(encoding="utf-8")
text = Path(sys.argv[3]).read_text(encoding="utf-8")
fonts = Path(sys.argv[4]).read_text(encoding="utf-8")
def match(pattern: str) -> str:
    found = re.search(pattern, info, re.M)
    if not found:
        raise SystemExit(f"{kind}: PDF metadata missing {pattern!r}")
    return found.group(1)
pages = int(match(r"^Pages:\s*(\d+)"))
size = re.search(r"^Page size:\s*([0-9.]+) x ([0-9.]+) pts", info, re.M)
if not size:
    raise SystemExit(f"{kind}: PDF page geometry missing")
width, height = map(float, size.groups())
expect = {"docx": (1, 595.28, 841.89),
          "xlsx": (1, 841.89, 595.28),
          "pptx": (2, 960.0, 540.0),
          "odt": (1, 595.28, 841.89),
          "ods": (1, 841.89, 595.28),
          "odp": (2, 960.0, 540.0),
          "rtf": (1, 595.28, 841.89)}[kind]
if pages != expect[0] or abs(width - expect[1]) > 3 or abs(height - expect[2]) > 3:
    raise SystemExit(f"{kind}: wrong page count or geometry: {pages}, {width} x {height}")
thai = "วิทยาลัยเกษตรและเทคโนโลยีร้อยเอ็ด"
second = "ทดสอบสระ วรรณยุกต์ และภาษาไทย"
if thai not in text or second not in text or "\ufffd" in text:
    raise SystemExit(f"{kind}: expected Thai text missing, mangled or replacement glyph")
if kind in {"xlsx", "ods"} and ("RCAT" not in text or "123" not in text):
    raise SystemExit("xlsx: missing cell or numeric value")
if kind in {"pptx", "odp"}:
    slides = text.split("\f")
    if len(slides) < 2 or thai not in slides[0] or second not in slides[1]:
        raise SystemExit("pptx: slide order or content is wrong")
# LibreOffice Impress/RTF use Loma as a Thai complex-script fallback in these fixtures.
# Require an embedded known Thai font; do not assert full source-font fidelity.
font_pattern = r"Garuda|Loma" if kind in {"odp", "rtf"} else r"Garuda"
if not re.search(font_pattern, fonts, re.IGNORECASE):
    raise SystemExit(f"{kind}: embedded Thai font missing ({font_pattern}); actual pdffonts:\n{fonts}")
print(f"PASS: real Gotenberg LibreOffice {kind}: pages={pages} size={width}x{height} pt, Thai text + embedded approved Thai font")
PY
done

# Additional real Microsoft Publisher binary regression against the same
# ephemeral Gotenberg container; no production services or download paths.
bash "$repo_root/scripts/test-t90-2-publisher-gotenberg.sh" "$port" "$tmp"

# Real HWP97 Korean text import in disposable converter.
bash "$repo_root/scripts/test-t90-2-hwp97-gotenberg.sh" "$port" "$tmp"
