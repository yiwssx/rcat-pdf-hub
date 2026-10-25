#!/usr/bin/env python3
"""T90-0 artifact manifest reference validator (planning only).

Standard-library only. This is NOT imported by the production API or workers;
it documents fail-closed invariants for an eventual owner-scoped multi-output seam.
"""
from __future__ import annotations

import ast
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/pdf-output-manifest.v1.schema.json"
REGISTRY = ROOT / "contracts/pdf-tools.v1.json"
WORKER = ROOT / "apps/api/app/worker_tasks.py"
MODELS = ROOT / "apps/api/app/models.py"
REQUESTS = ROOT / "apps/api/app/schemas.py"
JOB_ROUTER = ROOT / "apps/api/app/routers/jobs.py"
FILE_ROUTER = ROOT / "apps/api/app/routers/files.py"
EXPECTED_KINDS = {"pdf-to-images": ("legacy_zip", ".zip", "application/zip")}
VALID_ROLES = {"result", "part", "bundle"}
MAX_RASTER_PAGES = 200
MAX_ITEMS = MAX_RASTER_PAGES + 1
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MIME = re.compile(r"^[a-zA-Z0-9.+-]+/[a-zA-Z0-9.+*-]+$")


def _uuid(s):
    try:
        return isinstance(s, str) and str(uuid.UUID(s)) == s.lower()
    except (ValueError, TypeError, AttributeError):
        return False


def _datetime(value):
    if not isinstance(value, str):
        return None
    try:
        obj = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return obj if obj.tzinfo is not None and obj.utcoffset() is not None else None
    except (ValueError, TypeError):
        return None


def _safe_filename(name):
    return (isinstance(name, str) and 1 <= len(name) <= 255
            and name not in {".", ".."} and name == name.strip()
            and not name.startswith(".")
            and not any(c in "/\\:" or ord(c) < 32 or ord(c) == 127 for c in name))


def inspect_worker_output_spec(source):
    """Extract literal current worker outputs to detect single-file/ZIP drift."""
    tree = ast.parse(source)
    target = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_output_spec"), None)
    if target is None or len(target.body) != 2:
        raise ValueError("unsupported worker _output_spec structure")
    first, fallback = target.body
    if not isinstance(first, ast.If) or not isinstance(fallback, ast.Return) or len(first.body) != 1:
        raise ValueError("unexpected _output_spec branching")
    branch = first.test
    if not isinstance(branch, ast.Compare) or not isinstance(branch.left, ast.Name) or branch.left.id != "operation" or len(branch.comparators) != 1:
        raise ValueError("unexpected output operation branch")
    operation = ast.literal_eval(branch.comparators[0])
    zip_tuple = ast.literal_eval(first.body[0].value)
    pdf_tuple = ast.literal_eval(fallback.value)
    if not isinstance(first.body[0], ast.Return) or zip_tuple != (".zip", "application/zip") or pdf_tuple != (".pdf", "application/pdf"):
        raise ValueError("unexpected worker result suffix/MIME")
    return operation


def validate_repository_contract(registry, schema):
    errors = []
    if not isinstance(schema, dict) or schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        return ["manifest schema version/draft missing"]
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        errors.append("manifest top-level must reject additional properties")
    props = schema.get("properties", {})
    required = {"schema_version", "job_id", "status", "requested_by", "generated_at", "primary_file_id", "artifacts"}
    if not isinstance(props, dict) or set(props) != required or set(schema.get("required", [])) != required:
        errors.append("unexpected manifest field shape")
    if any(prop in props for prop in {"download_url", "signed_url", "stored_name", "path"}):
        errors.append("private storage or URL leaked in manifest")
    children = props.get("artifacts", {}).get("items", {})
    child_fields = {"file_id", "role", "ordinal", "file_name", "content_type", "size", "sha256", "source_system", "expires_at"}
    if children.get("additionalProperties") is not False or set(children.get("properties", {})) != child_fields:
        errors.append("artifact item shape drift or additional fields allowed")
    if children.get("maxProperties") is not None or props.get("artifacts", {}).get("maxItems") != MAX_ITEMS:
        errors.append("manifest max artifact count changed")
    if schema.get("title", "").find("planning") < 0:
        errors.append("manifest must remain a planning contract")
    if not isinstance(registry, dict) or not isinstance(registry.get("tools"), list) or len(registry["tools"]) != 90:
        return errors + ["90 tool registry missing"]
    actual_zip_op = inspect_worker_output_spec(WORKER.read_text(encoding="utf-8"))
    if actual_zip_op != "pdf-to-images":
        errors.append("worker ZIP operation baseline changed")
    models_text = MODELS.read_text(encoding="utf-8")
    schemas_text = REQUESTS.read_text(encoding="utf-8")
    job_text = JOB_ROUTER.read_text(encoding="utf-8")
    file_text = FILE_ROUTER.read_text(encoding="utf-8")
    worker_text = WORKER.read_text(encoding="utf-8")
    for label, expression in (
        ("JobRecord.output_file_id", "output_file_id: Mapped[str | None]"),
        ("FileRecord.source_system", "source_system: Mapped[str]"),
        ("FileRecord.expires_at", "expires_at: Mapped[datetime | None]"),
    ):
        if expression not in models_text:
            errors.append(f"legacy DB seam changed: {label}")
    if "output_file_id: str | None" not in schemas_text or "output_file_id=job.output_file_id" not in job_text:
        errors.append("legacy JobOut single result seam changed")
    if "output_file_id=record.id" not in worker_text or "store_staged_file(output," not in worker_text:
        errors.append("legacy single-file worker commit seam changed")
    if "def _owned_file(" not in file_text or "def _active_file_path(" not in file_text or "def download_file(" not in file_text:
        errors.append("existing authorized/expiry download seam changed")
    known_ops = set(registry.get("existing", {}).get("backend_operations", []))
    if len(known_ops) != 13:
        errors.append("expected exactly 13 legacy operations")
    for i, tool in enumerate(registry["tools"]):
        label = str(tool.get("id", i))
        legacy = tool.get("legacy", {}).get("operations", [])
        kinds = {"legacy_zip" if op == actual_zip_op else "legacy_pdf" for op in legacy}
        current = "none" if not kinds else next(iter(kinds)) if len(kinds) == 1 else "mixed"
        a = tool.get("artifact_contract", {})
        if (a.get("schema_ref") != "contracts/pdf-output-manifest.v1.schema.json"
                or a.get("status") != "planning_only"
                or a.get("current_delivery") != current
                or a.get("target_cardinality") != tool.get("planned_contract", {}).get("output", {}).get("cardinality")
                or type(a.get("multi_output_migration_required")) is not bool
                or a.get("multi_output_migration_required") != (a.get("target_cardinality") == "multi" and current != "none")):
            errors.append(f"tool {label}: result delivery source/target drift")
        if tool.get("runtime_enabled") is not False:
            errors.append(f"tool {label}: new artifact contract must not enable tools")
    return errors


def validate_manifest(manifest, job, file_records, related_output_ids):
    """Reference checks with trusted JobRecord/FileRecord snapshots + job-artifact linkage.

    A passed result does NOT replace runtime DB authorizations or malware/quota scans.
    """
    errors = []
    if not isinstance(manifest, dict) or not isinstance(job, dict) or not isinstance(file_records, dict):
        return ["missing trusted manifest/job/file records"]
    if not isinstance(related_output_ids, (set, frozenset)):
        return ["missing trusted job-artifact linkage"]
    fields = {"schema_version", "job_id", "status", "requested_by", "generated_at", "primary_file_id", "artifacts"}
    if set(manifest) != fields or manifest.get("schema_version") != "1.0.0" or manifest.get("status") != "completed":
        errors.append("invalid or unapproved manifest shape/state")
    if job.get("status") != "completed" or manifest.get("job_id") != job.get("id") or not _uuid(manifest.get("job_id")):
        errors.append("manifest not bound to a completed job")
    owner = manifest.get("requested_by")
    if not isinstance(owner, str) or not owner or len(owner) > 120 or job.get("requested_by") != owner:
        errors.append("job owner mismatch")
    generated = _datetime(manifest.get("generated_at"))
    if generated is None:
        errors.append("generated_at must be timezone-aware")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= MAX_ITEMS:
        return errors + ["invalid artifact count"]
    ids, names, ordinals, bundles, results = set(), set(), [], [], []
    primary = manifest.get("primary_file_id")
    if not _uuid(primary):
        errors.append("invalid primary file ID")
    for index, a in enumerate(artifacts):
        if not isinstance(a, dict):
            errors.append(f"artifact {index}: invalid record")
            continue
        expected = {"file_id", "role", "file_name", "content_type", "size", "sha256", "source_system", "expires_at"}
        if set(a) not in (expected, expected | {"ordinal"}):
            errors.append(f"artifact {index}: unexpected/omitted fields")
        fid, role, name = a.get("file_id"), a.get("role"), a.get("file_name")
        if not _uuid(fid) or fid in ids:
            errors.append(f"artifact {index}: invalid/duplicate file ID")
        else:
            ids.add(fid)
        if role not in VALID_ROLES:
            errors.append(f"artifact {index}: invalid role")
        if not _safe_filename(name) or name.casefold() in names:
            errors.append(f"artifact {index}: unsafe/duplicate filename")
        elif isinstance(name, str):
            names.add(name.casefold())
        if role == "part":
            if type(a.get("ordinal")) is not int or not 1 <= a["ordinal"] <= MAX_RASTER_PAGES:
                errors.append(f"artifact {index}: missing/invalid part ordinal")
            else:
                ordinals.append(a["ordinal"])
        elif "ordinal" in a:
            errors.append(f"artifact {index}: non-part cannot have ordinal")
        if role == "bundle":
            bundles.append(a)
            if a.get("content_type") != "application/zip":
                errors.append(f"artifact {index}: bundle must be ZIP")
        if role == "result":
            results.append(a)
        if not isinstance(a.get("content_type"), str) or not MIME.fullmatch(a["content_type"]):
            errors.append(f"artifact {index}: invalid content type")
        if type(a.get("size")) is not int or a["size"] < 0:
            errors.append(f"artifact {index}: invalid size")
        if not isinstance(a.get("sha256"), str) or not SHA256.fullmatch(a["sha256"]):
            errors.append(f"artifact {index}: invalid SHA256")
        if a.get("source_system") != owner:
            errors.append(f"artifact {index}: owner mismatch")
        expiry = None if a.get("expires_at") is None else _datetime(a["expires_at"])
        if a.get("expires_at") is not None and (expiry is None or (generated and expiry <= generated)):
            errors.append(f"artifact {index}: expired or timezone-naive")
        if fid not in related_output_ids:
            errors.append(f"artifact {index}: file not linked to completed job")
        saved = file_records.get(fid) if isinstance(fid, str) else None
        if not isinstance(saved, dict) or any(saved.get(k) != a.get(k) for k in (
            "source_system", "content_type", "size", "sha256", "expires_at"
        )):
            errors.append(f"artifact {index}: persisted FileRecord mismatch")
    if primary not in ids:
        errors.append("primary file not in artifact collection")
    if job.get("output_file_id") is not None and job["output_file_id"] != primary:
        errors.append("legacy primary output mismatch")
    if len(bundles) > 1 or len(results) > 1 or (bundles and results):
        errors.append("conflicting bundle/result roles")
    if (bundles and primary != bundles[0].get("file_id")) or (results and primary != results[0].get("file_id")):
        errors.append("primary file role mismatch")
    if ordinals != list(range(1, len(ordinals) + 1)):
        errors.append("part ordinals must be contiguous in presentation order")
    if len(artifacts) > 1 and not ordinals:
        errors.append("multiple outputs require numbered parts")
    if results and len(artifacts) != 1:
        errors.append("standalone result may not share child artifacts")
    if ordinals and not bundles and not (artifacts[0].get("file_id") == primary):
        errors.append("unbundled multi-result primary must be first part")
    return errors


def main():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    errors = validate_repository_contract(registry, schema)
    if errors:
        for message in errors:
            print("T90 artifacts FAIL:", message, file=sys.stderr)
        return 1
    print("T90 artifacts: PASS (90 planning mappings; legacy single PDF/ZIP preserved; manifest schema non-runtime)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
