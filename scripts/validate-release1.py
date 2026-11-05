#!/usr/bin/env python3
"""Release 1: narrow static scope gate and explicit real-host acceptance barrier.

Source gate only proves that the frozen legacy tool routes still exist. It does
not execute converters or certify a live institutional pilot. Python stdlib only.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/release1-scope.v1.json"
EXPECTED = {
    "ocr": ("ocr",),
    "merge-pdf": ("merge",),
    "split-rotate": ("organize", "split", "rotate"),
    "compress": ("compress",),
    "pdf-to-images": ("pdf-to-images",),
    "images-to-pdf": ("images-to-pdf",),
    "watermark": ("watermark",),
    "page-numbers": ("page-numbers",),
    "office-to-pdf": ("office-to-pdf",),
}
HEX_40 = re.compile(r"[0-9a-f]{40}\Z")
HEX_64 = re.compile(r"[0-9a-f]{64}\Z")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def queue_operations(source: str) -> set[str]:
    module = ast.parse(source)
    groups = {}
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        if name not in {"INTERACTIVE_OPERATIONS", "PDF_OPERATIONS", "HEAVY_OPERATIONS"}:
            continue
        require(isinstance(node.value, ast.Call) and
                isinstance(node.value.func, ast.Name) and
                node.value.func.id == "frozenset" and len(node.value.args) == 1,
                "Legacy processing queues changed shape")
        groups[name] = set(ast.literal_eval(node.value.args[0]))
    require(len(groups) == 3, "Missing legacy queue group")
    return set().union(*groups.values())


def validate_source(contract: dict, catalog: str, queue: str, config: str) -> None:
    require(contract.get("schema_version") == 1, "Unexpected R1 contract version")
    require(contract.get("release") == "RCAT-PDF-HUB-R1", "Wrong release name")
    require(contract.get("lifecycle") == "CODE_FREEZE_CANDIDATE_NOT_DEPLOYED",
            "R1 must never be declared deployed from source metadata")
    policy = contract.get("policy") or {}
    require(all(policy.get(k) is True for k in (
        "feature_expansion_frozen",
        "production_rollout_requires_explicit_approval",
        "independent_live_evidence_required",
    )), "Release safety policy changed")
    entries = contract.get("tools")
    require(isinstance(entries, list) and len(entries) == 9,
            "R1 has exactly nine essential processing tools")
    actual = {}
    for entry in entries:
        require(isinstance(entry, dict), "Invalid R1 tool record")
        slug, ops = entry.get("slug"), entry.get("operations")
        require(slug not in actual and isinstance(ops, list) and bool(ops),
                "Duplicate or invalid R1 tool")
        actual[slug] = tuple(ops)
        require(set(entry.get("acceptance", [])) == {
            "authenticated_upload", "queued_worker_conversion", "real_output_binary",
            "authenticated_download", "owner_isolation", "thai_fidelity",
            "failure_recovery",
        }, "Release cannot drop per-tool acceptance proof")
    require(actual == EXPECTED, "Release 1 scope must stay exactly frozen")
    require(set(contract.get("release_gates", [])) == {
        "google_workspace_authority", "non_rcat_denial", "provider_verified_email",
        "stable_oidc_owner", "secure_cookie", "service_key_and_share_bypass_denial",
        "browser_e2e", "av_and_parser_isolation", "quotas_retention_audit",
        "verified_backup", "rollback_rehearsal", "operator_approval",
    }, "Release cannot drop identity/security/recovery signoff")
    start = catalog.find("export const LEGACY_PDF_TOOLS")
    end = catalog.find("export const PDF_TOOLS")
    require(start >= 0 and end > start, "Legacy catalog boundaries not found")
    legacy = set(re.findall(r'\{\s*id:\s*"([^"]+)"', catalog[start:end]))
    require(set(EXPECTED).issubset(legacy), "An essential legacy tool is missing from Web")
    supported = queue_operations(queue)
    require(set().union(*(set(v) for v in EXPECTED.values())) <= supported,
            "An R1 operation is absent from legacy queue")
    for setting in ("rcat_institutional_only", "oidc_enabled",
                    "to_pdf_tools_enabled", "from_pdf_tools_enabled",
                    "multi_output_artifacts_enabled", "pdf_filler_tools_enabled"):
        require(re.search(r"^\s*" + setting + r": bool = False\s*$",
                          config, re.M) is not None,
                "Unexpected default activation for " + setting)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_pilot_evidence(
    contract: dict, evidence: dict, evidence_dir: Path, expected_sha: str, actual_sha: str
) -> None:
    """Validate traceable, immutable operator artifacts. No fictional auto-PASS."""
    require(bool(HEX_40.fullmatch(expected_sha)), "Expected Git SHA must be exact")
    require(expected_sha == actual_sha, "Candidate differs from inspected local HEAD")
    require(evidence.get("candidate_sha") == expected_sha, "Evidence uses a different SHA")
    require(evidence.get("release") == contract["release"], "Wrong release evidence")
    expected_tools = {t["slug"] for t in contract["tools"]}
    rows = evidence.get("tools")
    require(isinstance(rows, list) and len(rows) == len(expected_tools),
            "One operator evidence record required for every essential tool")
    require({r.get("slug") for r in rows if isinstance(r, dict)} == expected_tools,
            "Incomplete or duplicate tool evidence")
    required_checks = set(contract["tools"][0]["acceptance"])
    for row in rows:
        require(set(row.get("checks", {})) == required_checks,
                "Missing tool checks for " + str(row.get("slug")))
        for gate in required_checks:
            _check_proof(row["checks"][gate], evidence_dir, row["slug"] + "/" + gate)
        for field in ("source_sha256", "output_sha256"):
            require(bool(HEX_64.fullmatch(str(row.get(field, "")))),
                    "Missing genuine binary SHA-256: " + row["slug"] + "/" + field)
    gates = evidence.get("gates", {})
    require(set(gates) == set(contract["release_gates"]), "Missing global release gates")
    for name in contract["release_gates"]:
        _check_proof(gates[name], evidence_dir, name)
    approval = evidence.get("approval", {})
    require(all(isinstance(approval.get(k), str) and approval[k].strip()
                for k in ("approved_by", "approved_at", "cohort", "rollback_owner")),
            "Operator approval and rollback ownership are required")


def _check_proof(proof: object, root: Path, label: str) -> None:
    require(isinstance(proof, dict) and proof.get("result") == "PASS",
            "Missing PASS evidence for " + label)
    relative = proof.get("file")
    checksum = proof.get("sha256")
    require(isinstance(relative, str) and relative and
            not Path(relative).is_absolute() and
            ".." not in Path(relative).parts, "Unsafe evidence path: " + label)
    require(bool(HEX_64.fullmatch(str(checksum))), "Missing proof hash: " + label)
    target = (root / relative).resolve()
    require(target.is_relative_to(root.resolve()) and
            target.is_file() and target.stat().st_size > 0,
            "Missing evidence file: " + label)
    require(_sha256_file(target) == checksum, "Evidence hash mismatch: " + label)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("source", "pilot"), default="source")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--expected-sha")
    args = parser.parse_args()
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    validate_source(
        contract,
        (ROOT / "apps/web/app/components/tool-catalog.ts").read_text(encoding="utf-8"),
        (ROOT / "apps/api/app/queue.py").read_text(encoding="utf-8"),
        (ROOT / "apps/api/app/config.py").read_text(encoding="utf-8"),
    )
    if args.mode == "source":
        print("R1 SOURCE SCOPE: PASS; PILOT/PRODUCTION: NOT CERTIFIED")
        return
    require(args.evidence is not None and args.expected_sha is not None,
            "Pilot gate needs --evidence and --expected-sha")
    actual_sha = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
    ).strip()
    validate_pilot_evidence(
        contract, json.loads(args.evidence.read_text(encoding="utf-8")),
        args.evidence.resolve().parent, args.expected_sha, actual_sha,
    )
    print("R1 EVIDENCE MANIFEST: PASS (operator-attested; separate runtime audit required)")


if __name__ == "__main__":
    main()
