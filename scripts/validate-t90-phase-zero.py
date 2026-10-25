#!/usr/bin/env python3
"""T90-0.16: fail-closed Phase 0 architectural readiness contract.

Standard-library only: inspects source AST/JSON, never imports/runs production
converters or touches databases, Redis, storage or production resources.
This validates engineering readiness to START T90-1, not release readiness.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CATEGORY_COUNTS = {"manage": 33, "to_pdf": 40, "from_pdf": 17}
DEFAULT_DISABLED_FLAGS = {
    "multi_output_artifacts_enabled",
    "artifact_write_journal_enabled",
}
EXPECTED_OFFICE_ZIP_CAPS = {
    "MAX_OFFICE_ZIP_ENTRIES": 2048,
    "MAX_OFFICE_ZIP_ENTRY_BYTES": 64 * 1024 * 1024,
    "MAX_OFFICE_ZIP_UNCOMPRESSED": 256 * 1024 * 1024,
    "MAX_OFFICE_ZIP_EXPANSION": 1000,
}


def parse(path: str) -> ast.Module:
    return ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)


def assigned(module: ast.Module, name: str):
    """Find a top-level static definition (do not evaluate arbitrary Python)."""
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return node.value
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return node.value
    raise ValueError(f"Missing reviewed static declaration: {name}")


def static_strings(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "frozenset" and len(node.args) == 1 and not node.keywords:
        node = node.args[0]
    raw = ast.literal_eval(node)
    if not isinstance(raw, (set, frozenset, tuple, list, dict)):
        raise ValueError("Unexpected static collection type")
    if isinstance(raw, dict):
        raw = raw.keys()
    if not all(isinstance(value, str) and value for value in raw):
        raise ValueError("Non-string operation key")
    return set(raw)


def inspect_phase_zero() -> list[str]:
    errors: list[str] = []
    registry = json.loads((ROOT / "contracts/pdf-tools.v1.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "contracts/pdf-output-manifest.v1.schema.json").read_text(encoding="utf-8"))
    tools = registry.get("tools", [])
    if registry.get("counts") != EXPECTED_CATEGORY_COUNTS or len(tools) != 90:
        errors.append("Expected exactly 90 tools in canonical 33/40/17 registry")
    if registry.get("policy", {}).get("all_new_routes_disabled") is not True:
        errors.append("New tool route activation policy must be disabled")
    if any(tool.get("runtime_enabled") is not False for tool in tools):
        errors.append("A planning-only tool was unexpectedly enabled")
    ids = [tool.get("id") for tool in tools]
    slugs = [tool.get("slug") for tool in tools]
    if len(set(ids)) != 90 or len(set(slugs)) != 90:
        errors.append("90 tool IDs/slugs are not unique")

    declared_ops = set(registry.get("existing", {}).get("backend_operations", []))
    if len(declared_ops) != 13:
        errors.append("Legacy 13-operation registry baseline changed")

    adapters = parse("apps/api/app/operation_adapters.py")
    queue = parse("apps/api/app/queue.py")
    jobs = parse("apps/api/app/routers/jobs.py")
    pdf = parse("apps/api/app/routers/pdf.py")
    types = parse("apps/api/app/filetypes.py")
    worker = parse("apps/api/app/worker_tasks.py")
    config = parse("apps/api/app/config.py")
    schemas = parse("apps/api/app/schemas.py")

    try:
        adapter_ops = static_strings(assigned(adapters, "ADAPTERS"))
        queue_ops = set().union(*[
            static_strings(assigned(queue, name))
            for name in ("INTERACTIVE_OPERATIONS", "PDF_OPERATIONS", "HEAVY_OPERATIONS")
        ])
        scoped_ops = static_strings(assigned(jobs, "OPERATION_SCOPES"))
        pdf_only_ops = static_strings(assigned(pdf, "PDF_INPUT_OPERATIONS"))
    except (ValueError, SyntaxError, TypeError) as exc:
        errors.append(f"Static adapter/queue/API contract cannot be read: {exc}")
    else:
        if not (adapter_ops == queue_ops == scoped_ops == declared_ops):
            errors.append("13-adapter/queue/API-scope/planning legacy set diverged")
        if pdf_only_ops != declared_ops - {"images-to-pdf", "office-to-pdf"}:
            errors.append("PDF-only MIME validation does not cover every PDF adapter")

    try:
        max_artifacts = ast.literal_eval(assigned(schemas, "MAX_JOB_ARTIFACTS"))
        max_items = manifest["properties"]["artifacts"]["maxItems"]
        max_ordinal = manifest["properties"]["artifacts"]["items"]["properties"]["ordinal"]["maximum"]
        if (max_artifacts, max_items, max_ordinal) != (201, 201, 200):
            errors.append("Multi-output ZIP+200 pages contract is inconsistent")
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(f"Output manifest contract missing: {exc}")

    for cap, value in EXPECTED_OFFICE_ZIP_CAPS.items():
        try:
            if ast.literal_eval(assigned(types, cap)) != value:
                errors.append(f"Unsafe or changed Office ZIP bound: {cap}")
        except ValueError:
            errors.append(f"Office ZIP bound is not static: {cap}")

    for node in config.body:
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            settings = {n.target.id: n.value for n in node.body
                        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}
            for flag in DEFAULT_DISABLED_FLAGS:
                if not isinstance(settings.get(flag), ast.Constant) or settings[flag].value is not False:
                    errors.append(f"Feature flag default not false: {flag}")
            break
    else:
        errors.append("Settings model missing")

    process = next((n for n in worker.body if isinstance(n, ast.FunctionDef) and n.name == "process_job"), None)
    if process is None or not any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "execute_operation"
        for n in ast.walk(process)
    ):
        errors.append("Worker is not invoking the reviewed adapter seam")
    # No claimed production acceptance: the release tracker deliberately starts at 0.
    return errors


def main() -> int:
    errors = inspect_phase_zero()
    if errors:
        for item in errors:
            print("T90-0 ARCHITECTURE FAIL:", item, file=sys.stderr)
        return 1
    print("T90-0 architecture: PASS (90 planning-only tools, 13 explicit adapters, fail-closed boundaries; NOT Production signoff)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
