#!/usr/bin/env bash
# M05: disposable REAL bilingual model proof; only public fixed test sentences.
# This does not authorize model licensing, ship weights, or change Production.
set -euo pipefail
for cmd in curl docker python3 sha256sum; do command -v "$cmd" >/dev/null; done
root="$(mktemp -d)"
network="m05-ci-$RANDOM"
container="pdf-translate-mac-$RANDOM"
cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  rm -rf "$root"
}
trap cleanup EXIT
mkdir -p "$root/packages"
for pair in en_th th_en; do
  archive="$root/translate-$pair-1_9.argosmodel"
  curl --fail --location --retry 3 --max-time 160 --silent --show-error \
    --proto '=https' --proto-redir '=https' \
    "https://data.argosopentech.com/argospm/v1/translate-$pair-1_9.argosmodel" \
    -o "$archive"
  test "$(wc -c < "$archive")" -gt 20000000
  sha256sum "$archive"
  python3 - "$archive" "$root/packages/translate-$pair-1_9" "$pair" <<'PY'
import json
from pathlib import Path
import shutil
import stat
import sys
import zipfile
archive, destination, expected = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
source, target = expected.split("_")
with zipfile.ZipFile(archive) as z:
    infos = z.infolist()
    if not infos or len(infos) > 300 or sum(i.file_size for i in infos) > 700_000_000:
        raise SystemExit("Invalid model archive structure or resource budget")
    entries = [i for i in infos if i.filename.endswith("metadata.json")]
    if len(entries) != 1:
        raise SystemExit("Model archive requires one metadata.json")
    metadata = json.loads(z.read(entries[0]))
    if metadata.get("from_code") != source or metadata.get("to_code") != target:
        raise SystemExit("Model direction does not match its filename")
    print("M05_MODEL_METADATA", expected, {
        k: metadata.get(k) for k in ("package_version", "from_code", "to_code", "license", "license_url")
    })
    prefix = entries[0].filename.removesuffix("metadata.json")
    destination.mkdir(parents=True)
    for info in infos:
        name = info.filename
        if not name.startswith(prefix):
            raise SystemExit("Model archive contains files outside package root")
        relative = Path(name.removeprefix(prefix))
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise SystemExit("Model archive path traversal")
        if stat.S_ISLNK(info.external_attr >> 16):
            raise SystemExit("Model archive symlink not permitted")
        item = destination / relative
        if info.is_dir():
            item.mkdir(parents=True, exist_ok=True)
            continue
        item.parent.mkdir(parents=True, exist_ok=True)
        with z.open(info) as inp, item.open("wb") as out:
            shutil.copyfileobj(inp, out)
    if not (destination / "metadata.json").is_file():
        raise SystemExit("Missing extracted package metadata")
PY
done

# Immutable image digest, no host ports, no egress after packages are downloaded.
image="libretranslate/libretranslate@sha256:1de2d7056bb8ad607a412f4563d9abe324ff632b43b5be9428bcc8e213aebb32"
docker pull "$image" >/dev/null
docker network create --internal "$network" >/dev/null
docker run --detach --rm --name "$container" --network "$network" \
  --memory 2g --cpus 2 --pids-limit 128 --cap-drop ALL \
  --security-opt no-new-privileges \
  -e LT_HOST=0.0.0.0 -e LT_PORT=5000 -e LT_LOAD_ONLY=en,th \
  -e LT_UPDATE_MODELS=false -e LT_DISABLE_WEB_UI=true \
  -e LT_DISABLE_FILES_TRANSLATION=true -e LT_DEBUG=false \
  -v "$root/packages:/home/libretranslate/.local/share/argos-translate/packages:ro" \
  "$image" >/dev/null

ready=0
for i in $(seq 1 80); do
  if docker exec "$container" /app/venv/bin/python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2).read()" \
    >/dev/null 2>&1; then ready=1; break; fi
  sleep 2
done
if [[ "$ready" != 1 ]]; then
  docker logs "$container" | tail -50
  echo 'M05: real no-egress offline model failed to become ready' >&2
  exit 1
fi

# Query from inside the same offline service container. No institutional PDFs.
docker exec "$container" /app/venv/bin/python - <<'PY'
import json
import urllib.request
base = "http://127.0.0.1:5000"
def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(base+path, data=data,
        headers={"Content-Type":"application/json","Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.load(response)
languages = request("/languages")
mapping = {item["code"]: set(item.get("targets", [])) for item in languages}
if "th" not in mapping.get("en", set()) or "en" not in mapping.get("th", set()):
    raise SystemExit("M05: both direct model language directions unavailable")
for source, target, phrase in (
    ("en","th","The farmer measures soil moisture."),
    ("th","en","เกษตรกรตรวจสอบความชื้นในดิน"),
):
    response = request("/translate", {"q":phrase,"source":source,"target":target,"format":"text"})
    output = response.get("translatedText","")
    if not isinstance(output,str) or len(output.strip()) < 4 or output.strip()==phrase:
        raise SystemExit("M05: missing genuine non-echo translation")
    if target=="th" and not any("\u0e01"<=ch<="\u0e5b" for ch in output):
        raise SystemExit("M05: English-to-Thai output has no Thai glyphs")
    if target=="en" and not any(ch.isascii() and ch.isalpha() for ch in output):
        raise SystemExit("M05: Thai-to-English output has no English letters")
    print("M05_REAL_MODEL_TRANSLATION", f"{source}->{target}", repr(output))
print("M05_REAL_MODEL_PROBE_PASS: both directions, isolated offline runtime, fixed public input")
PY
