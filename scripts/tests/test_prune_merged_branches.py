"""Pure eligibility tests: never make GitHub API calls or delete refs."""
from __future__ import annotations

from datetime import datetime, timezone
import unittest
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "prune_merged_branches.py"
spec = importlib.util.spec_from_file_location("prune_merged_branches", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
classify = module.classify

NOW = datetime(2026, 11, 4, tzinfo=timezone.utc)
REPO = "yiwssx/rcat-pdf-hub"


def branch(name="feature/merged", sha="abc", protected=False):
    return {"name": name, "commit": {"sha": sha}, "protected": protected}


def pull(state="closed", merged_at="2026-11-02T00:00:00Z", sha="abc", number=4, ref="feature/merged"):
    return {"number": number, "state": state, "merged_at": merged_at,
            "head": {"ref": ref, "sha": sha, "repo": {"full_name": REPO}}}


class PruneBranchesTests(unittest.TestCase):
    def reason(self, b, ps, **kwargs):
        return classify(b, ps, REPO, "main", now=NOW, **kwargs)[0]

    def test_only_unchanged_merged_branch_eligible(self):
        self.assertEqual(self.reason(branch(), [pull()]), "eligible")
        self.assertEqual(self.reason(branch(sha="new"), [pull()]), "branch changed after PR merge")

    def test_preserve_open_pr_even_when_previous_pr_merged(self):
        self.assertEqual(self.reason(branch(), [pull(), pull(state="open", merged_at=None, number=5)]), "open PR")

    def test_preserve_default_protected_and_dependabot(self):
        self.assertEqual(self.reason(branch("main"), []), "protected")
        self.assertEqual(self.reason(branch(protected=True), [pull()]), "protected")
        self.assertEqual(self.reason(branch("dependabot/pip/foo"), []), "protected")

    def test_preserve_orphans_closed_unmerged_and_recent(self):
        self.assertEqual(self.reason(branch(), []), "no linked PR")
        self.assertEqual(self.reason(branch(), [pull(merged_at=None)]), "latest PR not merged")
        self.assertEqual(self.reason(branch(), [pull(merged_at="2026-11-03T23:00:00Z")], min_age_days=2), "too recent")

    def test_latest_pr_authoritative_and_forks_not_matched(self):
        self.assertEqual(self.reason(branch(), [pull(), pull(merged_at=None, number=6)]), "latest PR not merged")
        other = pull()
        other["head"]["repo"]["full_name"] = "someone/fork"
        self.assertEqual(self.reason(branch(), [other]), "no linked PR")


if __name__ == "__main__":
    unittest.main()
