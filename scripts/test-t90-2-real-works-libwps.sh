#!/usr/bin/env bash
# Real Works .wps libwps-tools probe, run ONLY in disposable API CI image.
set -euo pipefail
revision="fac2bcb8ce6c81bda79b624e000c293fcdf1e7e4"
temp="$(mktemp -d)"
# CI test container runs as uid 10001. mktemp defaults to 0700 root,
# making the read-only bind-mount inaccessible unless mode is relaxed.
chmod 0755 "$temp"
trap 'rm -rf "$temp"' EXIT
passed=0
while IFS='|' read -r name blob bytes; do
  test -n "$name" || continue
  source="$temp/$name"
  curl --fail --silent --show-error --location --retry 3 --max-time 40 \
    --proto '=https' --proto-redir '=https' \
    "https://raw.githubusercontent.com/LibreOffice/core/$revision/writerperfect/qa/unit/data/writer/libwps/pass/$name" -o "$source"
  test "$(git hash-object "$source")" = "$blob"
  test "$(wc -c < "$source")" -eq "$bytes"
  sum="$(sha256sum "$source" | cut -d' ' -f1)"
  if docker run --rm --network none --entrypoint /usr/bin/wps2text \
    -v "$temp:/fixtures:ro" rcat-pdf-hub-api-test "/fixtures/$name" \
    > "$temp/$name.txt" 2> "$temp/$name.err"; then
    python3 - "$temp/$name.txt" "$name" <<'PY'
from pathlib import Path
import sys
data=Path(sys.argv[1]).read_bytes()
text=data.decode("utf-8", errors="replace")
print("WORKS LIBWPS TEXT", sys.argv[2], "bytes", len(data), "excerpt", repr(text[:260]))
if len(text.strip()) < 10 or "\ufffd" in text:
    raise SystemExit("Works libwps document content missing or invalid")
print("PASS genuine Works text", sys.argv[2])
PY
    passed=$((passed + 1))
  else
    echo "UNSUPPORTED libwps $name: $(head -c 220 "$temp/$name.err" | tr '\n' ' ')"
  fi
  test "$(sha256sum "$source" | cut -d' ' -f1)" = "$sum"
done <<'FIXTURES'
Works_3.0.wps|74f46091e6683e8ae1b1d0240ea695d29b44a84f|3584
Works_4.5.wps|65c25a002dd51fba883d7903f1c376a8b4cb619d|4608
Works_5.0.wps|97bb269f36513bee813010256c422a69fe21349b|6144
Works_6.0.wps|d0a40c4c0300e4c6b4b5f975994b065cb4d6278f|13824
FIXTURES
echo "WPS libwps genuine text converters $passed/4 accepted"
test "$passed" -gt 0
