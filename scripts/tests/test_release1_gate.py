"""R1 source freeze and fail-closed operator evidence contract tests."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "release1", ROOT / "scripts/validate-release1.py"
)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class ReleaseOneGateTest(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((ROOT / "contracts/release1-scope.v1.json").read_text())
        self.catalog = (ROOT / "apps/web/app/components/tool-catalog.ts").read_text()
        self.queue = (ROOT / "apps/api/app/queue.py").read_text()
        self.config = (ROOT / "apps/api/app/config.py").read_text()

    def test_source_gate_passes_for_frozen_nine_real_legacy_operations(self):
        gate.validate_source(self.contract, self.catalog, self.queue, self.config)

    def test_fail_if_scope_expands_or_core_operation_is_removed(self):
        self.contract["tools"].append(dict(self.contract["tools"][0], slug="new-feature"))
        with self.assertRaises(ValueError):
            gate.validate_source(self.contract, self.catalog, self.queue, self.config)

    def test_missing_core_web_card_fails(self):
        altered = self.catalog.replace('id: "ocr"', 'id: "removed-ocr"')
        with self.assertRaises(ValueError):
            gate.validate_source(self.contract, altered, self.queue, self.config)

    def test_missing_worker_queue_operation_fails(self):
        altered = self.queue.replace('"ocr",', '"removed-ocr",', 1)
        with self.assertRaises(ValueError):
            gate.validate_source(self.contract, self.catalog, altered, self.config)

    def test_default_on_experimental_converter_fails(self):
        altered = self.config.replace(
            "from_pdf_tools_enabled: bool = False",
            "from_pdf_tools_enabled: bool = True",
        )
        with self.assertRaises(ValueError):
            gate.validate_source(self.contract, self.catalog, self.queue, altered)

    def test_missing_security_release_gate_fails(self):
        self.contract["release_gates"].remove("non_rcat_denial")
        with self.assertRaises(ValueError):
            gate.validate_source(self.contract, self.catalog, self.queue, self.config)

    def test_pilot_refuses_missing_artifacts_and_false_approval(self):
        with tempfile.TemporaryDirectory() as work:
            proof = {
                "release": self.contract["release"],
                "candidate_sha": "a" * 40,
                "tools": [],
                "gates": {},
                "approval": {"approved_by": "operator"},
            }
            with self.assertRaises(ValueError):
                gate.validate_pilot_evidence(
                    self.contract, proof, Path(work), "a" * 40, "a" * 40
                )

    def test_pilot_refuses_a_different_deployed_commit(self):
        with tempfile.TemporaryDirectory() as work:
            with self.assertRaisesRegex(ValueError, "differs"):
                gate.validate_pilot_evidence(
                    self.contract, {}, Path(work), "a" * 40, "b" * 40
                )

    def test_symlink_or_parent_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as work:
            with self.assertRaises(ValueError):
                gate._check_proof(
                    {"result": "PASS", "file": "../outside",
                     "sha256": "a" * 64}, Path(work), "host-log"
                )

    def test_falsified_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "log.txt"
            path.write_text("genuine log")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                gate._check_proof(
                    {"result": "PASS", "file": "log.txt",
                     "sha256": "a" * 64}, Path(work), "host-log"
                )


if __name__ == "__main__":
    unittest.main()
