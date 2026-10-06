#!/usr/bin/env python3
import ast
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
APP_ROOT = API_ROOT / "app"
BASELINE = ROOT / "quality" / "backend-coverage-baseline.json"
ARTIFACT = Path(os.environ.get("PDFHUB_COVERAGE_ARTIFACT", str(ROOT / "artifacts" / "quality" / "backend-coverage.json")))


def executable_lines(path: Path) -> set[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt):
            continue
        if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), (ast.Str, ast.Constant)):
            value = getattr(node.value, "value", None)
            if isinstance(value, str):
                continue
        lines.add(node.lineno)
    return lines


sources = {
    path.resolve(): executable_lines(path)
    for path in sorted(APP_ROOT.rglob("*.py"))
    if path.name != "__init__.py"
}
covered: dict[Path, set[int]] = {path: set() for path in sources}


def trace(frame, event, arg):
    if event == "line":
        filename = Path(frame.f_code.co_filename).resolve()
        if filename in covered:
            covered[filename].add(frame.f_lineno)
    return trace


os.chdir(API_ROOT)
sys.path.insert(0, str(API_ROOT))
import pytest  # noqa: E402

sys.settrace(trace)
try:
    exit_code = pytest.main(["-q"])
finally:
    sys.settrace(None)

if exit_code != 0:
    raise SystemExit(exit_code)

files = []
total_statements = 0
total_covered = 0
for path, statements in sources.items():
    hit = statements & covered[path]
    total_statements += len(statements)
    total_covered += len(hit)
    files.append(
        {
            "path": path.relative_to(ROOT).as_posix(),
            "statements": len(statements),
            "covered": len(hit),
            "percent": round((100.0 * len(hit) / len(statements)) if statements else 100.0, 2),
        }
    )

percent = round((100.0 * total_covered / total_statements) if total_statements else 100.0, 2)
report = {
    "metric": "python-statement-line-execution",
    "scope": "apps/api/app/**/*.py excluding __init__.py",
    "statements": total_statements,
    "covered": total_covered,
    "percent": percent,
    "files": files,
}
ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
ARTIFACT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
minimum = float(baseline["minimum_percent"])
accepted = float(baseline["measured_percent"])
print(f"backend coverage: {percent:.2f}% ({total_covered}/{total_statements})")
print(f"accepted baseline: {accepted:.2f}% | enforced floor: {minimum:.2f}%")
try:
    artifact_label = ARTIFACT.relative_to(ROOT)
except ValueError:
    artifact_label = ARTIFACT
print(f"coverage artifact: {artifact_label}")
if percent + 1e-9 < minimum:
    raise SystemExit(
        f"Backend coverage regression: {percent:.2f}% is below the accepted floor {minimum:.2f}%"
    )
print("backend coverage gate: PASS")
