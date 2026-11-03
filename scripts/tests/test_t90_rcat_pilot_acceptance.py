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

    def test_actual_registry_credits_individual_engines_and_T21_staged(self):
        report = module.verify(self.registry, self.evidence)
        self.assertEqual(report["total"], 90)
        self.assertEqual(report["released"], 0)
        self.assertEqual(report["state_counts"]["IMPLEMENTED"], 12)
        self.assertEqual(report["state_counts"]["STAGED"], 1)
        self.assertEqual(report["state_counts"]["UNASSESSED"], 77)
        self.assertEqual(len(report["uncertified"]), 77)
        implemented = {"T09", "T11", "T19", "T20", "T25", "T30", "T33", "T34", "F09", "F16", "F17", "M33"}
        self.assertEqual(
            {item["tool_id"] for item in self.evidence["tool_evidence"]},
            implemented | {"T21"},
        )
        for item in self.evidence["tool_evidence"]:
            self.assertTrue(item["supported_subset"])
            self.assertTrue(item["acceptance_pending"])
            self.assertNotIn(item["state"], {"VERIFIED", "RELEASED"})
            if item["tool_id"] in implemented:
                self.assertEqual(item["state"], "IMPLEMENTED")
                if item["tool_id"] in {"T09", "T20", "T25", "T30", "T33", "T34"}:
                    self.assertEqual(
                        item["source_commit"],
                        "b1ce2f15c9f4273901b1e3034bd685a99177b85d",
                    )
                    self.assertEqual(
                        item["pr"],
                        "https://github.com/yiwssx/rcat-pdf-hub/pull/259",
                    )
        for item_id, commit, pr in (
            ("F09", "ee4a95e2eded5f171d78909920ffdf280280f288", 269),
            ("M33", "6e067f68656aed38749acca401f697d6ba5e171d", 270),
        ):
            item = next(record for record in self.evidence["tool_evidence"]
                        if record["tool_id"] == item_id)
            self.assertEqual(item["state"], "IMPLEMENTED")
            self.assertEqual(item["source_commit"], commit)
            self.assertEqual(
                item["pr"],
                f"https://github.com/yiwssx/rcat-pdf-hub/pull/{pr}",
            )
        for item_id, commit, pr, run in (
            ("F16", "c9d17d92eee9bdb66d76a12c1e6a0198935f613b", 278, 41437263796),
            ("F17", "adbcfd2fb92ba3413bdbd10b20c8b91d63ce12d6", 280, 41438461454),
        ):
            item = next(record for record in self.evidence["tool_evidence"]
                        if record["tool_id"] == item_id)
            self.assertEqual(item["state"], "IMPLEMENTED")
            self.assertEqual(item["source_commit"], commit)
            self.assertEqual(
                item["pr"], f"https://github.com/yiwssx/rcat-pdf-hub/pull/{pr}",
            )
            self.assertEqual(
                item["ci_run"],
                f"https://github.com/yiwssx/rcat-pdf-hub/actions/runs/{run}",
            )
            self.assertIn("RCAT", item["acceptance_pending"])
        publisher = next(x for x in self.evidence["tool_evidence"] if x["tool_id"] == "T21")
        self.assertEqual(publisher["state"], "STAGED")
        self.assertTrue(publisher["pages_or_items_checked"])
        self.assertEqual(len(publisher["source_sha256"]), 64)
        self.assertEqual(len(publisher["output_sha256"]), 64)
        self.assertIn("fdo59355-1.pub", publisher["fixture_provenance"])
        self.assertIn("page 2 visibly blank", publisher["supported_subset"])
        self.assertIn("page 2", publisher["acceptance_pending"])
        self.assertEqual(
            publisher["ci_run"],
            "https://github.com/yiwssx/rcat-pdf-hub/actions/runs/41419587183",
        )

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

    def test_to_pdf_implementation_requires_scoped_capability_and_pending_checks(self):
        proof = {
            "tool_id": "T21", "state": "IMPLEMENTED",
            "source_commit": "2abd02bbc176c8748f3da11acd911a61e5826c3f",
            "pr": "https://github.com/yiwssx/rcat-pdf-hub/pull/249",
        }
        self.evidence["tool_evidence"] = [proof]
        with self.assertRaisesRegex(ValueError, "supported subset"):
            module.verify(self.registry, self.evidence)
        proof["supported_subset"] = "Publisher CFB sample only"
        with self.assertRaisesRegex(ValueError, "supported subset"):
            module.verify(self.registry, self.evidence)
        proof["acceptance_pending"] = "Thai visual tests and independent validation"
        self.assertEqual(
            module.verify(self.registry, self.evidence)["state_counts"]["IMPLEMENTED"], 1
        )

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


    def test_release_policy_requires_google_workspace_authority_and_stable_owner(self):
        for key in (
            "oidc_provider_authority_required",
            "google_workspace_hd_required_for_google_issuer",
            "stable_oidc_subject_owner_required",
        ):
            candidate = json.loads(json.dumps(self.evidence))
            candidate["policy"][key] = False
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.verify(self.registry, candidate)

    def test_release_requires_real_institutional_sso_evidence(self):
        proof = {
            "tool_id": "F09", "state": "RELEASED",
            "source_commit": "a" * 40,
            "pr": "https://github.com/yiwssx/rcat-pdf-hub/pull/264",
            "ci_run": "https://github.com/yiwssx/rcat-pdf-hub/actions/runs/1",
            "source_sha256": "a" * 64, "output_sha256": "b" * 64,
            "pages_or_items_checked": True,
            "source_vs_output_report": "verified source vs output",
            "security_isolation_report": "offline renderer proof",
            "owner_scope_test_report": "user isolation proof",
            "thai_fidelity_report": "Thai quality proof",
            "approved_by": "institution reviewer",
            "approved_at": "2026-11-02",
            "rollback_plan": "rollback staging and flags",
            "cohort": "RCAT staff",
        }
        self.evidence["tool_evidence"] = [proof]
        with self.assertRaisesRegex(ValueError, "SSO"):
            module.verify(self.registry, self.evidence)


if __name__ == "__main__":
    unittest.main()
