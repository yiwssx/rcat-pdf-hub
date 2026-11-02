"""Planning-only T90-5 institutional acceptance ledger contract tests."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "t90_rcat_pilot_acceptance", ROOT / "scripts/validate-t90-rcat-pilot-acceptance.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class PilotAcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / "contracts/pdf-tools.v1.json").read_text())
        self.evidence = json.loads((ROOT / "contracts/t90-rcat-pilot-acceptance.v1.json").read_text())

    def test_actual_registry_starts_unverified_without_invented_evidence(self):
        report = module.verify(self.registry, self.evidence)
        self.assertEqual(report["total"], 90)
        self.assertEqual(report["released"], 0)
        self.assertEqual(report["state_counts"]["UNASSESSED"], 90)
        self.assertEqual(len(report["uncertified"]), 90)

    def test_reject_public_release_scope(self):
        self.evidence["scope"] = "anonymous-public"
        with self.assertRaises(ValueError):
            module.verify(self.registry, self.evidence)

    def test_reject_missing_verified_email_gate(self):
        self.evidence["policy"]["require_provider_verified_email"] = False
        with self.assertRaises(ValueError):
            module.verify(self.registry, self.evidence)

    def test_reject_unknown_or_duplicate_tool(self):
        valid = {
            "tool_id": "F09", "state": "IMPLEMENTED",
            "source_commit": "a" * 40,
            "pr": "https://github.com/yiwssx/rcat-pdf-hub/pull/264",
        }
        self.evidence["tool_evidence"] = [valid, valid.copy()]
        with self.assertRaises(ValueError):
            module.verify(self.registry, self.evidence)
        self.evidence["tool_evidence"] = [{**valid, "tool_id": "F99"}]
        with self.assertRaises(ValueError):
            module.verify(self.registry, self.evidence)

    def test_implementation_can_be_recorded_but_not_marked_released(self):
        record = {
            "tool_id": "F09", "state": "IMPLEMENTED",
            "source_commit": "a" * 40,
            "pr": "https://github.com/yiwssx/rcat-pdf-hub/pull/264",
        }
        self.evidence["tool_evidence"] = [record]
        report = module.verify(self.registry, self.evidence)
        self.assertEqual(report["state_counts"]["IMPLEMENTED"], 1)
        self.assertEqual(report["released"], 0)
        self.assertEqual(report["state_counts"]["UNASSESSED"], 89)

    def test_staged_without_real_file_checksums_is_rejected(self):
        self.evidence["tool_evidence"] = [{
            "tool_id": "F09", "state": "STAGED",
            "source_commit": "a" * 40,
            "pr": "https://github.com/yiwssx/rcat-pdf-hub/pull/264",
            "ci_run": "https://github.com/yiwssx/rcat-pdf-hub/actions/runs/1",
        }]
        with self.assertRaises(ValueError):
            module.verify(self.registry, self.evidence)

    def test_release_without_isolation_evidence_and_approval_is_rejected(self):
        self.evidence["tool_evidence"] = [{
            "tool_id": "F09", "state": "RELEASED",
            "source_commit": "a" * 40,
            "pr": "https://github.com/yiwssx/rcat-pdf-hub/pull/264",
            "ci_run": "https://github.com/yiwssx/rcat-pdf-hub/actions/runs/1",
            "source_sha256": "a" * 64, "output_sha256": "b" * 64,
            "pages_or_items_checked": True,
        }]
        with self.assertRaises(ValueError):
            module.verify(self.registry, self.evidence)


if __name__ == "__main__":
    unittest.main()
