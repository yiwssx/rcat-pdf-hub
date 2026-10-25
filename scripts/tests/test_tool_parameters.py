"""T90-0 source-mapped parameters: source parity and negative acceptance."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate-tool-parameters.py"
SPEC = importlib.util.spec_from_file_location("pdf_t90_parameters", SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class OperationParameterContractsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(guard.PARAMETERS.read_text(encoding="utf-8"))
        cls.tools = json.loads(guard.CAPABILITIES.read_text(encoding="utf-8"))
        target = {op["request_model"] for op in cls.doc["operations"].values()} | {"OrganizePage"}
        cls.models = guard.inspect_source_models(guard.SCHEMAS.read_text(encoding="utf-8"), target)
        cls.routes = guard.inspect_routes(guard.ROUTES.read_text(encoding="utf-8"))

    def validate(self, doc=None, tools=None):
        return guard.validate(doc or self.doc, tools or self.tools, self.models, self.routes)

    def test_all_legacy_parameters_match_source(self):
        self.assertEqual([], self.validate())

    def test_90_tools_are_explicitly_mapped_or_pending(self):
        mapping = [t["parameter_contract"] for t in self.tools["tools"]]
        self.assertEqual(90, len(mapping))
        self.assertEqual(26, sum(x["status"] == "legacy_projection" for x in mapping))
        self.assertEqual(64, sum(x["status"] == "pending_design" for x in mapping))
        self.assertTrue(all(not x.get("runtime_enabled", False) for x in self.tools["tools"]))

    def assert_invalid(self, doc, tools, fragment):
        problems = self.validate(doc, tools)
        self.assertTrue(any(fragment in e for e in problems), problems)

    def test_source_model_mismatch_rejected(self):
        doc = copy.deepcopy(self.doc)
        doc["operations"]["watermark"]["request_model"] = "MergeRequest"
        self.assert_invalid(doc, self.tools, "route/model/dispatch binding")

    def test_invalid_or_missing_operation_rejected(self):
        doc = copy.deepcopy(self.doc)
        doc["operations"].pop("ocr")
        self.assert_invalid(doc, self.tools, "exactly 13")

    def test_default_and_bounds_drift_rejected(self):
        doc = copy.deepcopy(self.doc)
        doc["operations"]["images-to-pdf"]["parameters"]["dpi"]["maximum"] = 900
        self.assert_invalid(doc, self.tools, "constraint/default drift")

    def test_type_drift_rejected(self):
        doc = copy.deepcopy(self.doc)
        doc["operations"]["ocr"]["parameters"]["deskew"]["type"] = "string"
        self.assert_invalid(doc, self.tools, "parameter type/required drift")

    def test_unclassified_request_field_rejected(self):
        doc = copy.deepcopy(self.doc)
        doc["operations"]["pdfa"]["ignored_request_fields"] = []
        self.assert_invalid(doc, self.tools, "not exactly classified")

    def test_nested_page_field_drift_rejected(self):
        doc = copy.deepcopy(self.doc)
        doc["operations"]["organize"]["parameters"]["pages"]["items"]["properties"]["page"]["minimum"] = 0
        self.assert_invalid(doc, self.tools, "nested page property drift")

    def test_fake_readiness_claim_rejected(self):
        tools = copy.deepcopy(self.tools)
        pending = next(t for t in tools["tools"] if t["parameter_contract"]["status"] == "pending_design")
        pending["parameter_contract"]["status"] = "legacy_projection"
        self.assert_invalid(self.doc, tools, "inflated parameter readiness")

    def test_arbitrary_operation_reference_rejected(self):
        tools = copy.deepcopy(self.tools)
        tools["tools"][0]["parameter_contract"]["operation_refs"] = ["subprocess"]
        self.assert_invalid(self.doc, tools, "contract reference drift")

    def test_unreviewed_tool_activation_rejected(self):
        tools = copy.deepcopy(self.tools)
        tools["tools"][0]["runtime_enabled"] = True
        self.assert_invalid(self.doc, tools, "enabled without runtime approval")


if __name__ == "__main__":
    unittest.main()
