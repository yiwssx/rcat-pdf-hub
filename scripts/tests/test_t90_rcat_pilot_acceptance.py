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
        self.assertEqual(report["state_counts"]["IMPLEMENTED"], 40)
        self.assertEqual(report["state_counts"]["STAGED"], 1)
        self.assertEqual(report["state_counts"]["UNASSESSED"], 49)
        self.assertEqual(len(report["uncertified"]), 49)
        implemented = {"T09", "T11", "T19", "T20", "T25", "T30", "T33", "T34", "F02", "F03", "F04", "F05", "F06", "F07", "F08", "F09", "F10", "F12", "F13", "F14", "F16", "F17", "M33", "M14", "M15", "F01", "F11", "M22", "M07", "M08", "M09", "M16", "M18", "M30", "M31", "M13", "M17", "M27", "M11", "M28"}
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
        # Source-level exact-head evidence is never an independent real-host release.
        for item_id, commit, pr, ci_run in (
            ("F02", "a05a674ac0b71a707f98e277260f3c7a1ed2a732", 286, 41593120159),
            ("F06", "a05a674ac0b71a707f98e277260f3c7a1ed2a732", 286, 41593120159),
            ("F07", "031643c0b9d5f503d6067da8044831eae1cbc65c", 287, 41593763974),
            ("F10", "e761c92e16efb8f11286efc8844d786297bd3b2d", 285, 41592473851),
            ("F12", "d2d7009b5768d631f0522847b873ff5dceecec7b", 282, 41589680309),
            ("F13", "26818d1142c4beb53bc12be37b8755b6a938dd50", 283, 41590380462),
            ("F14", "e60ae83359ea1d83fc4478d5513914899b956039", 284, 41591622801),
        ):
            item = next(record for record in self.evidence["tool_evidence"]
                        if record["tool_id"] == item_id)
            self.assertEqual(item["state"], "IMPLEMENTED")
            self.assertEqual(item["source_commit"], commit)
            self.assertEqual(item["pr"], f"https://github.com/yiwssx/rcat-pdf-hub/pull/{pr}")
            self.assertEqual(
                item["ci_run"],
                f"https://github.com/yiwssx/rcat-pdf-hub/actions/runs/{ci_run}",
            )
            self.assertTrue(item["supported_subset"])
            self.assertTrue(item["acceptance_pending"])

        # Independently credited merged tools, never production acceptance.
        for tool_id, source_sha, pr, run in (
            ("F03", "118f8c75d4b21f1956c82dc7ec7a65c2b09e5da1", 291, 41596390837),
            ("F04", "118f8c75d4b21f1956c82dc7ec7a65c2b09e5da1", 291, 41596390837),
            ("F05", "d75d367b939fab1c4cc863f2f4184f27526fc470", 289, 41595483198),
            ("F08", "53dae762937fe3571c67bcefed9ce507d3b61781", 290, 41598057731),
        ):
            evidence = next(x for x in self.evidence["tool_evidence"]
                            if x["tool_id"] == tool_id)
            self.assertEqual(evidence["state"], "IMPLEMENTED")
            self.assertEqual(evidence["source_commit"], source_sha)
            self.assertEqual(evidence["pr"], f"https://github.com/yiwssx/rcat-pdf-hub/pull/{pr}")
            self.assertEqual(
                evidence["ci_run"],
                f"https://github.com/yiwssx/rcat-pdf-hub/actions/runs/{run}",
            )
            self.assertIn("RCAT", evidence["acceptance_pending"])
            self.assertTrue(evidence["supported_subset"])

        # M14/M15 are source-level credits only. No live institutional release.
        for tool_id in ("M14", "M15"):
            evidence = next(x for x in self.evidence["tool_evidence"]
                            if x["tool_id"] == tool_id)
            self.assertEqual(evidence["state"], "IMPLEMENTED")
            self.assertEqual(evidence["source_commit"],
                             "0c20166056978c0b07a6dc7c9932a81930ed6ee2")
            self.assertEqual(evidence["pr"],
                             "https://github.com/yiwssx/rcat-pdf-hub/pull/294")
            self.assertEqual(evidence["ci_run"],
                             "https://github.com/yiwssx/rcat-pdf-hub/actions/runs/41599777959")
            self.assertIn("RCAT", evidence["acceptance_pending"])
            self.assertNotIn(evidence["state"], {"VERIFIED", "RELEASED"})
        # F01/F11 have reviewed source code, not independently certified PDF/A.
        for tool_id in ("F01", "F11"):
            entry = next(x for x in self.evidence["tool_evidence"]
                         if x["tool_id"] == tool_id)
            self.assertEqual(entry["state"], "IMPLEMENTED")
            self.assertEqual(entry["source_commit"],
                             "0b376742ae2cb1dfd9b29b53b20b5b2957c5b075")
            self.assertEqual(entry["pr"],
                             "https://github.com/yiwssx/rcat-pdf-hub/pull/292")
            self.assertEqual(entry["ci_run"],
                             "https://github.com/yiwssx/rcat-pdf-hub/actions/runs/41789621087")
            self.assertIn("RCAT", entry["acceptance_pending"])
            self.assertNotIn(entry["state"], {"VERIFIED", "RELEASED"})

        # M22 is only a bounded ASCII text-overlay implementation, not a
        # certified editor or production/Thai release.
        m22 = next(x for x in self.evidence["tool_evidence"]
                   if x["tool_id"] == "M22")
        self.assertEqual(m22["state"], "IMPLEMENTED")
        self.assertEqual(m22["source_commit"],
                         "2a0600758d6470d6561713fdf28a16c0e518c94f")
        self.assertEqual(m22["pr"],
                         "https://github.com/yiwssx/rcat-pdf-hub/pull/297")
        self.assertEqual(m22["ci_run"],
                         "https://github.com/yiwssx/rcat-pdf-hub/actions/runs/41802848012")
        self.assertIn("ASCII", m22["supported_subset"])
        self.assertIn("RCAT", m22["acceptance_pending"])
        self.assertNotIn(m22["state"], {"VERIFIED", "RELEASED"})


        # Exact reviewed source-head CI proves code integration only; not
        # institutional runtime/Thai fidelity or activation evidence.
        for tool_id, source_sha, pr, ci_run in (
            ("M07", "0651613ef199037f15043d0c2b09d3d295ae7222", 300, 41817899273),
            ("M08", "0945eddfde0c07eff80fb13588ef709d5008cca7", 302, 41826789046),
            ("M09", "2e2aaa7946fcb3c5a5e3eca2f5f918693acab01a", 303, 41957731146),
            ("M16", "2a21eba1ce6a51d686fadca5502af0bbb49d0435", 301, 41819587647),
            ("M18", "c74273e241b6bdaae6bcdabd0565b8edb8435f3b", 304, 41961212961),
            ("M30", "72d0a11ac9fee69524396461e6236713c13d2085", 305, 41963071305),
            ("M31", "a5983b618a5c356c931d6782a865ed3003758a37", 306, 41971960969),
        ):
            entry = next(item for item in self.evidence["tool_evidence"]
                         if item["tool_id"] == tool_id)
            self.assertEqual(entry["state"], "IMPLEMENTED")
            self.assertEqual(entry["source_commit"], source_sha)
            self.assertEqual(entry["pr"],
                             f"https://github.com/yiwssx/rcat-pdf-hub/pull/{pr}")
            self.assertEqual(entry["ci_run"],
                             f"https://github.com/yiwssx/rcat-pdf-hub/actions/runs/{ci_run}")
            self.assertIn("default-off", entry["supported_subset"].lower())
            self.assertIn("RCAT", entry["acceptance_pending"])
            self.assertIn("Google Workspace OIDC", entry["acceptance_pending"])
            for prohibited in ("approved_by", "approved_at", "cohort",
                               "institutional_sso_report", "thai_fidelity_report"):
                self.assertNotIn(prohibited, entry)

        # M13/M17/M27 already shipped bounded code in reviewed PR #235,
        # but had been omitted from the independent evidence ledger.
        for tool_id in ("M13", "M17", "M27"):
            item = next(x for x in self.evidence["tool_evidence"]
                        if x["tool_id"] == tool_id)
            self.assertEqual(item["state"], "IMPLEMENTED")
            self.assertEqual(
                item["source_commit"],
                "329ef359a6177fe73da91e7f31c22c10949bacbe",
            )
            self.assertEqual(
                item["pr"], "https://github.com/yiwssx/rcat-pdf-hub/pull/235"
            )
            self.assertEqual(
                item["ci_run"],
                "https://github.com/yiwssx/rcat-pdf-hub/actions/runs/40710634967",
            )
            self.assertIn("owner", item["supported_subset"].lower())
            self.assertIn("RCAT", item["acceptance_pending"])
            self.assertNotIn(item["state"], {"VERIFIED", "RELEASED"})
            for field in ("thai_fidelity_report", "institutional_sso_report",
                          "approved_by", "approved_at", "cohort"):
                self.assertNotIn(field, item)

        # M11/M28 source code and binary staging tests merged through #236.
        # CropBox is NOT secure redaction; resize may distort aspect ratio.
        for tool_id, distinct_limitation in (
            ("M11", "NOT redaction"), ("M28", "NOT aspect-ratio preserving"),
        ):
            item = next(x for x in self.evidence["tool_evidence"]
                        if x["tool_id"] == tool_id)
            self.assertEqual(item["state"], "IMPLEMENTED")
            self.assertEqual(
                item["source_commit"],
                "7b3d0497ed5c1b1bd32ea7e758f0b229b85daa61",
            )
            self.assertEqual(
                item["pr"], "https://github.com/yiwssx/rcat-pdf-hub/pull/236"
            )
            self.assertEqual(
                item["ci_run"],
                "https://github.com/yiwssx/rcat-pdf-hub/actions/runs/40718249607",
            )
            self.assertIn(distinct_limitation, item["supported_subset"])
            self.assertIn("RCAT", item["acceptance_pending"])
            self.assertNotIn(item["state"], {"VERIFIED", "RELEASED"})
            for forbidden in ("thai_fidelity_report", "institutional_sso_report",
                              "approved_by", "approved_at", "cohort"):
                self.assertNotIn(forbidden, item)

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

    @staticmethod
    def _synthetic_pass_report():
        # Schema fixture only; NOT a claim that physical RCAT QA took place.
        return {
            "result": "PASS",
            "artifact_sha256": "a" * 64,
            "evidence_ref": "rcat-evidence:unit-test-shape-only",
            "checked_at": "2026-11-09T00:00:00Z",
        }

    def test_reject_legacy_truthy_strings_for_verified_reports(self):
        proof = next(x for x in self.evidence["tool_evidence"]
                     if x["tool_id"] == "T21").copy()
        proof["state"] = "VERIFIED"
        for name in module.REPORTS_FOR_VERIFICATION:
            proof[name] = "verified"
        self.evidence["tool_evidence"] = [proof]
        with self.assertRaisesRegex(ValueError, "structured evidence"):
            module.verify(self.registry, self.evidence)

    def test_verified_requires_explicit_pass_digest_reference_and_date(self):
        original = next(x for x in self.evidence["tool_evidence"]
                        if x["tool_id"] == "T21").copy()
        original["state"] = "VERIFIED"
        for name in module.REPORTS_FOR_VERIFICATION:
            original[name] = self._synthetic_pass_report()
        self.evidence["tool_evidence"] = [original]
        # This only validates the format of a synthetic test fixture, not
        # whether a real institution-side report exists in the private store.
        self.assertEqual(
            module.verify(self.registry, self.evidence)["released"], 0
        )
        for key, bad_value in (
            ("result", "PENDING"),
            ("artifact_sha256", "not-an-actual-sha256"),
            ("evidence_ref", "https://example.com/arbitrary-string"),
            ("checked_at", "2026-02-31T00:00:00Z"),
        ):
            with self.subTest(key=key):
                report = original["thai_fidelity_report"].copy()
                original["thai_fidelity_report"] = {**report, key: bad_value}
                with self.assertRaises(ValueError):
                    module.verify(self.registry, self.evidence)
                original["thai_fidelity_report"] = report

    def test_release_requires_real_institutional_sso_evidence(self):
        proof = {
            "tool_id": "F09", "state": "RELEASED",
            "source_commit": "a" * 40,
            "pr": "https://github.com/yiwssx/rcat-pdf-hub/pull/264",
            "ci_run": "https://github.com/yiwssx/rcat-pdf-hub/actions/runs/1",
            "source_sha256": "a" * 64, "output_sha256": "b" * 64,
            "pages_or_items_checked": True,
            "source_vs_output_report": self._synthetic_pass_report(),
            "security_isolation_report": self._synthetic_pass_report(),
            "owner_scope_test_report": self._synthetic_pass_report(),
            "thai_fidelity_report": self._synthetic_pass_report(),
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
