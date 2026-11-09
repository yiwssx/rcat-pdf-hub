#!/usr/bin/env python3
"""Validate institutional per-tool evidence; never auto-promote a 90-tool release.

Reads original planning registry and a separate evidence file. Absence of
proof is "UNASSESSED" and never inherited from untested feature code or CI.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "contracts/pdf-tools.v1.json"
EVIDENCE = ROOT / "contracts/t90-rcat-pilot-acceptance.v1.json"

STATES = {"IMPLEMENTED", "STAGED", "VERIFIED", "RELEASED"}
ALLOWED_CATEGORIES = {"manage", "to_pdf", "from_pdf"}
HASH = re.compile(r"[0-9a-f]{64}\Z")
GITHUB = re.compile(r"https://github\.com/[^\s/]+/[^\s/]+/(?:pull|actions/runs)/[0-9]+\Z")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


REPORTS_FOR_VERIFICATION = (
    "source_vs_output_report",
    "security_isolation_report",
    "owner_scope_test_report",
    "thai_fidelity_report",
)
# Never store source documents, student data or bearer secrets in a ledger.
# The report is retained in an approved private RCAT evidence store; its
# opaque reference and digest are safe for the version-controlled ledger.
REPORT_REF = re.compile(r"rcat-evidence:[A-Za-z0-9][A-Za-z0-9._:/-]{7,127}\Z")
UTC_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


def _require_hashed_pass_report(record: dict, name: str) -> None:
    """Require a machine-readable PASS attestation, not arbitrary prose."""
    report = record.get(name)
    _require(isinstance(report, dict), f"{name} requires structured evidence")
    _require(report.get("result") == "PASS",
             f"{name} requires an explicit PASS result")
    digest = report.get("artifact_sha256")
    _require(isinstance(digest, str) and HASH.fullmatch(digest) is not None,
             f"{name} requires evidence artifact SHA-256")
    ref = report.get("evidence_ref")
    _require(isinstance(ref, str) and REPORT_REF.fullmatch(ref) is not None,
             f"{name} requires opaque RCAT evidence reference")
    stamp = report.get("checked_at")
    _require(isinstance(stamp, str) and UTC_STAMP.fullmatch(stamp) is not None,
             f"{name} requires an ISO UTC timestamp")
    try:
        datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(f"{name} has invalid UTC date") from exc


def verify(registry: dict, evidence: dict) -> dict:
    tools = registry.get("tools", [])
    _require(len(tools) == 90, "Pilot requires exactly 90 canonical tools")
    names = [t["id"] for t in tools]
    slugs = [t["slug"] for t in tools]
    _require(len(set(names)) == 90 and len(set(slugs)) == 90,
             "Canonical IDs and slugs must be unique")
    _require(Counter(t["category"] for t in tools)
             == {"manage": 33, "to_pdf": 40, "from_pdf": 17},
             "Pilot category inventory differs from 33/40/17")
    _require(evidence.get("schema_version") == 1, "Unknown pilot evidence schema")
    _require(evidence.get("scope") == "rcat-institutional-oidc-verified-email",
             "Pilot scope may not silently expand to public users")
    policy = evidence.get("policy", {})
    _require(policy.get("institutional_email_domain") == "rcat.ac.th"
             and policy.get("require_provider_verified_email") is True
             and policy.get("no_anonymous_service_release") is True
             and policy.get("each_tool_independently_approved") is True
             and policy.get("oidc_provider_authority_required") is True
             and policy.get("google_workspace_hd_required_for_google_issuer") is True
             and policy.get("stable_oidc_subject_owner_required") is True,
             "Mandatory verified institutional OIDC authority or stable ownership policy missing")
    by_id = {t["id"]: t for t in tools}
    certified: dict[str, dict] = {}
    for record in evidence.get("tool_evidence", []):
        _require(isinstance(record, dict), "Evidence entries must be objects")
        id_ = record.get("tool_id")
        state = record.get("state")
        _require(isinstance(id_, str) and id_ in by_id, "Unknown tool in evidence")
        _require(id_ not in certified, "Duplicate tool evidence")
        _require(state in STATES, "Unknown pilot engineering stage")
        commit = record.get("source_commit")
        pr = record.get("pr")
        _require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit),
                 "Evidence requires exact source commit")
        _require(isinstance(pr, str) and GITHUB.fullmatch(pr),
                 "Evidence requires traceable GitHub PR")
        if by_id[id_]["category"] == "to_pdf":
            _require(isinstance(record.get("supported_subset"), str)
                     and len(record["supported_subset"].strip()) >= 16
                     and isinstance(record.get("acceptance_pending"), str)
                     and len(record["acceptance_pending"].strip()) >= 16,
                     "T90-2 evidence must describe supported subset and unmet acceptance")
        # Green source-level CI alone is never production acceptance. Every
        # higher stage needs explicit positive/negative source-file evidence.
        if state in {"STAGED", "VERIFIED", "RELEASED"}:
            _require(isinstance(record.get("ci_run"), str)
                     and GITHUB.fullmatch(record["ci_run"]),
                     "STAGED requires a concrete CI run")
            _require(isinstance(record.get("source_sha256"), str)
                     and HASH.fullmatch(record["source_sha256"]),
                     "STAGED requires a checksum for tested original source")
            _require(isinstance(record.get("output_sha256"), str)
                     and HASH.fullmatch(record["output_sha256"]),
                     "STAGED requires a checksum for real converted output")
            _require(record.get("pages_or_items_checked") is True,
                     "STAGED requires real output inventory")
        if state in {"VERIFIED", "RELEASED"}:
            for report_name in REPORTS_FOR_VERIFICATION:
                _require_hashed_pass_report(record, report_name)
        if state == "RELEASED":
            _require_hashed_pass_report(record, "institutional_sso_report")
            _require(bool(record.get("approved_by"))
                     and bool(record.get("approved_at"))
                     and bool(record.get("rollback_plan"))
                     and bool(record.get("cohort")),
                     "RELEASED requires institutional approval and rollback")
        certified[id_] = record
    counts = Counter(record["state"] for record in certified.values())
    counts["UNASSESSED"] = 90 - len(certified)
    return {"scope": evidence["scope"], "total": 90,
            "state_counts": dict(sorted(counts.items())),
            "released": counts.get("RELEASED", 0),
            "not_released": 90 - counts.get("RELEASED", 0),
            "uncertified": [x for x in names if x not in certified]}


def main() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    print(json.dumps(verify(registry, evidence), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
