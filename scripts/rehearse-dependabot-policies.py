#!/usr/bin/env python3
"""Offline policy/SHA rehearsal. No network, GitHub writes or dependency install.

Synthetic git fixtures exercise the real trusted policy scripts. The exact npm
merge shell is executed against a stub gh binary, never the real GitHub CLI.
This is not evidence of a real Dependabot-triggered workflow execution.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], cwd: Path, **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, **kwargs)


def must(result: subprocess.CompletedProcess[str], expected: int, case: str) -> None:
    if result.returncode != expected:
        raise AssertionError(f"{case}: expected {expected}, got {result.returncode}\n{result.stdout}\n{result.stderr}")


def commit(repo: Path, message: str) -> str:
    for args in (["git", "add", "."], ["git", "commit", "-qm", message]):
        must(run(args, repo), 0, "fixture commit")
    result = run(["git", "rev-parse", "HEAD"], repo)
    must(result, 0, "fixture SHA")
    return result.stdout.strip()


def write(repo: Path, path: str, value: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(value, encoding="utf-8")


def npm_manifest(repo: Path, version: str, *, lock_version: str | None = None) -> None:
    package = {"name": "offline-policy-fixture", "version": "1.0.0", "dependencies": {"example": version}}
    lock_root = dict(package)
    lock_root["dependencies"] = {"example": lock_version or version}
    write(repo, "apps/web/package.json", json.dumps(package))
    write(repo, "apps/web/package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {"": lock_root}}))


def policies(repo: Path) -> int:
    must(run(["git", "init", "-q"], repo), 0, "fixture init")
    for key, value in (("user.name", "Offline rehearsal"), ("user.email", "offline@example.invalid")):
        must(run(["git", "config", key, value], repo), 0, "fixture identity")
    npm_manifest(repo, "1.2.3")
    write(repo, "apps/api/requirements.txt", "pypdf==6.19.0\nPillow==12.3.0\n")
    base = commit(repo, "fixture base")
    count = 0

    def check(name: str, expected: int, script: str) -> None:
        nonlocal count
        head = commit(repo, name)
        result = run([sys.executable, str(ROOT / "scripts" / script), base, head], repo)
        must(result, expected, name)
        print(f"PASS: {name}")
        count += 1
        must(run(["git", "reset", "--hard", base], repo), 0, "reset disposable fixture")
        must(run(["git", "clean", "-fd"], repo), 0, "clean disposable fixture")

    npm_manifest(repo, "1.2.4")
    check("npm forward patch accepted", 0, "check-direct-dependency.py")
    npm_manifest(repo, "1.3.0")
    check("npm minor rejected", 1, "check-direct-dependency.py")
    npm_manifest(repo, "1.2.2")
    check("npm downgrade rejected", 1, "check-direct-dependency.py")
    npm_manifest(repo, "1.2.4", lock_version="1.2.3")
    check("npm mismatched lock rejected", 1, "check-direct-dependency.py")
    npm_manifest(repo, "1.2.4")
    write(repo, "unexpected.sh", "exit 0\n")
    check("npm unexpected file rejected", 1, "check-direct-dependency.py")
    write(repo, "apps/api/requirements.txt", "pypdf==6.19.1\nPillow==12.3.0\n")
    check("python single forward pin accepted", 0, "check-python-security-dependency.py")
    write(repo, "apps/api/requirements.txt", "pypdf==6.19.1\nPillow==12.3.0\n")
    write(repo, "apps/api/requirements.lock", "# synthetic lock fixture; not installable\n")
    check("python manifest plus lock allowed by policy", 0, "check-python-security-dependency.py")
    write(repo, "apps/api/requirements.txt", "pypdf==6.18.0\nPillow==12.3.0\n")
    check("python downgrade rejected", 1, "check-python-security-dependency.py")
    write(repo, "apps/api/requirements.txt", "pypdf==6.19.1\nPillow==12.3.1\n")
    check("python multiple pins rejected", 1, "check-python-security-dependency.py")
    write(repo, "apps/api/requirements.txt", "pypdf==6.19.1\nPillow==12.3.0\n# unexpected change\n")
    check("python extra manifest edit rejected", 1, "check-python-security-dependency.py")
    return count


def sha_guards(work: Path) -> int:
    workflow = (ROOT / ".github/workflows/dependabot-patch-automerge.yml").read_text()
    marker = "      - name: Squash-merge unchanged validated patch\n        run: |\n"
    if workflow.count(marker) != 1:
        raise AssertionError("Cannot identify exact merge shell; update rehearsal for reviewed workflow")
    shell = textwrap.dedent(workflow.split(marker, 1)[1])
    if not shell.strip():
        raise AssertionError("Missing merge shell")
    # An unexpected extra workflow stanza must fail rather than be ignored.
    script = work / "merge-under-test.sh"
    script.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + shell)
    bindir = work / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text("""#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args == ['api', 'repos/offline/fixture/git/ref/heads/main', '--jq', '.object.sha']:
    print(os.environ['MOCK_MAIN'])
elif args == ['api', 'repos/offline/fixture/pulls/1', '--jq', '.head.sha']:
    print(os.environ['MOCK_HEAD'])
elif args == ['api', '-X', 'PUT', 'repos/offline/fixture/pulls/1/merge', '-f', 'merge_method=squash', '-f', 'sha=' + os.environ['HEAD_SHA']]:
    with open(os.environ['MOCK_MERGE_LOG'], 'w') as log:
        log.write('sha=' + os.environ['HEAD_SHA'])
    print(json.dumps({'merged': os.environ['MOCK_MERGED'] == 'true'}))
else:
    print('Unexpected gh call; offline rehearsal refuses it', file=sys.stderr)
    sys.exit(97)
""")
    gh.chmod(0o700)
    base, head = "1" * 40, "2" * 40
    cases = [
        ("unchanged SHA uses exact head (offline stub only)", base, head, "true", 0, True),
        ("moved main rejects stale merge", "3" * 40, head, "true", 1, False),
        ("moved head rejects stale merge", base, "4" * 40, "true", 1, False),
        ("server refusal remains failure", base, head, "false", 1, True),
    ]
    for name, current_main, current_head, merged, status, expected_call in cases:
        log = work / "offline-merge-call"
        log.unlink(missing_ok=True)
        env = os.environ.copy()
        env.pop("GH_TOKEN", None)
        env.pop("GITHUB_TOKEN", None)
        env.update(PATH=str(bindir) + os.pathsep + env["PATH"], REPO="offline/fixture", PR_NUMBER="1",
                   BASE_SHA=base, HEAD_SHA=head, MOCK_MAIN=current_main, MOCK_HEAD=current_head,
                   MOCK_MERGED=merged, MOCK_MERGE_LOG=str(log))
        result = run(["bash", str(script)], work, env=env)
        must(result, status, name)
        if log.exists() != expected_call:
            raise AssertionError(f"{name}: unexpected offline merge-call state")
        if log.exists() and log.read_text() != "sha=" + head:
            raise AssertionError("Wrong validated head sent to offline stub")
        print(f"PASS: {name}")
    return len(cases)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="pdfhub-bot-policy-rehearsal-") as directory:
        work = Path(directory)
        repo = work / "fixture"
        repo.mkdir()
        count = policies(repo) + sha_guards(work)
    print(f"Dependabot offline policy/SHA rehearsal: {count} PASS; no GitHub write or real merge")


if __name__ == "__main__":
    main()

