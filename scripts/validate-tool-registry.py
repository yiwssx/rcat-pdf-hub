#!/usr/bin/env python3
"""T90 central registry contract guard; validation only, never enables new tools."""
import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COUNTS = {"manage": 33, "to_pdf": 40, "from_pdf": 17}
PREFIXES = {"manage": "M", "to_pdf": "T", "from_pdf": "F"}
STATES = {"PLANNED", "PARTIAL", "BASELINE", "IMPLEMENTED", "VERIFIED", "RELEASED"}
REGISTRY = ROOT / "contracts/pdf-tools.v1.json"
TRACKER = ROOT / "docs/workstreams/pdf-90-tools-master-tracker.md"
WEB = ROOT / "apps/web/app/components/tool-catalog.ts"
QUEUE = ROOT / "apps/api/app/queue.py"
ROW = re.compile(
    r"^\| (M\d\d|T\d\d|F\d\d) \| \*\*([^*]+)\*\* "
    r"\x60([^\x60]+)\x60 \| \x60([^\x60]+)\x60 \| (P\d) \| ([^|]+) \| ([^|]+) \|$",
    re.MULTILINE,
)
SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
MIME = re.compile(r"^[a-z][a-z0-9.+-]*/(?:[a-z0-9.+-]+|\*)$")


def read_operations(source):
    tree = ast.parse(source)
    required = {"INTERACTIVE_OPERATIONS", "PDF_OPERATIONS", "HEAVY_OPERATIONS"}
    result, seen = set(), set()
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign):
            continue
        names = {t.id for t in stmt.targets if isinstance(t, ast.Name)}
        if not (names & required):
            continue
        if not isinstance(stmt.value, ast.Call) or not isinstance(stmt.value.func, ast.Name) or stmt.value.func.id != "frozenset" or len(stmt.value.args) != 1:
            raise ValueError("nonliteral queue definition")
        values = ast.literal_eval(stmt.value.args[0])
        if not isinstance(values, set) or any(not isinstance(v, str) for v in values) or (result & values):
            raise ValueError("overlapping or invalid operations")
        result.update(values)
        seen.update(names & required)
    if seen != required:
        raise ValueError("missing queue classes")
    return result


def validate(data, check_sources=True):
    """Return a list of errors, keeping all runtime functionality unchanged."""
    errors = []
    def fail(message):
        errors.append(message)

    if not isinstance(data, dict) or data.get("schema_version") != "1.0.0":
        return ["unsupported registry schema"]
    if data.get("status") != "planning-only" or data.get("counts") != COUNTS:
        fail("planning status or 33/40/17 target invalid")
    policy = data.get("policy", {})
    if not isinstance(policy, dict) or not all(policy.get(k) is True for k in (
        "release_requires_manual_acceptance", "all_new_routes_disabled", "legacy_catalog_unchanged"
    )):
        fail("unsafe planning/release policy")
    baseline = data.get("existing", {})
    if not isinstance(baseline, dict):
        return errors + ["invalid existing baseline"]
    ui, ops = baseline.get("ui_routes"), baseline.get("backend_operations")
    if not isinstance(ui, list) or len(ui) != 13 or len(set(ui)) != 13:
        fail("expected exactly 13 legacy Web routes")
        ui = []
    if not isinstance(ops, list) or len(ops) != 13 or len(set(ops)) != 13:
        fail("expected exactly 13 legacy operations")
        ops = []
    tools = data.get("tools")
    if not isinstance(tools, list) or len(tools) != 90:
        return errors + ["expected exactly 90 definitions"]
    by_id, slugs, counts = {}, set(), Counter()
    for n, item in enumerate(tools, 1):
        p = f"entry {n}"
        if not isinstance(item, dict):
            fail(f"{p}: not an object")
            continue
        cat, key, slug = item.get("category"), item.get("id"), item.get("slug")
        if cat not in COUNTS:
            fail(f"{p}: unknown category")
            continue
        counts[cat] += 1
        if key != f"{PREFIXES[cat]}{counts[cat]:02d}" or key in by_id:
            fail(f"{p}: ID not unique/sequential")
        by_id[key] = item
        if not isinstance(slug, str) or not SLUG.fullmatch(slug) or slug in slugs:
            fail(f"{p}: invalid/duplicate slug")
        else:
            slugs.add(slug)
        for field in ("title", "adapter_proposal", "acceptance"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                fail(f"{p}: missing {field}")
        if item.get("state") not in STATES or item.get("priority") not in {"P0", "P1", "P2", "P3"}:
            fail(f"{p}: invalid state/priority")
        if item.get("runtime_enabled") is not False:
            fail(f"{p}: planned feature enabled without release gate")
        mapping = item.get("legacy")
        if not isinstance(mapping, dict):
            fail(f"{p}: no legacy mapping")
            continue
        routes, operations = mapping.get("ui_routes"), mapping.get("operations")
        if not isinstance(routes, list) or any(s not in ui for s in routes):
            fail(f"{p}: undeclared existing UI route")
        if not isinstance(operations, list) or any(s not in ops for s in operations):
            fail(f"{p}: undeclared existing backend operation")
        if item.get("state") == "PLANNED" and (routes or operations):
            fail(f"{p}: planned tool falsely claims implementation")
        contract = item.get("planned_contract", {})
        ins = contract.get("inputs") if isinstance(contract, dict) else None
        output = contract.get("output") if isinstance(contract, dict) else None
        if not isinstance(ins, list) or len(ins) < 1:
            fail(f"{p}: missing proposed inputs")
        else:
            for v in ins:
                if not isinstance(v, dict):
                    fail(f"{p}: invalid input type")
                    continue
                lo, hi, mime = v.get("min_count"), v.get("max_count"), v.get("mime")
                if type(lo) is not int or lo < 1 or (hi is not None and (type(hi) is not int or hi < lo)):
                    fail(f"{p}: invalid file count bounds")
                if not isinstance(mime, str) or not MIME.fullmatch(mime):
                    fail(f"{p}: invalid input MIME")
        if not isinstance(output, dict) or output.get("cardinality") not in {"single", "multi", "special"} or not isinstance(output.get("mime"), str) or not MIME.fullmatch(output["mime"]):
            fail(f"{p}: invalid proposed output")
        if not isinstance(contract, dict) or contract.get("workload_hint") not in {"interactive", "pdf", "heavy"} or type(contract.get("security_review")) is not bool:
            fail(f"{p}: invalid workload or security indicator")
    if dict(counts) != COUNTS:
        fail("category counts drift")
    if check_sources:
        if re.findall(r'\{\s*id:\s*"([a-z0-9-]+)"', WEB.read_text(encoding="utf-8")) != ui:
            fail("legacy Web catalog drift")
        if read_operations(QUEUE.read_text(encoding="utf-8")) != set(ops):
            fail("legacy backend operations drift")
        rows = list(ROW.finditer(TRACKER.read_text(encoding="utf-8")))
        if len(rows) != 90:
            fail("tracker no longer contains 90 rows")
        for match in rows:
            row = by_id.get(match[1])
            if not row or any(row.get(k) != v for k, v in (
                ("title", match[2]), ("slug", match[3]), ("state", match[4]),
                ("priority", match[5]), ("adapter_proposal", match[6].strip()),
                ("acceptance", match[7].strip())
            )):
                fail(f"tracker drift: {match[1]}")
    return errors


def main():
    issues = validate(json.loads(REGISTRY.read_text(encoding="utf-8")))
    if issues:
        for issue in issues:
            print("T90 FAIL:", issue, file=sys.stderr)
        return 1
    print("T90: PASS (90 definitions: 33 manage / 40 to-PDF / 17 from-PDF; legacy unchanged; all new tools disabled)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
