"""Read-only bot lock artifact workflow security regression tests."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/dependabot-python-security.yml").read_text(encoding="utf-8")

class PythonLockArtifactWorkflowTests(unittest.TestCase):
    def test_bot_only_and_immutable_base(self):
        job = WORKFLOW.split("\n  lock-artifact:\n", 1)[1]
        self.assertIn("github.event.pull_request.user.login == 'dependabot[bot]'", job)
        self.assertIn("github.event.pull_request.base.ref == 'main'", job)
        self.assertIn("ref: ${{ env.BASE_SHA }}", job)
        self.assertIn("persist-credentials: false", job)
        self.assertIn("test \"$(git rev-parse refs/remotes/origin/dependabot-lock-pr)\" = \"${HEAD_SHA}\"", job)
        self.assertLess(job.index("check-python-security-dependency.py"), job.index("git show \"${HEAD_SHA}:apps/api/requirements.txt\""))

    def test_no_write_permission_or_unsafe_trigger(self):
        self.assertNotIn("pull_request_target:", WORKFLOW)
        self.assertNotIn("contents: write", WORKFLOW)
        self.assertNotIn("pull-requests: write", WORKFLOW)
        self.assertNotIn("gh pr merge", WORKFLOW)
        self.assertNotIn("git push", WORKFLOW)

    def test_hashed_artifact_is_only_output(self):
        job = WORKFLOW.split("\n  lock-artifact:\n", 1)[1]
        self.assertIn("runs-on: ubuntu-latest", job)
        self.assertIn("bash scripts/compile-python-lock.sh", job)
        self.assertIn("python3 scripts/check-python-lock.py", job)
        self.assertLess(job.index("compile-python-lock.sh"), job.index("actions/upload-artifact@v6"))
        self.assertIn("path: apps/api/requirements.lock", job)
        self.assertIn("if-no-files-found: error", job)
        self.assertIn("retention-days: 14", job)

if __name__ == "__main__":
    unittest.main()
