"""Regression tests for T90's planning-only central registry."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate-tool-registry.py"
spec = importlib.util.spec_from_file_location("t90_registry_validation", SCRIPT)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class ToolRegistryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(validator.REGISTRY.read_text(encoding="utf-8"))

    def test_valid_manifest_matches_legacy_sources_and_tracker(self):
        self.assertEqual([], validator.validate(self.data, check_sources=True))

    def test_all_ninety_tools_disabled_and_unique(self):
        self.assertEqual(90, len(self.data["tools"]))
        self.assertEqual(90, len({t["id"] for t in self.data["tools"]}))
        self.assertEqual(90, len({t["slug"] for t in self.data["tools"]}))
        self.assertTrue(all(t["runtime_enabled"] is False for t in self.data["tools"]))

    def assert_invalid(self, document, fragment):
        errors = validator.validate(document, check_sources=False)
        self.assertTrue(any(fragment in e for e in errors), errors)

    def test_duplicate_public_slug_fails(self):
        document = copy.deepcopy(self.data)
        document["tools"][1]["slug"] = document["tools"][0]["slug"]
        self.assert_invalid(document, "duplicate slug")

    def test_duplicate_sequential_id_fails(self):
        document = copy.deepcopy(self.data)
        document["tools"][1]["id"] = document["tools"][0]["id"]
        self.assert_invalid(document, "ID not unique")

    def test_unreviewed_runtime_enablement_fails(self):
        document = copy.deepcopy(self.data)
        document["tools"][0]["runtime_enabled"] = True
        self.assert_invalid(document, "enabled without release")

    def test_fake_legacy_operation_fails(self):
        document = copy.deepcopy(self.data)
        document["tools"][1]["legacy"]["operations"] = ["arbitrary-command"]
        self.assert_invalid(document, "backend operation")

    def test_broken_output_cardinality_fails(self):
        document = copy.deepcopy(self.data)
        document["tools"][0]["planned_contract"]["output"]["cardinality"] = "unknown"
        self.assert_invalid(document, "proposed output")

    def test_invalid_file_count_fails(self):
        document = copy.deepcopy(self.data)
        document["tools"][0]["planned_contract"]["inputs"][0]["min_count"] = -1
        self.assert_invalid(document, "file count")

    def test_category_count_drift_fails(self):
        document = copy.deepcopy(self.data)
        document["tools"][0]["category"] = "to_pdf"
        self.assert_invalid(document, "category counts")

    def test_planned_feature_cannot_claim_legacy_implementation(self):
        document = copy.deepcopy(self.data)
        planned = next(item for item in document["tools"] if item["state"] == "PLANNED")
        planned["legacy"]["operations"] = ["merge"]
        self.assert_invalid(document, "falsely claims")

    def test_nonliteral_queue_or_duplicate_operation_fails(self):
        snippet = (
            "INTERACTIVE_OPERATIONS = frozenset({'merge'})\n"
            "PDF_OPERATIONS = frozenset({'merge'})\n"
            "HEAVY_OPERATIONS = frozenset({'ocr'})\n"
        )
        with self.assertRaisesRegex(ValueError, "overlapping"):
            validator.read_operations(snippet)


if __name__ == "__main__":
    unittest.main()
