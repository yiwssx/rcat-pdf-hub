"""Regressions for the strict Dependabot approval gate (no GitHub tokens)."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-dependabot-approval.py"
HEAD = "a" * 40
OLD = "b" * 40
spec = importlib.util.spec_from_file_location("dependabot_approval_gate", SCRIPT)
assert spec and spec.loader
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def review(review_id, state="APPROVED", sha=HEAD, login="reviewer", user_type="User"):
    return {"id": review_id, "state": state, "commit_id": sha,
            "user": {"login": login, "type": user_type}}


def workflow_step_script(step_name):
    """Extract a literal GitHub Actions run block without a YAML dependency."""
    content = (ROOT / ".github/workflows/dependabot-patch-automerge.yml").read_text(encoding="utf-8")
    marker = f"      - name: {step_name}\\n".replace("\\n", "\n")
    if content.count(marker) != 1:
        raise ValueError(f"Missing or duplicate workflow step: {step_name}")
    section = content.split(marker, 1)[1]
    if "        run: |\n" not in section:
        raise ValueError(f"No shell body: {step_name}")
    lines = []
    for line in section.split("        run: |\n", 1)[1].splitlines():
        if line.startswith("          "):
            lines.append(line[10:])
        elif not line:
            lines.append("")
        else:
            break
    if not lines:
        raise ValueError(f"Empty shell step: {step_name}")
    return "\n".join(lines) + "\n"


class DependabotApprovalTests(unittest.TestCase):
    def test_missing_review_and_comment_not_approval(self):
        self.assertFalse(gate.has_independent_approval([], HEAD))
        self.assertFalse(gate.has_independent_approval([review(1, "COMMENTED")], HEAD))

    def test_rejects_stale_head_and_bot_approval(self):
        self.assertFalse(gate.has_independent_approval([review(1, sha=OLD)], HEAD))
        self.assertFalse(gate.has_independent_approval(
            [review(1, login="dependabot[bot]", user_type="Bot")], HEAD
        ))

    def test_approval_by_human_on_exact_head(self):
        self.assertTrue(gate.has_independent_approval([review(1)], HEAD))
        self.assertTrue(gate.has_independent_approval([[review(1)]], HEAD))

    def test_changes_requested_blocks_merge_even_if_approved_elsewhere(self):
        self.assertFalse(gate.has_independent_approval(
            [review(1), review(2, "CHANGES_REQUESTED", login="another")], HEAD
        ))

    def test_later_dismissal_or_changes_requested_invalidates_approval(self):
        self.assertFalse(gate.has_independent_approval(
            [review(1), review(3, "DISMISSED")], HEAD
        ))
        self.assertFalse(gate.has_independent_approval(
            [review(1), review(3, "CHANGES_REQUESTED")], HEAD
        ))

    def test_latest_reapproval_and_pagination_order(self):
        self.assertTrue(gate.has_independent_approval(
            [[review(10), review(11, "CHANGES_REQUESTED")], [review(12)]], HEAD
        ))
        self.assertTrue(gate.has_independent_approval(
            [review(12), review(11, "CHANGES_REQUESTED"), review(10)], HEAD
        ))

    def test_invalid_evidence_fails_closed(self):
        for payload in ({}, [None], [[review(1)], None], [{"state": "APPROVED"}]):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                gate.has_independent_approval(payload, HEAD)
        with self.assertRaises(ValueError):
            gate.has_independent_approval([review(1)], "not-a-commit")

    def test_required_check_wait_refuses_merge_on_fail_or_pending(self):
        """Run the actual reviewed wait and merge shell with local fake gh only."""
        workflow = (ROOT / ".github/workflows/dependabot-patch-automerge.yml").read_text(encoding="utf-8")
        wait = workflow_step_script("Wait for required branch checks")
        merge = workflow_step_script("Squash-merge unchanged validated patch")
        self.assertIn("if: steps.approval.outputs.approved == 'true'", workflow)
        self.assertIn("--required --watch --fail-fast", wait)
        self.assertIn("timeout 900s", wait)
        self.assertIn("current_main", merge)
        self.assertIn("current_head", merge)

        with tempfile.TemporaryDirectory(prefix="dependabot-check-gate-") as temp:
            root = Path(temp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            gh_log = root / "gh.log"
            gh = bin_dir / "gh"
            gh.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$*\" >> \"$MOCK_GH_LOG\"\n"
                "if [[ \"$1\" == pr && \"$2\" == checks ]]; then exit \"$MOCK_CHECKS_EXIT\"; fi\n"
                "if [[ \"$1\" == api && \"$2\" == -X && \"$3\" == PUT ]]; then echo '{\"merged\":true}'; exit 0; fi\n"
                "if [[ \"$1\" == api && \"$2\" == *'/git/ref/heads/main' ]]; then echo \"$BASE_SHA\"; exit 0; fi\n"
                "if [[ \"$1\" == api && \"$2\" == *'/pulls/'* ]]; then echo \"$HEAD_SHA\"; exit 0; fi\n"
                "exit 99\n",
                encoding="utf-8",
            )
            gh.chmod(0o755)
            jq = bin_dir / "jq"
            jq.write_text("#!/usr/bin/env bash\necho true\n", encoding="utf-8")
            jq.chmod(0o755)

            for check_exit in (1, 8, 0):
                with self.subTest(check_exit=check_exit):
                    gh_log.write_text("", encoding="utf-8")
                    env = os.environ.copy()
                    env.update({
                        "PATH": f"{bin_dir}:{env['PATH']}",
                        "MOCK_GH_LOG": str(gh_log),
                        "MOCK_CHECKS_EXIT": str(check_exit),
                        "REPO": "example/repo",
                        "PR_NUMBER": "42",
                        "BASE_SHA": OLD,
                        "HEAD_SHA": HEAD,
                    })
                    result = subprocess.run(
                        ["bash", "-e", "-o", "pipefail", "-c", wait + merge],
                        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
                    )
                    calls = gh_log.read_text(encoding="utf-8")
                    self.assertIn("pr checks 42 --repo example/repo --required --watch --fail-fast", calls)
                    if check_exit:
                        self.assertEqual(result.returncode, check_exit, result.stderr)
                        self.assertNotIn("api -X PUT", calls, "Merge API called on failed/pending checks")
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn("api -X PUT", calls)


    def test_cli_exit_codes(self):
        for payload, expected in (([], 3), ([[review(1)]], 0), ({}, 2)):
            with self.subTest(payload=payload):
                process = subprocess.run(
                    [sys.executable, str(SCRIPT), HEAD],
                    input=json.dumps(payload), capture_output=True, text=True, check=False,
                )
                self.assertEqual(process.returncode, expected, process.stderr)
        bad_json = subprocess.run(
            [sys.executable, str(SCRIPT), HEAD],
            input="{bad", capture_output=True, text=True, check=False,
        )
        self.assertEqual(bad_json.returncode, 2)


if __name__ == "__main__":
    unittest.main()
