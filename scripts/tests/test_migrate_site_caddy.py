"""Test safe host-specific Caddy preservation without touching Docker or CI."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("site_caddy", ROOT / "scripts/migrate-site-caddy.py")
assert spec and spec.loader
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class SiteCaddyMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "ops/caddy").mkdir(parents=True)
        (self.root / "ops/caddy/Caddyfile").write_text(":80 { respond \"canonical\" }\n")
        (self.root / ".gitignore").write_text(".env\n/.local-config/\n")
        (self.root / ".env").write_text("POSTGRES_PASSWORD=secret-do-not-output\n")
        self.git("init", "-q")
        self.git("config", "user.name", "CI Tester")
        self.git("config", "user.email", "ci@example.invalid")
        self.git("add", ".gitignore", "ops/caddy/Caddyfile")
        self.git("commit", "-qm", "baseline")
        self.original = ":80 { respond \"custom-site\" }\n"
        (self.root / "ops/caddy/Caddyfile").write_text(self.original)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def test_preserves_site_caddy_and_restores_clean_index(self):
        with patch.object(migration, "ROOT", self.root):
            self.assertIn("PASS", migration.migrate())
        site = self.root / ".local-config/caddy/Caddyfile"
        self.assertEqual(site.read_text(), self.original)
        self.assertEqual((self.root / "ops/caddy/Caddyfile").read_text(),
                         ':80 { respond "canonical" }\n')
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual(
            (self.root / ".env").read_text().count("PDFHUB_CADDYFILE_PATH="), 1,
        )
        self.assertIn("POSTGRES_PASSWORD=secret-do-not-output",
                      (self.root / ".env").read_text())
        with patch.object(migration, "ROOT", self.root):
            self.assertIn("clean", migration.migrate())

    def test_refuses_to_discard_other_tracked_changes(self):
        (self.root / ".gitignore").write_text("different\n")
        with patch.object(migration, "ROOT", self.root):
            with self.assertRaisesRegex(ValueError, "only one"):
                migration.migrate()
        self.assertFalse((self.root / ".local-config").exists())

    def test_refuses_existing_different_site_file(self):
        target = self.root / ".local-config/caddy"
        target.mkdir(parents=True)
        (target / "Caddyfile").write_text("do-not-overwrite")
        with patch.object(migration, "ROOT", self.root):
            with self.assertRaisesRegex(ValueError, "exists and differs"):
                migration.migrate()
        self.assertEqual((self.root / "ops/caddy/Caddyfile").read_text(),
                         self.original)

    def test_refuses_unknown_env_override(self):
        with (self.root / ".env").open("a") as stream:
            stream.write("PDFHUB_CADDYFILE_PATH=/etc/prod/reverse-proxy\n")
        with patch.object(migration, "ROOT", self.root):
            with self.assertRaisesRegex(ValueError, "existing PDFHUB"):
                migration.migrate()
        self.assertEqual((self.root / "ops/caddy/Caddyfile").read_text(),
                         self.original)

    def test_refuses_to_discard_staged_site_content(self):
        self.git("add", "ops/caddy/Caddyfile")
        with patch.object(migration, "ROOT", self.root):
            with self.assertRaisesRegex(ValueError, "only one"):
                migration.migrate()
        self.assertEqual((self.root / "ops/caddy/Caddyfile").read_text(),
                         self.original)


if __name__ == "__main__":
    unittest.main()
