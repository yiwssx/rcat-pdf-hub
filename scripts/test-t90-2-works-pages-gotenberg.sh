#!/usr/bin/env bash
# Real immutable Microsoft Works / Apple Pages test corpus, disposable CI only.
set -euo pipefail
port="$1"
work="$2"
revision="fac2bcb8ce6c81bda79b624e000c293fcdf1e7e4"
mkdir -p "$work/works-pages"
passed=0
not_supported=0
while IFS='|' read -r member expected_sha expected_bytes; do
  test -n "$member" || continue
  name="$(basename "$member")"
  source="$work/works-pages/$name"
  url="https://raw.githubusercontent.com/LibreOffice/core/$revision/writerperfect/qa/unit/data/$member"
  curl --fail --silent --show-error --location --retry 3 --max-time 40 \
    --proto '=https' --proto-redir '=https' "$url" -o "$source"
  test "$(git hash-object "$source")" = "$expected_sha"
  test "$(wc -c < "$source")" -eq "$expected_bytes"
  original_sha="$(sha256sum "$source" | cut -d' ' -f1)"
  echo "T90-2 source $name first32=$(head -c 32 "$source" | od -An -tx1 | tr -d ' \n')"
  python3 - "$source" <<'PY'
from pathlib import Path
import sys, zipfile
p = Path(sys.argv[1])
if zipfile.is_zipfile(p):
    with zipfile.ZipFile(p) as archive:
        print("T90-2 ZIP members", p.name, archive.namelist()[:18], "count", len(archive.namelist()))
PY
  pdf="$work/works-pages/$name.pdf"
  if ! curl --fail --silent --show-error --max-time 90 \
    -F "files=@$source;filename=$name;type=application/octet-stream" \
    "http://127.0.0.1:$port/forms/libreoffice/convert" -o "$pdf"; then
    echo "UNSUPPORTED: $name LibreOffice import returned error"
    not_supported=$((not_supported + 1))
    continue
  fi
  if [ "$(head -c 5 "$pdf")" != "%PDF-" ]; then
    echo "UNSUPPORTED: $name LibreOffice output is not PDF"
    not_supported=$((not_supported + 1))
    continue
  fi
  pdfinfo "$pdf" > "$pdf.info"
  pdftotext -enc UTF-8 "$pdf" "$pdf.text"
  pdftoppm -f 1 -l 1 -scale-to 450 -singlefile -gray "$pdf" "$pdf.preview"
  echo "T90-2 PDF text $name: $(head -c 250 "$pdf.text" | tr '\n' ' ')"
  if python3 - "$pdf" "$pdf.info" "$pdf.preview.pgm" <<'PY'
from pathlib import Path
import re
import sys
pdf, info, preview = map(Path, sys.argv[1:])
meta = info.read_text(encoding="utf-8")
match = re.search(r"^Pages:\s*(\d+)$", meta, re.M)
size = re.search(r"^Page size:\s*([\d.]+) x ([\d.]+) pts", meta, re.M)
if not match or not size:
    raise SystemExit("Works/Pages import PDF metadata missing")
pages = int(match.group(1))
w, h = map(float, size.groups())
if not 1 <= pages <= 30 or not 100 <= w <= 2000 or not 100 <= h <= 2000:
    raise SystemExit(f"Works/Pages page geometry invalid: {meta}")
data = preview.read_bytes()
header = data.find(b"\n255\n")
if not data.startswith(b"P5\n") or header < 0:
    raise SystemExit("Works/Pages PDF first page unreadable")
pixels = data[header + 5:]
if len(pixels) < 3000 or sum(p < 240 for p in pixels) < 100:
    raise SystemExit("Works/Pages PDF first page blank")
if pdf.stat().st_size <= 1000:
    raise SystemExit("Works/Pages PDF too small")
print(f"PASS REAL {pdf.name}: {pages} pages, {w} x {h} pt, nonblank")
PY
  then
    passed=$((passed + 1))
  else
    echo "UNSUPPORTED: $name converted blank or invalid"
    not_supported=$((not_supported + 1))
  fi
  test "$(sha256sum "$source" | cut -d' ' -f1)" = "$original_sha"
done <<'FIXTURES'
writer/libwps/pass/Works_3.0.wps|74f46091e6683e8ae1b1d0240ea695d29b44a84f|3584
writer/libwps/pass/Works_4.5.wps|65c25a002dd51fba883d7903f1c376a8b4cb619d|4608
writer/libwps/pass/Works_5.0.wps|97bb269f36513bee813010256c422a69fe21349b|6144
writer/libwps/pass/Works_6.0.wps|d0a40c4c0300e4c6b4b5f975994b065cb4d6278f|13824
writer/libetonyek/pass/Pages_4.pages|43c9213922bd26f9242ae93ed6a5aabcc85df11f|42277
writer/libetonyek/pass/Pages_5.pages|cd4438a34b451518a8547a8670fc96154255ace8|57362
FIXTURES

echo "REAL WORKS/PAGES import corpus: $passed nonblank PASS, $not_supported UNSUPPORTED"
test "$passed" -gt 0
