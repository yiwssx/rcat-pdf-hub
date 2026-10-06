#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
WEB_API = ROOT / "apps" / "web" / "lib" / "api.ts"
MANIFEST = ROOT / "apps" / "web" / "lib" / "api-contract.json"
ARTIFACT = Path(os.environ.get("PDFHUB_CONTRACT_ARTIFACT", str(ROOT / "artifacts" / "contracts" / "openapi.json")))

os.environ.setdefault("PDFHUB_DATABASE_URL", "sqlite+pysqlite:////tmp/pdfhub-contract.db")
os.environ.setdefault("PDFHUB_DATA_DIR", "/tmp/pdfhub-contract-data")
os.environ.setdefault("PDFHUB_API_KEY_PEPPER", "contract-test-pepper-change-me")
os.environ.setdefault("PDFHUB_ADMIN_API_KEY", "pdfh_contract_admin_key_change_me")
os.environ.setdefault("PDFHUB_WEBHOOK_MASTER_SECRET", "contract-webhook-secret-change-me")
os.environ.setdefault("PDFHUB_DOWNLOAD_SIGNING_SECRET", "contract-download-secret-change-me-at-least-32")
os.environ.setdefault("PDFHUB_AUTH_TOKEN_SECRET", "contract-auth-secret-change-me-at-least-32")

sys.path.insert(0, str(API_ROOT))
from app.main import app  # noqa: E402


def response_schema_name(operation: dict) -> str | None:
    responses = operation.get("responses", {})
    for status in ("200", "201", "202", "203", "204"):
        response = responses.get(status)
        if not response:
            continue
        content = response.get("content", {})
        media = content.get("application/json")
        if not media:
            return None
        schema = media.get("schema", {})
        ref = schema.get("$ref")
        if ref:
            return ref.rsplit("/", 1)[-1]
        if schema.get("type") == "array":
            item_ref = schema.get("items", {}).get("$ref")
            if item_ref:
                return f"list[{item_ref.rsplit('/', 1)[-1]}]"
        return None
    return None


def fail(message: str) -> None:
    raise SystemExit(f"API contract validation failed: {message}")


schema = app.openapi()
ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
ARTIFACT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")

manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
client_source = WEB_API.read_text(encoding="utf-8")
paths = schema.get("paths", {})

markers: set[str] = set()
for entry in manifest["endpoints"]:
    method = entry["method"].lower()
    path = entry["path"]
    marker = entry["client_marker"]
    markers.add(marker)
    if marker not in client_source:
        fail(f"frontend marker disappeared: {marker}")
    operation = paths.get(path, {}).get(method)
    if operation is None:
        fail(f"OpenAPI endpoint missing: {entry['method']} {path}")
    expected = entry.get("response")
    if expected is not None:
        actual = response_schema_name(operation)
        if actual != expected:
            fail(f"{entry['method']} {path} response changed: expected {expected}, got {actual}")

for family in manifest.get("families", []):
    marker = family["client_marker"]
    markers.add(marker)
    if marker not in client_source:
        fail(f"frontend family marker disappeared: {marker}")
    method = family["method"].lower()
    prefix = family["prefix"]
    matched = [
        (path, operation[method])
        for path, operation in paths.items()
        if path.startswith(prefix) and method in operation
    ]
    if not matched:
        fail(f"OpenAPI endpoint family missing: {family['method']} {prefix}*")
    for path, operation in matched:
        actual = response_schema_name(operation)
        if actual != family["response"]:
            fail(f"{family['method']} {path} response changed: expected {family['response']}, got {actual}")

literal_re = re.compile(r'(?P<literal>["`]/api/v1/[^"`]+["`])')
client_literals = {match.group("literal") for match in literal_re.finditer(client_source)}
untracked = sorted(client_literals - markers)
if untracked:
    fail("frontend API calls are not declared in api-contract.json: " + ", ".join(untracked))

print(
    f"openapi/frontend contract: PASS "
    f"({len(manifest['endpoints'])} endpoints, {len(manifest.get('families', []))} families)"
)
try:
    artifact_label = ARTIFACT.relative_to(ROOT)
except ValueError:
    artifact_label = ARTIFACT
print(f"generated OpenAPI artifact: {artifact_label}")
