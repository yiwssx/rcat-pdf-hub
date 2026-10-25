"""Pure-reference T90 artifact contract tests; never touch production storage."""
import copy
import importlib.util
import json
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("t90_artifacts", ROOT / "scripts/validate-tool-artifacts.py")
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)

JOB_ID = "57a139c1-9737-4de0-b928-8ecbf42cd611"
PDF_ID = "13cfb5e2-a817-4eca-9a6c-55a20fc06f42"
PART1_ID = "fe5e71f1-a842-4671-b16d-20f14e81a20f"
PART2_ID = "73b0c9b6-8167-4fc7-9217-4b6143c4f92c"
ZIP_ID = "9c71cd5f-a834-4805-a44f-e49169b0cce4"
NOW = "2026-10-22T19:00:00+07:00"
EXPIRY = "2026-10-23T19:00:00+07:00"


def artifact(file_id, role, name, mime, ordinal=None):
    row = {
        "file_id": file_id, "role": role, "file_name": name, "content_type": mime,
        "size": 120, "sha256": "a" * 64, "source_system": "rcat-user",
        "expires_at": EXPIRY,
    }
    if ordinal is not None:
        row["ordinal"] = ordinal
    return row


def fixture(items, primary):
    manifest = {
        "schema_version": "1.0.0", "job_id": JOB_ID, "status": "completed",
        "requested_by": "rcat-user", "generated_at": NOW,
        "primary_file_id": primary, "artifacts": items,
    }
    job = {"id": JOB_ID, "status": "completed", "requested_by": "rcat-user", "output_file_id": primary}
    records = {i["file_id"]: {
        key: i[key] for key in ("source_system", "content_type", "size", "sha256", "expires_at")
    } for i in items}
    return manifest, job, records, set(records)


class ArtifactContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(guard.SCHEMA.read_text(encoding="utf-8"))
        cls.registry = json.loads(guard.REGISTRY.read_text(encoding="utf-8"))

    def assert_bad(self, payload, expected):
        errors = guard.validate_manifest(*payload)
        self.assertTrue(any(expected in e for e in errors), errors)

    def test_repo_and_90_tool_delivery_mapping(self):
        self.assertEqual([], guard.validate_repository_contract(self.registry, self.schema))
        current = [x["artifact_contract"]["current_delivery"] for x in self.registry["tools"]]
        self.assertEqual(24, current.count("legacy_pdf"))
        self.assertEqual(2, current.count("legacy_zip"))
        self.assertEqual(64, current.count("none"))

    def test_one_legacy_pdf_result(self):
        self.assertEqual([], guard.validate_manifest(*fixture([
            artifact(PDF_ID, "result", "เอกสารภาษาไทย.pdf", "application/pdf"),
        ], PDF_ID)))

    def test_one_legacy_zip_bundle(self):
        self.assertEqual([], guard.validate_manifest(*fixture([
            artifact(ZIP_ID, "bundle", "pages.zip", "application/zip"),
        ], ZIP_ID)))

    def test_future_multipart_with_zip(self):
        self.assertEqual([], guard.validate_manifest(*fixture([
            artifact(ZIP_ID, "bundle", "all-pages.zip", "application/zip"),
            artifact(PART1_ID, "part", "page-0001.png", "image/png", 1),
            artifact(PART2_ID, "part", "page-0002.png", "image/png", 2),
        ], ZIP_ID)))

    def test_future_multipart_without_zip(self):
        self.assertEqual([], guard.validate_manifest(*fixture([
            artifact(PART1_ID, "part", "page-0001.png", "image/png", 1),
            artifact(PART2_ID, "part", "page-0002.png", "image/png", 2),
        ], PART1_ID)))

    def test_200_raster_parts_plus_zip_bundle_are_valid(self):
        pages = [
            artifact(
                str(uuid.uuid5(uuid.NAMESPACE_DNS, f"t90-page-{i}")),
                "part", f"page-{i:04d}.png", "image/png", i,
            )
            for i in range(1, 201)
        ]
        manifest = fixture([
            artifact(ZIP_ID, "bundle", "pages.zip", "application/zip"), *pages,
        ], ZIP_ID)
        self.assertEqual(201, len(manifest[0]["artifacts"]))
        self.assertEqual([], guard.validate_manifest(*manifest))
        self.assertEqual(201, self.schema["properties"]["artifacts"]["maxItems"])

    def test_201_raster_parts_and_invalid_page_201_rejected(self):
        pages = [
            artifact(
                str(uuid.uuid5(uuid.NAMESPACE_DNS, f"t90-page-{i}")),
                "part", f"page-{i:04d}.png", "image/png", i,
            )
            for i in range(1, 202)
        ]
        self.assert_bad(fixture([
            artifact(ZIP_ID, "bundle", "pages.zip", "application/zip"), *pages,
        ], ZIP_ID), "invalid artifact count")
        self.assert_bad(fixture([
            artifact(ZIP_ID, "bundle", "pages.zip", "application/zip"), pages[-1],
        ], ZIP_ID), "invalid part ordinal")

    def test_reject_cross_user_artifact(self):
        p = list(fixture([artifact(PDF_ID, "result", "a.pdf", "application/pdf")], PDF_ID))
        p[0]["artifacts"][0]["source_system"] = "someone-else"
        self.assert_bad(p, "owner mismatch")

    def test_reject_unlinked_file(self):
        p = list(fixture([artifact(PDF_ID, "result", "a.pdf", "application/pdf")], PDF_ID))
        p[3].clear()
        self.assert_bad(p, "not linked to completed job")

    def test_reject_file_record_tampering(self):
        p = list(fixture([artifact(PDF_ID, "result", "a.pdf", "application/pdf")], PDF_ID))
        p[2][PDF_ID]["sha256"] = "b" * 64
        self.assert_bad(p, "persisted FileRecord mismatch")

    def test_reject_storage_paths_and_url_fields(self):
        p = list(fixture([artifact(PDF_ID, "result", "a.pdf", "application/pdf")], PDF_ID))
        p[0]["artifacts"][0]["stored_name"] = "processed/private.pdf"
        self.assert_bad(p, "unexpected/omitted fields")
        p = list(fixture([artifact(PDF_ID, "result", "a.pdf", "application/pdf")], PDF_ID))
        p[0]["signed_url"] = "https://attacker.example"
        self.assert_bad(p, "manifest shape")

    def test_reject_traversal_and_control_characters(self):
        for name in ("../../secret.pdf", "folder\\secret.pdf", "page\n001.png", ".hidden.pdf", "  page.pdf"):
            p = list(fixture([artifact(PDF_ID, "result", name, "application/pdf")], PDF_ID))
            self.assert_bad(p, "unsafe/duplicate filename")

    def test_reject_duplicate_files_and_display_names(self):
        p = list(fixture([
            artifact(PART1_ID, "part", "Page.PNG", "image/png", 1),
            artifact(PART1_ID, "part", "page.png", "image/png", 2),
        ], PART1_ID))
        self.assert_bad(p, "duplicate file ID")
        self.assert_bad(p, "duplicate filename")

    def test_reject_noncontiguous_parts(self):
        p = list(fixture([
            artifact(PART1_ID, "part", "a.png", "image/png", 1),
            artifact(PART2_ID, "part", "b.png", "image/png", 3),
        ], PART1_ID))
        self.assert_bad(p, "ordinals must be contiguous")

    def test_reject_bundle_with_wrong_media_type(self):
        p = list(fixture([artifact(ZIP_ID, "bundle", "a.zip", "application/pdf")], ZIP_ID))
        self.assert_bad(p, "bundle must be ZIP")

    def test_reject_expired_or_timezone_naive(self):
        p = list(fixture([artifact(PDF_ID, "result", "a.pdf", "application/pdf")], PDF_ID))
        p[0]["artifacts"][0]["expires_at"] = "2026-10-22T18:00:00+07:00"
        self.assert_bad(p, "expired or timezone-naive")
        p = list(fixture([artifact(PDF_ID, "result", "a.pdf", "application/pdf")], PDF_ID))
        p[0]["generated_at"] = "2026-10-22T19:00:00"
        self.assert_bad(p, "generated_at must be timezone-aware")

    def test_reject_noncompleted_job(self):
        p = list(fixture([artifact(PDF_ID, "result", "a.pdf", "application/pdf")], PDF_ID))
        p[1]["status"] = "failed"
        self.assert_bad(p, "not bound to a completed job")

    def test_reject_wrong_primary_output(self):
        p = list(fixture([artifact(PDF_ID, "result", "a.pdf", "application/pdf")], PDF_ID))
        p[0]["primary_file_id"] = PART1_ID
        self.assert_bad(p, "primary file not in artifact collection")

    def test_reject_registry_activating_unimplemented_tool(self):
        d = copy.deepcopy(self.registry)
        d["tools"][0]["runtime_enabled"] = True
        self.assertTrue(any("must not enable tools" in e for e in guard.validate_repository_contract(d, self.schema)))

    def test_reject_dishonest_legacy_delivery(self):
        d = copy.deepcopy(self.registry)
        r = next(t for t in d["tools"] if t["artifact_contract"]["current_delivery"] == "legacy_zip")
        r["artifact_contract"]["current_delivery"] = "legacy_pdf"
        self.assertTrue(any("delivery source/target drift" in e for e in guard.validate_repository_contract(d, self.schema)))


if __name__ == "__main__":
    unittest.main()
