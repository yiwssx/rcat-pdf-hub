"""RCAT one-command Google Workspace .env onboarding regression tests."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "rcat_workspace_setup", ROOT / "scripts/setup-rcat-workspace.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

EXAMPLE_ID = "123456789-abcdefghi123.apps.googleusercontent.com"
EXAMPLE_SECRET = "GOCSPX-example-only-not-real"
SOURCE = (
    "# Preserve original service settings\n"
    "POSTGRES_PASSWORD='original-db-secret'\n"
    "PDFHUB_PUBLIC_BIND_HOST=10.10.1.100\n"
    "PDFHUB_HTTP_PORT=8080\n"
    "PDFHUB_RCAT_INSTITUTIONAL_ONLY=false\n"
    "PDFHUB_OIDC_ENABLED=false\n"
    "PDFHUB_OIDC_CLIENT_ID=\n"
    "PDFHUB_OIDC_CLIENT_SECRET=\n"
)


class WorkspaceSetupTests(unittest.TestCase):
    def test_merge_preserves_other_secrets_bind_and_comments(self):
        values = {**module.POLICY, module.CLIENT_ID: module.quote_dotenv(EXAMPLE_ID),
                  module.CLIENT_SECRET: module.quote_dotenv(EXAMPLE_SECRET)}
        updated = module.merge_settings(SOURCE, values)
        self.assertIn("POSTGRES_PASSWORD='original-db-secret'", updated)
        self.assertIn("PDFHUB_PUBLIC_BIND_HOST=10.10.1.100", updated)
        self.assertIn("PDFHUB_HTTP_PORT=8080", updated)
        self.assertIn("# Preserve original service settings", updated)
        self.assertEqual(module.parse_values(updated)["PDFHUB_RCAT_INSTITUTIONAL_ONLY"], "true")
        self.assertEqual(updated.count("PDFHUB_OIDC_CLIENT_SECRET="), 1)
        self.assertEqual(module.merge_settings(updated, values), updated)

    def test_duplicate_keys_are_collapsed_without_touching_unrelated_entries(self):
        original = SOURCE + "PDFHUB_OIDC_ENABLED=true\nPOSTGRES_PASSWORD=second\n"
        updated = module.merge_settings(original, module.POLICY)
        self.assertEqual(updated.count("PDFHUB_OIDC_ENABLED="), 1)
        self.assertEqual(updated.count("POSTGRES_PASSWORD="), 2)

    def test_missing_google_secret_is_rejected_by_check(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(SOURCE, encoding="utf-8")
            os.chmod(path, 0o600)
            self.assertEqual(module.configure(path, check_only=True), 1)

    def test_secure_write_is_atomic_backup_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(SOURCE, encoding="utf-8")
            # Never create a world-readable credential fixture, even temporarily.
            os.chmod(path, 0o600)
            new_text = module.merge_settings(SOURCE, module.POLICY)
            self.assertTrue(module.write_secure(path, SOURCE, new_text))
            self.assertEqual(path.read_text(), new_text)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            backups = list(Path(directory).glob(".env.backup.*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), SOURCE)
            self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)
            self.assertFalse(module.write_secure(path, new_text, new_text))
            self.assertEqual(len(list(Path(directory).glob(".env.backup.*"))), 1)

    def test_complete_existing_credentials_are_reused_without_prompting(self):
        values = {**module.POLICY, module.CLIENT_ID: module.quote_dotenv(EXAMPLE_ID),
                  module.CLIENT_SECRET: module.quote_dotenv(EXAMPLE_SECRET)}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(module.merge_settings(SOURCE, values), encoding="utf-8")
            os.chmod(path, 0o600)
            with patch.object(module.getpass, "getpass", side_effect=AssertionError("unnecessary prompt")):
                self.assertEqual(module.configure(path), 0)
                self.assertEqual(module.configure(path, check_only=True), 0)

    def test_invalid_client_and_symlink_are_rejected(self):
        self.assertFalse(module.valid_client_id("someone@rcat.ac.th"))
        self.assertFalse(module.valid_client_id("replace-client-id"))
        self.assertFalse(module.valid_secret("<secret>"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            actual = Path(directory) / "actual"
            actual.write_text(SOURCE, encoding="utf-8")
            path.symlink_to(actual)
            self.assertEqual(module.configure(path, check_only=True), 2)

    def test_dollar_in_secret_is_treated_as_literal(self):
        value = module.quote_dotenv("GOCSPX-this$should-not-be-interpolated")
        self.assertEqual(value, "'GOCSPX-this$should-not-be-interpolated'")


if __name__ == "__main__":
    unittest.main()
