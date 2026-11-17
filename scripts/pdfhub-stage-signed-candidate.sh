#!/usr/bin/env bash
# Staging ONLY. Build private OCI archives on a separate existing Docker context.
# Never load/push/tag a runtime image or modify Production containers.
set -Eeuo pipefail
umask 077
APP_SHA=645de50a9205f5b54455ea78d8fef26e97640e9c
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
die() { printf 'PDFHUB_STAGE_BLOCKED=%s\n' "$*" >&2; exit 1; }
usage() { die "Usage: $0 --preflight | --build | --verify CANDIDATE_DIR"; }
mode="${1:---preflight}"
[[ "$mode" == "--preflight" || "$mode" == "--build" || "$mode" == "--verify" ]] || usage
if [[ "$mode" == "--verify" ]]; then
  [[ $# -eq 2 ]] || usage
  [[ -n "${PDFHUB_STAGE_VERIFY_KEY:-}" ]] || die "Set PDFHUB_STAGE_VERIFY_KEY to trusted public key"
  exec python3 scripts/pdfhub-stage-oci.py verify "$2" "$PDFHUB_STAGE_VERIFY_KEY"
fi
[[ $# -eq 1 ]] || usage
for cmd in docker git python3 openssl tar sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || die "Missing tool: $cmd"
done
[[ -z "${DOCKER_HOST:-}" && -z "${BUILDX_BUILDER:-}" ]] \
  || die "DOCKER_HOST and BUILDX_BUILDER environment overrides are forbidden"
STAGE_CONTEXT="${PDFHUB_STAGE_DOCKER_CONTEXT:-}"
STAGE_BUILDER="${PDFHUB_STAGE_BUILDER:-}"
OUT_ROOT="${PDFHUB_STAGE_OUTPUT_ROOT:-}"
FONT_ROOT="${PDFHUB_STAGE_FONTS_DIR:-}"
VERIFY_KEY="${PDFHUB_STAGE_VERIFY_KEY:-}"
SIGN_KEY="${PDFHUB_STAGE_SIGN_KEY:-}"
[[ "$STAGE_CONTEXT" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{2,63}$ && "$STAGE_CONTEXT" != "default" ]] \
  || die "Set named, non-default PDFHUB_STAGE_DOCKER_CONTEXT"
[[ "$STAGE_BUILDER" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{2,63}$ && "$STAGE_BUILDER" != "default" ]] \
  || die "Set existing non-default PDFHUB_STAGE_BUILDER"
[[ -n "$OUT_ROOT" && -d "$OUT_ROOT" && ! -L "$OUT_ROOT" ]] \
  || die "PDFHUB_STAGE_OUTPUT_ROOT must be an existing private directory"
[[ -n "$FONT_ROOT" && -d "$FONT_ROOT" && ! -L "$FONT_ROOT" ]] \
  || die "PDFHUB_STAGE_FONTS_DIR must contain private approved 13Fonts"
[[ -n "$VERIFY_KEY" && -f "$VERIFY_KEY" && ! -L "$VERIFY_KEY" ]] \
  || die "Require locally trusted operator public key"
[[ -n "$SIGN_KEY" && -f "$SIGN_KEY" && ! -L "$SIGN_KEY" ]] \
  || die "Require protected operator private signing key"
default_host="$(docker context inspect default --format '{{.Endpoints.docker.Host}}' 2>/dev/null)" \
  || die "Cannot inspect default Docker daemon endpoint"
stage_host="$(docker context inspect "$STAGE_CONTEXT" --format '{{.Endpoints.docker.Host}}' 2>/dev/null)" \
  || die "Unrecognized staging Docker context"
[[ -n "$default_host" && -n "$stage_host" && "$default_host" != "$stage_host" ]] \
  || die "Staging endpoint equals the default/Production endpoint"
builder_info="$(docker --context "$STAGE_CONTEXT" buildx inspect "$STAGE_BUILDER" 2>/dev/null)" \
  || die "Dedicated staging Buildx builder not found"
grep -Eq '^[[:space:]]*Driver:[[:space:]]+docker-container([[:space:]]|$)' <<< "$builder_info" \
  || die "Require an isolated docker-container builder"
grep -Eq "^[[:space:]]*Endpoint:[[:space:]]+${STAGE_CONTEXT}([[:space:]]|$)" <<< "$builder_info" \
  || die "Builder endpoint does not match approved staging context"
[[ "$(git cat-file -t "${APP_SHA}^{commit}")" == "commit" ]] \
  || die "Approved signed-source commit is unavailable"
git merge-base --is-ancestor "$APP_SHA" HEAD || die "Approved source not ancestral to current operator code"
[[ "$(stat -c '%u' "$OUT_ROOT")" == "$(id -u)" && "$(stat -c '%a' "$OUT_ROOT")" == 700 ]] \
  || die "Staging output directory must be user-owned, mode 700"
case "$(readlink -f "$OUT_ROOT")/" in
  "$(readlink -f "$ROOT")/"*) die "Output must be outside the repository checkout" ;;
esac
[[ "$(stat -c '%a' "$SIGN_KEY")" == 600 || "$(stat -c '%a' "$SIGN_KEY")" == 400 ]] \
  || die "Signing private key must have permissions 600 or 400"
shopt -s nullglob
font_files=("$FONT_ROOT"/*.ttf)
[[ "${#font_files[@]}" -eq 57 ]] || die "Staging input directory must have exactly 57 TTF files"
# Verify the new staging private font input, not the already accepted live Host.
font_result="$( (cd "$FONT_ROOT" && sha256sum -- ./*.ttf) \
  | PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/scripts/verify-office-font-bundle.py" )" \
  || die "Staging font fingerprint differs from approved manifest"
[[ "$font_result" == "PASS verified 57 exact font files and contents in Gotenberg" ]] \
  || die "Unexpected font verifier result"
echo "PDFHUB_STAGE_PREFLIGHT=PASS"
echo "PDFHUB_STAGE_SIGNED_SOURCE_SHA=$APP_SHA"
echo "PDFHUB_STAGE_BUILDER_ENDPOINT_ISOLATED=PASS"
echo "PDFHUB_STAGE_PRIVATE_FONT_INPUTS=PASS_57_OF_57"
echo "PDFHUB_PRODUCTION_MUTATION=NONE"
if [[ "$mode" == "--preflight" ]]; then
  echo "PDFHUB_STAGE_CANDIDATE=READY_NOT_BUILT"
  exit 0
fi
[[ "${PDFHUB_STAGE_APPROVAL:-}" == "APPROVED_PRIVATE_STAGE_BUILD_ONLY" ]] \
  || die "Explicit staging-build acknowledgement absent"
candidate="$(mktemp -d "$OUT_ROOT/pdfhub-stage-${APP_SHA:0:12}-XXXXXX")"
source_tree="$(mktemp -d "$OUT_ROOT/.pdfhub-stage-context-XXXXXX")"
trap 'if [[ -n "${source_tree:-}" && -d "$source_tree" ]]; then rm -rf -- "$source_tree"; fi' EXIT
git archive "$APP_SHA" | tar -xf - -C "$source_tree"
mkdir -p "$source_tree/ops/gotenberg/fonts/13fonts"
cp -p -- "${font_files[@]}" "$source_tree/ops/gotenberg/fonts/13fonts/"
for component in api web gotenberg; do
  case "$component" in
    api) context_path="$source_tree/apps/api" ;;
    web) context_path="$source_tree/apps/web" ;;
    gotenberg) context_path="$source_tree/ops/gotenberg" ;;
  esac
  archive="$candidate/$component.oci.tar"
  : > "$archive"
  echo "PDFHUB_STAGE_BUILD_COMPONENT=$component"
  docker --context "$STAGE_CONTEXT" buildx build \
    --builder "$STAGE_BUILDER" --platform linux/amd64 \
    --provenance=mode=max \
    --label "org.opencontainers.image.revision=$APP_SHA" \
    --label 'org.opencontainers.image.source=https://github.com/yiwssx/rcat-pdf-hub' \
    --output "type=oci,dest=$archive" "$context_path"
  chmod 600 "$archive"
  python3 scripts/pdfhub-stage-oci.py inspect "$archive" "$APP_SHA" \
    > "$candidate/$component.metadata.json" || die "OCI/BuildKit SLSA verification failed: $component"
  chmod 600 "$candidate/$component.metadata.json"
done
python3 scripts/pdfhub-stage-oci.py receipt "$candidate" "$APP_SHA" "$VERIFY_KEY" >/dev/null \
  || die "Candidate build receipt failed"
openssl dgst -sha256 -sign "$SIGN_KEY" -out "$candidate/candidate.sig" "$candidate/candidate.json" \
  || die "Owner-controlled candidate signature failed"
chmod 600 "$candidate/candidate.sig"
python3 scripts/pdfhub-stage-oci.py verify "$candidate" "$VERIFY_KEY" \
  || die "Local signed OCI candidate verification failed"
echo "PDFHUB_STAGE_LOCAL_PRIVATE_EVIDENCE_DIR=$candidate"
echo "PDFHUB_STAGE_NO_LOAD_NO_PUSH_NO_DEPLOY=PASS"
