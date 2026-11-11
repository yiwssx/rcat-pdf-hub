"""Read-only tests for the one-command production entrypoint.

The suite never contacts GitHub, Docker or the production server and never
creates a real backup. It exercises only safe discovery and selection.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from contextlib import redirect_stderr
from io import StringIO
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("one_command", ROOT / "scripts/one-command-release.py")
assert spec and spec.loader
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class OneCommandTests(unittest.TestCase):
    def container(self, *files: str) -> str:
        labels = {
            "com.docker.compose.project.working_dir": "/opt/rcat-pdf-hub",
            "com.docker.compose.project.config_files": ",".join(
                "/opt/rcat-pdf-hub/" + name for name in files
            ),
        }
        return json.dumps([{"Config": {"Labels": labels}}])

    def test_safe_preflight_error_prints_only_key_names(self):
        source = chr(10).join([
            "R1 HOST PREFLIGHT: BLOCKED; no secrets printed",
            " - insecure_setting:PDFHUB_OIDC_ENABLED",
            " - service_environment_mismatch:worker-heavy:PDFHUB_TO_PDF_TOOLS_ENABLED",
            "PDFHUB_OIDC_CLIENT_SECRET=please-never-print-me",
            " - unsafe_public_base_url",
        ]) + chr(10)
        out = StringIO()
        with redirect_stderr(out):
            release.print_safe_preflight_errors(source)
        result = out.getvalue()
        self.assertIn("insecure_setting:PDFHUB_OIDC_ENABLED", result)
        self.assertIn("service_environment_mismatch:worker-heavy", result)
        self.assertIn("unsafe_public_base_url", result)
        self.assertNotIn("please-never-print-me", result)

    def test_release_reports_safe_host_preflight_diagnostics_on_failure(self):
        failed = subprocess.CompletedProcess(
            ["python3", "scripts/release1-host-preflight.py"], 1, "",
            chr(10).join([
                "R1 HOST PREFLIGHT: BLOCKED; no secrets printed",
                " - missing_or_invalid_secret:PDFHUB_NATIVE_SIDECAR_SHARED_SECRET",
                "SECRET=do-not-log",
            ]) + chr(10),
        )
        stderr = StringIO()
        with patch.object(release.subprocess, "run", return_value=failed), redirect_stderr(stderr):
            with self.assertRaisesRegex(SystemExit, "required step failed"):
                release.call("python3", "scripts/release1-host-preflight.py")
        log = stderr.getvalue()
        self.assertIn("missing_or_invalid_secret:PDFHUB_NATIVE_SIDECAR_SHARED_SECRET", log)
        self.assertNotIn("do-not-log", log)

    def test_full_runtime_preflight_includes_both_profiled_sidecars(self):
        self.assertEqual(
            release.compose_profile_args(True),
            ("--profile", "native-dev", "--profile", "url-import-dev"),
        )

    def test_normal_release_preflight_does_not_enable_optional_sidecars(self):
        self.assertEqual(release.compose_profile_args(False), ())

    def test_detects_existing_prod_compose_not_assumed_mode(self):
        with patch.object(release, "ROOT", Path("/opt/rcat-pdf-hub")):
            with patch.object(release, "call", side_effect=[
                "example-container",
                self.container("docker-compose.yml", "docker-compose.prod.yml"),
            ]):
                self.assertEqual(release.live_compose_mode(), ("prod", False, False))

    def test_detects_nas_without_guessing(self):
        with patch.object(release, "ROOT", Path("/opt/rcat-pdf-hub")):
            with patch.object(release, "call", side_effect=[
                "example-container",
                self.container("docker-compose.yml", "docker-compose.prod.yml",
                               "docker-compose.nas.yml"),
            ]):
                self.assertEqual(release.live_compose_mode(), ("prod-nas", False, False))

    def test_existing_t90_code_overlay_survives_later_production_releases(self):
        with patch.object(release, "ROOT", Path("/opt/rcat-pdf-hub")):
            with patch.object(release, "call", side_effect=[
                "example-container",
                self.container("docker-compose.yml", "docker-compose.prod.yml",
                               "compose.t90-code-first.yaml"),
            ]):
                self.assertEqual(release.live_compose_mode(), ("prod", True, False))

    def test_live_full_runtime_is_not_silently_removed(self):
        with patch.object(release, "ROOT", Path("/opt/rcat-pdf-hub")):
            with patch.object(release, "call", side_effect=[
                "example-container",
                self.container("docker-compose.yml", "docker-compose.prod.yml",
                               "compose.t90-code-first.yaml",
                               "compose.native-sidecar.yaml",
                               "compose.url-fetcher.yaml",
                               "compose.t90-full-runtime.yaml"),
            ]):
                self.assertEqual(release.live_compose_mode(), ("prod", True, True))

    def test_refuses_dev_stack(self):
        with patch.object(release, "ROOT", Path("/opt/rcat-pdf-hub")):
            with patch.object(release, "call", side_effect=[
                "example-container", self.container("docker-compose.yml"),
            ]):
                with self.assertRaisesRegex(SystemExit, "not uniquely"):
                    release.live_compose_mode()

    def test_refuses_no_running_app(self):
        with patch.object(release, "call", return_value=""):
            with self.assertRaisesRegex(SystemExit, "no running Compose API"):
                release.live_compose_mode()

    def test_backup_path_is_not_shell_evaluated(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / ".env").write_text(
                "POSTGRES_PASSWORD=do-not-log\n"
                "PDFHUB_BACKUP_ROOT='./backup-safe'\n"
            )
            with patch.object(release, "ROOT", root):
                self.assertEqual(release.backup_root(), (root / "backup-safe").resolve())

    def test_backup_root_defaults_to_project_backups(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / ".env").write_text("PDFHUB_STORAGE_BACKEND=local\n")
            with patch.object(release, "ROOT", root):
                self.assertEqual(release.backup_root(), root / "backups")


if __name__ == "__main__":
    unittest.main()
