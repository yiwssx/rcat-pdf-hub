#!/usr/bin/env python3
"""Offline T90-2 fixture checksum audit; NOT a PDF rendering/release certification.

Run only against trusted, rights-cleared fixture copies in a confined workspace.
No external network, archive extraction, interpreter/shell or native PDF renderer.
Outputs a provenance report; this script cannot modify T90-5 states.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

MAX_CASES = 50
MAX_FILE_BYTES = 64 * 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
CASE_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}\Z")
ROOT = Path(__file__).resolve().parents[1]


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _read_hash(path: Path) -> str:
    size = path.stat().st_size
    _ensure(0 < size <= MAX_FILE_BYTES, "Fixture size exceeds 64 MiB limit")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    _ensure(path.stat().st_size == size, "Fixture size changed while reading")
    return digest.hexdigest()


def _trusted_file(root: Path, relative: object) -> Path:
    _ensure(isinstance(relative, str) and 0 < len(relative) <= 240,
            "Fixture path must be a nonempty short string")
    candidate = Path(relative)
    _ensure(not candidate.is_absolute() and ".." not in candidate.parts
            and "." not in candidate.parts and "\\" not in relative,
            "Absolute, parent and platform-alternate paths are forbidden")
    root = root.resolve(strict=True)
    # Reject any symlink on the entire relative path, even if it resolves
    # back inside the root. This guards accidental reads of private files.
    current = root
    for part in candidate.parts:
        _ensure(part not in {"", "/", "."}, "Invalid fixture path component")
        current = current / part
        _ensure(not current.is_symlink(), "Fixture symlink is forbidden")
    resolved = current.resolve(strict=True)
    _ensure(resolved.is_relative_to(root) and resolved.is_file(),
            "Fixture must be a regular file inside the fixture root")
    return resolved


def _check_pdf_envelope(pdf: Path) -> None:
    # This is intentionally just a cheap format/sanity check, not a parser.
    # PDF syntax, page inventory and visible layout require isolated QA.
    with pdf.open("rb") as stream:
        prefix = stream.read(1024)
        stream.seek(max(0, pdf.stat().st_size - 4096))
        suffix = stream.read(4096)
    _ensure(prefix.startswith(b"%PDF-"), "Output lacks a PDF header")
    _ensure(b"%%EOF" in suffix, "Output lacks a PDF EOF marker")


def audit_fixture_manifest(manifest: dict, fixture_root: Path, registry: dict) -> dict:
    _ensure(isinstance(manifest, dict) and manifest.get("schema_version") == 1,
            "Unsupported fixture manifest version")
    ids = {tool["id"] for tool in registry.get("tools", [])
           if tool.get("category") == "to_pdf"}
    _ensure(len(ids) == 40, "Canonical 40 to-PDF tools are missing")
    tool_id = manifest.get("tool_id")
    _ensure(isinstance(tool_id, str) and tool_id in ids,
            "Fixture audit accepts canonical T90-2 tool IDs only")
    samples = manifest.get("cases")
    _ensure(isinstance(samples, list) and 1 <= len(samples) <= MAX_CASES,
            "Expected 1..50 independent fixture cases")
    results = []
    unique_ids: set[str] = set()
    for case in samples:
        _ensure(isinstance(case, dict), "Each fixture case must be an object")
        case_id = case.get("case_id")
        _ensure(isinstance(case_id, str) and CASE_ID.fullmatch(case_id),
                "Invalid fixture case identifier")
        _ensure(case_id not in unique_ids, "Duplicate fixture case identifier")
        unique_ids.add(case_id)
        src = _trusted_file(fixture_root, case.get("source"))
        out = _trusted_file(fixture_root, case.get("output"))
        _ensure(src != out, "Source and output must be distinct files")
        _ensure(out.suffix.casefold() == ".pdf", "Output must use .pdf extension")
        for name in ("source_sha256", "output_sha256"):
            value = case.get(name)
            _ensure(isinstance(value, str) and SHA256.fullmatch(value),
                    f"Missing or invalid {name}")
        original_sha = _read_hash(src)
        produced_sha = _read_hash(out)
        _ensure(original_sha == case["source_sha256"],
                f"Source SHA-256 mismatch for case {case_id}")
        _ensure(produced_sha == case["output_sha256"],
                f"Output SHA-256 mismatch for case {case_id}")
        _check_pdf_envelope(out)
        # Re-read both after the format check; reject mid-check modification.
        _ensure(_read_hash(src) == original_sha and _read_hash(out) == produced_sha,
                f"Fixture changed during case {case_id}")
        results.append({
            "case_id": case_id,
            "source_sha256": original_sha,
            "output_sha256": produced_sha,
            "source_bytes": src.stat().st_size,
            "output_bytes": out.stat().st_size,
            "pdf_header_eof_checked": True,
            "page_count_checked": False,
            "visual_fidelity_checked": False,
            "security_isolation_checked": False,
            "owner_scope_checked": False,
        })
    return {
        "tool_id": tool_id,
        "result": "PROVENANCE_ONLY",
        "cases_checked": len(results),
        "cases": results,
        "t90_5_state_transition": False,
        "note": "Hashes and PDF envelope only. Does not certify page count, "
                "real rendering, Thai glyphs, isolation, ownership or release.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path,
                        help="JSON fixture manifest outside the tracked repository")
    parser.add_argument("--fixtures-root", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=ROOT / "contracts/pdf-tools.v1.json")
    args = parser.parse_args(argv)
    try:
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        outcome = audit_fixture_manifest(manifest, args.fixtures_root, registry)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
