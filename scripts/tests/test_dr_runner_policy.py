"""Stdlib-only DR runner safety tests; never start Docker or touch backup data."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("dr_runner_policy", ROOT / "scripts/dr-runner-policy.py")
assert spec and spec.loader
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
SHA = "a" * 40


class DRRunnerPolicyTests(unittest.TestCase):
    def valid_env(self):
        return {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "yiwssx/rcat-pdf-hub",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "schedule",
            "RUNNER_ENVIRONMENT": "self-hosted",
            "GITHUB_SHA": SHA,
        }

    def test_accepts_only_protected_main_on_self_hosted(self):
        with tempfile.TemporaryDirectory() as t, patch.object(policy.os, "getuid", return_value=1001), patch.object(policy.Path, "cwd", return_value=Path(t)):
            policy.require_context(self.valid_env())
            for key, value in (
                ("GITHUB_EVENT_NAME", "pull_request"),
                ("GITHUB_REF", "refs/pull/23/merge"),
                ("RUNNER_ENVIRONMENT", "github-hosted"),
                ("GITHUB_REPOSITORY", "outside/other"),
                ("GITHUB_SHA", "not-a-commit"),
            ):
                bad = self.valid_env()
                bad[key] = value
                with self.subTest(key=key), self.assertRaises(ValueError):
                    policy.require_context(bad)

    def test_refuses_root_user_and_deployment_env(self):
        with tempfile.TemporaryDirectory() as t:
            with patch.object(policy.Path, "cwd", return_value=Path(t)):
                with patch.object(policy.os, "getuid", return_value=0):
                    with self.assertRaises(ValueError):
                        policy.require_context(self.valid_env())
                (Path(t) / ".env").write_text("DO_NOT_READ=1")
                with patch.object(policy.os, "getuid", return_value=1001):
                    with self.assertRaises(ValueError):
                        policy.require_context(self.valid_env())

    def test_only_latest_direct_backup_with_checksums(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for stamp in ("20261108T120000Z", "20261109T030000Z"):
                snapshot = root / stamp
                snapshot.mkdir()
                for name in ("manifest.env", "SHA256SUMS", "postgres.dump"):
                    (snapshot / name).write_bytes(b"fixture")
            (root / "bad").mkdir()
            (root / "20261110T000000Z").symlink_to(root / "20261108T120000Z", target_is_directory=True)
            with patch.object(policy, "EXPECTED_BACKUP_ROOT", root), patch.object(
                policy.os, "statvfs", return_value=types.SimpleNamespace(f_flag=os.ST_RDONLY)
            ):
                self.assertEqual(policy.choose_snapshot(root).name, "20261109T030000Z")

    def test_requires_read_only_backup_mount(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            with patch.object(policy, "EXPECTED_BACKUP_ROOT", root), patch.object(
                policy.os, "statvfs", return_value=types.SimpleNamespace(f_flag=0)
            ):
                with self.assertRaisesRegex(ValueError, "read-only"):
                    policy.choose_snapshot(root)

    def test_requires_rootless_docker_and_empty_daemon(self):
        good_info = types.SimpleNamespace(stdout='["name=seccomp","name=rootless"]', returncode=0)
        empty = types.SimpleNamespace(stdout="", returncode=0)
        with patch.object(policy.os, "getuid", return_value=1001), patch.dict(
            policy.os.environ, {"DOCKER_HOST": "unix:///run/user/1001/docker.sock"}
        ):
            with patch.object(policy.subprocess, "run", side_effect=[good_info, empty, empty]) as run:
                policy.require_rootless_empty_docker()
                self.assertEqual(run.call_args_list[1].args[0], ["docker", "ps", "-aq"])
                self.assertEqual(run.call_args_list[2].args[0], ["docker", "volume", "ls", "-q"])
            rootful = types.SimpleNamespace(stdout='["name=seccomp"]', returncode=0)
            with patch.object(policy.subprocess, "run", return_value=rootful):
                with self.assertRaisesRegex(ValueError, "rootless"):
                    policy.require_rootless_empty_docker()
            stopped = types.SimpleNamespace(stdout="stopped-container-id\\n", returncode=0)
            with patch.object(policy.subprocess, "run", side_effect=[good_info, stopped]):
                with self.assertRaisesRegex(ValueError, "containers"):
                    policy.require_rootless_empty_docker()
            volumes = types.SimpleNamespace(stdout="other-workload-data\\n", returncode=0)
            with patch.object(policy.subprocess, "run", side_effect=[good_info, empty, volumes]):
                with self.assertRaisesRegex(ValueError, "named volumes"):
                    policy.require_rootless_empty_docker()
            with patch.dict(policy.os.environ, {"DOCKER_HOST": "unix:///var/run/docker.sock"}):
                with self.assertRaisesRegex(ValueError, "rootless Docker socket"):
                    policy.require_rootless_empty_docker()

    def test_report_contains_no_backup_paths_or_private_logs(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            snap = root / "20261109T030000Z"
            snap.mkdir()
            (snap / "SHA256SUMS").write_bytes(b"fixture")
            out = root / "result.json"
            policy.write_report(out, status="PASS", sha=SHA, backup=snap, started="2026-11-09T01:00:00Z", result_code=0)
            obj = json.loads(out.read_text())
            self.assertEqual(obj["result"], "PASS")
            self.assertEqual(obj["backup_stamp"], snap.name)
            self.assertNotIn(str(root), out.read_text())
            self.assertFalse(obj["private_logs_uploaded"])
            self.assertFalse(obj["restored_production"])
            self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
