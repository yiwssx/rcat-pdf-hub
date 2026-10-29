#!/usr/bin/env bash
# Real HWP 97 legacy import feasibility, pinned upstream corpus; CI only.
set -euo pipefail
port="$1"
work="$2"
revision="fac2bcb8ce6c81bda79b624e000c293fcdf1e7e4"
name="hangul97-3.0.hwp"
source="$work/$name"
url="https://raw.githubusercontent.com/LibreOffice/core/$revision/hwpfilter/qa/cppunit/data/pass/$name"
curl --fail --silent --show-error --location --retry 3 --max-time 45 \
  --proto '=https' --proto-redir '=https' "$url" -o "$source"
test "$(git hash-object "$source")" = "68ff2f51269f3ab619f6465073518cd84694300c"
test "$(wc -c < "$source")" -eq 11537
digest="$(sha256sum "$source" | cut -d' ' -f1)"
echo "HWP97 real header=$(head -c 64 "$source" | od -An -tx1 | tr -d ' \n')"
pdf="$work/hwp-real.pdf"
curl --fail --silent --show-error --max-time 80 \
  -F "files=@$source;filename=$name;type=application/octet-stream" \
  "http://127.0.0.1:$port/forms/libreoffice/convert" -o "$pdf"
test "$(head -c 5 "$pdf")" = "%PDF-"
pdfinfo "$pdf" > "$pdf.info"
pdftotext -enc UTF-8 "$pdf" "$pdf.text"
pdftoppm -f 1 -l 1 -scale-to 450 -singlefile -gray "$pdf" "$pdf.preview"
python3 - "$pdf" "$pdf.info" "$pdf.preview.pgm" "$pdf.text" <<'PY'
from pathlib import Path
import re, sys
pdf, info, preview, text_path = map(Path, sys.argv[1:])
meta = info.read_text(encoding="utf-8")
page = re.search(r"^Pages:\s*(\d+)$", meta, re.M)
dims = re.search(r"^Page size:\s*([\d.]+) x ([\d.]+) pts", meta, re.M)
if not page or not dims:
    raise SystemExit("HWP legacy importer produced unreadable PDF metadata")
n = int(page.group(1))
w,h=map(float,dims.groups())
data = preview.read_bytes()
end=data.find(b"\n255\n")
pixels=data[end+5:] if end>=0 else b""
text=text_path.read_text(encoding="utf-8", errors="replace").strip()
print("HWP97 extracted UTF-8 text snippet", repr(text[:300]))
if not 1<=n<=30 or not 100<w<2000 or not 100<h<2000:
    raise SystemExit("HWP legacy converter returned invalid page geometry")
if not data.startswith(b"P5\n") or len(pixels)<3000 or sum(p<240 for p in pixels)<100:
    raise SystemExit("HWP legacy converter returned blank page")
if not text or "\ufffd" in text:
    raise SystemExit("HWP legacy converter lost all document text")
print(f"PASS HWP97 real fixture: {n} pages size {w}x{h}pt nonblank text")
PY
test "$(sha256sum "$source" | cut -d' ' -f1)" = "$digest"
