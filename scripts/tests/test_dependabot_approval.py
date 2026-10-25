"""Regressions for the strict Dependabot approval gate (no GitHub tokens)."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
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
