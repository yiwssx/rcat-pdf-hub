#!/usr/bin/env python3
"""Conservatively prune GitHub PR branches; dry-run unless --execute --yes.

Requires an authenticated GitHub CLI (gh auth status) and contents:write rights.
A branch is eligible only when its most recent PR was merged, its exact head
SHA was not advanced after merge, and no PR currently references it as open.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import subprocess
from urllib.parse import quote

REPOSITORY = "yiwssx/rcat-pdf-hub"
PROTECTED_PREFIXES = ("dependabot/", "release/", "hotfix/")


def api(endpoint: str, *, paginate: bool = False, method: str = "GET"):
    args = ["gh", "api"]
    if paginate:
        args.extend(("--paginate", "--slurp"))
    if method != "GET":
        args.extend(("-X", method))
    args.append(endpoint)
    result = subprocess.run(args, text=True, capture_output=True, check=True)
    if method == "DELETE":
        return None
    return json.loads(result.stdout)


def all_pages(endpoint: str) -> list[dict]:
    pages = api(endpoint, paginate=True)
    if not isinstance(pages, list) or not all(isinstance(p, list) for p in pages):
        raise ValueError("Unexpected paginated GitHub response")
    return [item for page in pages for item in page]


def classify(branch: dict, pulls: list[dict], repository: str, default: str,
             min_age_days: int = 0, now: datetime | None = None) -> tuple[str, dict | None]:
    name = branch["name"]
    if (name == default or branch.get("protected")
            or name.startswith(PROTECTED_PREFIXES)):
        return "protected", None
    same_repo = [p for p in pulls if (p.get("head") or {}).get("ref") == name
                 and ((p.get("head") or {}).get("repo") or {}).get("full_name") == repository]
    if any(p.get("state") == "open" for p in same_repo):
        return "open PR", None
    if not same_repo:
        return "no linked PR", None
    latest = max(same_repo, key=lambda p: p["number"])
    if not latest.get("merged_at"):
        return "latest PR not merged", None
    if ((latest.get("head") or {}).get("sha") != (branch.get("commit") or {}).get("sha")):
        return "branch changed after PR merge", None
    now = now or datetime.now(timezone.utc)
    merged = datetime.fromisoformat(latest["merged_at"].replace("Z", "+00:00"))
    if (now - merged).total_seconds() < min_age_days * 86400:
        return "too recent", None
    return "eligible", latest



def reviewed_pr_tip_matches(repository: str, pr_number: int, sha: str) -> bool:
    """Require the last immutable PR review commit, not just mutable head.ref."""
    commits = all_pages(f"repos/{repository}/pulls/{pr_number}/commits?per_page=100")
    return bool(commits) and commits[-1].get("sha") == sha


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=REPOSITORY)
    parser.add_argument("--execute", action="store_true", help="actually delete eligible branches")
    parser.add_argument("--yes", action="store_true", help="confirm irreversible remote deletion")
    parser.add_argument("--min-age-days", type=int, default=0)
    args = parser.parse_args()
    if args.min_age_days < 0:
        parser.error("--min-age-days cannot be negative")
    if args.execute and not args.yes:
        parser.error("deletion requires both --execute and --yes")
    if args.repo != REPOSITORY:
        parser.error("this reviewed utility is scoped to yiwssx/rcat-pdf-hub only")

    meta = api(f"repos/{args.repo}")
    default = meta["default_branch"]
    branches = all_pages(f"repos/{args.repo}/branches?per_page=100")
    pulls = all_pages(f"repos/{args.repo}/pulls?state=all&per_page=100")
    eligible = []
    for branch in sorted(branches, key=lambda b: b["name"]):
        reason, pr = classify(branch, pulls, args.repo, default, args.min_age_days)
        print(f"{reason:30s} {branch['name']}",
              f"(PR #{pr['number']})" if pr else "")
        if pr:
            eligible.append((branch, pr))
    print(f"Eligible: {len(eligible)} / {len(branches)}. ",
          "Execute enabled" if args.execute else "DRY RUN: nothing was deleted")
    if not args.execute:
        return 0

    deleted = 0
    owner = args.repo.split("/", 1)[0]
    for branch, pr in eligible:
        name, sha = branch["name"], branch["commit"]["sha"]
        encoded = quote(name, safe="/")
        # Recheck exact HEAD, same merged PR and absence of active PRs at deletion time.
        fresh = api(f"repos/{args.repo}/git/ref/heads/{encoded}")
        latest = api(f"repos/{args.repo}/pulls/{pr['number']}")
        head_filter = quote(f"{owner}:{name}", safe="")
        active = api(f"repos/{args.repo}/pulls?state=open&head={head_filter}")
        if (fresh["object"]["sha"] != sha
                or latest.get("merged_at") is None
                or latest["head"]["sha"] != sha
                or active
                or not reviewed_pr_tip_matches(args.repo, pr["number"], sha)):
            print(f"SKIP: changed/open since planning: {name}")
            continue
        api(f"repos/{args.repo}/git/refs/heads/{encoded}", method="DELETE")
        print(f"DELETED: {name} (PR #{pr['number']})")
        deleted += 1
    print(f"Deleted {deleted}/{len(eligible)} eligible branches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
