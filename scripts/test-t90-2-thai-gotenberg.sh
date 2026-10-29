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
