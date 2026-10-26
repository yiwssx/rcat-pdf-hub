"""Fail-closed regression for bot patch required-check wait and SHA guards."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/dependabot-patch-automerge.yml"
BASE = "b" * 40
HEAD = "a" * 40


def shell_step(name: str) -> str:
    source = WORKFLOW.read_text(encoding="utf-8")
    marker = f"      - name: {name}\n"
    if source.count(marker) != 1:
        raise ValueError(f"Missing or duplicate step: {name}")
    lines = []
    for line in source.split(marker, 1)[1].split("        run: |\n", 1)[1].splitlines():
        if line.startswith("          "):
            lines.append(line[10:])
        elif not line:
            lines.append("")
        else:
            break
    if not lines:
        raise ValueError(f"Missing script body: {name}")
    return "\n".join(lines) + "\n"


class SoloBotMergeTests(unittest.TestCase):
    def test_required_checks_and_fresh_shas(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("github.event.pull_request.user.login == 'dependabot[bot]'", workflow)
        self.assertIn("check-direct-dependency.py", workflow)
        self.assertNotIn("pull_request_target:", workflow)
        self.assertNotIn("pull_request_review:", workflow)
        self.assertIn("checks: read", workflow)
        wait = shell_step("Wait for required branch checks")
        merge = shell_step("Squash-merge unchanged validated patch")
        self.assertIn("timeout 900s", wait)
        self.assertIn("--required --watch --fail-fast", wait)
        self.assertIn("current_main", merge)
        self.assertIn("current_head", merge)
        with tempfile.TemporaryDirectory(prefix="bot-checks-") as temp:
            root = Path(temp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            log = root / "calls.log"
            gh = bin_dir / "gh"
            gh.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$*\" >> \"$MOCK_LOG\"\n"
                "if [[ \"$1\" == pr && \"$2\" == checks ]]; then exit \"$MOCK_CHECKS_EXIT\"; fi\n"
                "if [[ \"$1\" == api && \"$2\" == -X && \"$3\" == PUT ]]; then echo '{\"merged\":true}'; exit 0; fi\n"
                "if [[ \"$1\" == api && \"$2\" == *'/git/ref/heads/main' ]]; then echo \"$MOCK_MAIN\"; exit 0; fi\n"
                "if [[ \"$1\" == api && \"$2\" == *'/pulls/'* ]]; then echo \"$MOCK_HEAD\"; exit 0; fi\n"
                "exit 97\n",
                encoding="utf-8",
            )
            gh.chmod(0o755)
            jq = bin_dir / "jq"
            jq.write_text("#!/usr/bin/env bash\necho true\n", encoding="utf-8")
            jq.chmod(0o755)
            for check_exit, live_base, live_head in (
                (1, BASE, HEAD),    # failed check
                (8, BASE, HEAD),    # pending check
                (124, BASE, HEAD),  # expired timeout
                (0, "c" * 40, HEAD),  # stale base
                (0, BASE, "d" * 40),  # stale head
                (0, BASE, HEAD),     # all checks green and fresh
            ):
                with self.subTest(check=check_exit, base=live_base, head=live_head):
                    log.write_text("", encoding="utf-8")
                    env = os.environ.copy()
                    env.update({
                        "PATH": f"{bin_dir}:{env['PATH']}",
                        "MOCK_LOG": str(log),
                        "MOCK_CHECKS_EXIT": str(check_exit),
                        "MOCK_MAIN": live_base,
                        "MOCK_HEAD": live_head,
                        "BASE_SHA": BASE,
                        "HEAD_SHA": HEAD,
                        "PR_NUMBER": "42",
                        "REPO": "example/repo",
                    })
                    proc = subprocess.run(
                        ["bash", "-e", "-o", "pipefail", "-c", wait + merge],
                        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
                    )
                    calls = log.read_text(encoding="utf-8")
                    self.assertIn("pr checks 42 --repo example/repo --required --watch --fail-fast", calls)
                    success = check_exit == 0 and live_base == BASE and live_head == HEAD
                    self.assertEqual(proc.returncode == 0, success, proc.stderr)
                    self.assertEqual("api -X PUT" in calls, success)


if __name__ == "__main__":
    unittest.main()
