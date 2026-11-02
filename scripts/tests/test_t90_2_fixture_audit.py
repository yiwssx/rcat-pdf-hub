"""Pure-stdlib tests for the T90-2 offline sample-integrity audit.

Fixtures are generated in a temporary directory. A passing test does not
assert that the generated PDF is visually valid or the actual converter works.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "t90_2_fixture_audit", ROOT / "scripts/t90_2_fixture_audit.py",
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FixtureAuditTest(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="t90-2-provenance-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = b"test-src\x00not-a-real-heic"
        self.output = b"%PDF-1.7\n%synthetic envelope only\n%%EOF\n"
        (self.root / "sample.heic").write_bytes(self.source)
        (self.root / "result.pdf").write_bytes(self.output)
        self.registry = {
            "tools": [
                {"id": f"T{i:02d}", "category": "to_pdf"}
                for i in range(1, 41)
            ]
        }
        self.manifest = {
            "schema_version": 1, "tool_id": "T09",
            "cases": [{
                "case_id": "test-case",
                "source": "sample.heic",
                "output": "result.pdf",
                "source_sha256": sha(self.source),
                "output_sha256": sha(self.output),
            }],
        }

    def _run(self, manifest=None):
        return audit.audit_fixture_manifest(
            manifest if manifest is not None else self.manifest,
            self.root, self.registry,
        )

    def test_success_only_proves_hashes_not_release(self):
        report = self._run()
        self.assertEqual(report["result"], "PROVENANCE_ONLY")
        self.assertEqual(report["cases_checked"], 1)
        self.assertEqual(report["cases"][0]["source_sha256"], sha(self.source))
        self.assertFalse(report["cases"][0]["page_count_checked"])
        self.assertFalse(report["cases"][0]["visual_fidelity_checked"])
        self.assertFalse(report["t90_5_state_transition"])

    def test_reject_sha256_and_source_tampering(self):
        candidate = copy.deepcopy(self.manifest)
        candidate["cases"][0]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Source SHA-256 mismatch"):
            self._run(candidate)
        (self.root / "result.pdf").write_bytes(self.output + b"altered")
        with self.assertRaisesRegex(ValueError, "Output SHA-256 mismatch"):
            self._run()

    def test_reject_pdf_with_valid_hash_but_invalid_envelope(self):
        missing_pdf = b"not actually a pdf"
        (self.root / "result.pdf").write_bytes(missing_pdf)
        candidate = copy.deepcopy(self.manifest)
        candidate["cases"][0]["output_sha256"] = sha(missing_pdf)
        with self.assertRaisesRegex(ValueError, "PDF header"):
            self._run(candidate)

    def test_reject_absolute_escape_and_same_source_output(self):
        for path in ("/etc/passwd", "../outside", "foo\\bar"):
            candidate = copy.deepcopy(self.manifest)
            candidate["cases"][0]["source"] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                self._run(candidate)
        candidate = copy.deepcopy(self.manifest)
        candidate["cases"][0]["output"] = "sample.heic"
        with self.assertRaises(ValueError):
            self._run(candidate)

    def test_reject_symlinks_even_when_target_inside_root(self):
        link = self.root / "sym-result.pdf"
        link.symlink_to(self.root / "result.pdf")
        candidate = copy.deepcopy(self.manifest)
        candidate["cases"][0]["output"] = "sym-result.pdf"
        with self.assertRaisesRegex(ValueError, "symlink"):
            self._run(candidate)

    def test_reject_unknown_tools_duplicate_cases_and_oversized_files(self):
        candidate = copy.deepcopy(self.manifest)
        candidate["tool_id"] = "M33"
        with self.assertRaisesRegex(ValueError, "T90-2"):
            self._run(candidate)
        candidate = copy.deepcopy(self.manifest)
        candidate["cases"].append(copy.deepcopy(candidate["cases"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self._run(candidate)
        candidate = copy.deepcopy(self.manifest)
        candidate["cases"][0]["case_id"] = "bad case"
        with self.assertRaisesRegex(ValueError, "identifier"):
            self._run(candidate)
        candidate = copy.deepcopy(self.manifest)
        candidate["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "version"):
            self._run(candidate)

    def test_manifest_root_requires_full_canonical_40(self):
        self.registry["tools"].pop()
        with self.assertRaisesRegex(ValueError, "40"):
            self._run()

    def test_cli_writes_no_t90_5_approvals(self):
        manifest_file = self.root / "evidence-manifest.json"
        manifest_file.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.assertEqual(
            audit.main([
                str(manifest_file), "--fixtures-root", str(self.root),
                "--registry", str(ROOT / "contracts/pdf-tools.v1.json"),
            ]), 0,
        )


if __name__ == "__main__":
    unittest.main()
