"""Zero-network release DR evidence tests. No production host, Docker or backups."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("proof", ROOT / "scripts/verify-release-dr-evidence.py")
assert spec and spec.loader
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)
SHA = "a" * 40
NOW = datetime(2026, 11, 9, 3, 0, tzinfo=timezone.utc)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.backup = Path(self.dir.name) / "20261109T020000Z"
        self.backup.mkdir()
        data = b"fixture backup manifest"
        (self.backup / "SHA256SUMS").write_bytes(data)
        self.run = {
            "head_sha": SHA,
            "head_branch": "main",
            "conclusion": "success",
            "status": "completed",
            "event": "workflow_dispatch",
            "path": ".github/workflows/isolated-dr.yml",
            "repository": {"full_name": "yiwssx/rcat-pdf-hub"},
        }
        self.report = {
            "schema": 1,
            "workflow": "rcat-isolated-dr",
            "result": "PASS",
            "commit_sha": SHA,
            "backup_stamp": self.backup.name,
            "backup_checksums_sha256": hashlib.sha256(data).hexdigest(),
            "started_utc": (NOW - timedelta(hours=2)).isoformat(),
            "finished_utc": (NOW - timedelta(hours=1)).isoformat(),
            "exit_code": 0,
            "private_logs_uploaded": False,
            "restored_production": False,
        }

    def verify(self):
        proof.verify(self.run, self.report, self.backup, SHA, NOW)

    def test_accepts_matching_main_sha_and_backup(self):
        self.verify()

    def test_rejects_wrong_commit(self):
        self.report["commit_sha"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "proof"):
            self.verify()

    def test_rejects_untrusted_workflow_and_failed_run(self):
        for field, value in [
            ("conclusion", "failure"),
            ("event", "pull_request"),
            ("head_branch", "feature"),
            ("path", ".github/workflows/other.yml"),
        ]:
            with self.subTest(field=field):
                previous = self.run[field]
                self.run[field] = value
                with self.assertRaisesRegex(ValueError, "trusted"):
                    self.verify()
                self.run[field] = previous

    def test_rejects_changed_backup_manifest(self):
        (self.backup / "SHA256SUMS").write_bytes(b"modified")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.verify()

    def test_rejects_old_backup_even_with_recent_dr(self):
        old = self.backup.parent / "20261101T020000Z"
        self.backup.rename(old)
        self.backup = old
        self.report["backup_stamp"] = old.name
        with self.assertRaisesRegex(ValueError, "not recent"):
            self.verify()

    def test_rejects_different_backup_stamp(self):
        self.report["backup_stamp"] = "20261108T020000Z"
        with self.assertRaisesRegex(ValueError, "snapshot"):
            self.verify()

    def test_rejects_stale_or_future_evidence(self):
        for finished in (NOW - timedelta(days=5), NOW + timedelta(hours=2)):
            with self.subTest(finished=finished):
                self.report["finished_utc"] = finished.isoformat()
                with self.assertRaisesRegex(ValueError, "expired"):
                    self.verify()

    def test_rejects_fake_pass_without_restore(self):
        for field, value in [
            ("result", "FAIL"), ("exit_code", 1),
            ("private_logs_uploaded", True), ("restored_production", True)
        ]:
            with self.subTest(field=field):
                previous = self.report[field]
                self.report[field] = value
                with self.assertRaisesRegex(ValueError, "proof"):
                    self.verify()
                self.report[field] = previous


if __name__ == "__main__":
    unittest.main()
