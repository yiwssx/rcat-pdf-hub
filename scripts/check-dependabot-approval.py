#!/usr/bin/env python3
"""Fail-closed independent approval check for a validated Dependabot PR head.

Exit 0: a non-bot GitHub user approved exactly the current validated HEAD.
Exit 3: approval is missing, dismissed, stale or contradicted (do not merge).
Exit 2: malformed review evidence or invalid input (CI must fail).
GitHub's active ruleset remains the final authority at merge time.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

SHA = re.compile(r"[0-9a-f]{40}\Z")
MEANINGFUL_STATES = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}


def has_independent_approval(payload: Any, head_sha: str) -> bool:
    if not isinstance(head_sha, str) or not SHA.fullmatch(head_sha):
        raise ValueError("Expected exact 40-character lowercase commit SHA")
    if not isinstance(payload, list):
        raise ValueError("Review response must be a JSON list")
    if payload and all(isinstance(page, list) for page in payload):
        reviews = [review for page in payload for review in page]
    elif all(isinstance(review, dict) for review in payload):
        reviews = payload
    else:
        raise ValueError("Review response has an invalid pagination structure")

    for review in reviews:
        if not isinstance(review, dict) or not isinstance(review.get("id"), int):
            raise ValueError("Review is missing a numeric GitHub ID")
        if not isinstance(review.get("user"), dict):
            raise ValueError("Review is missing its GitHub user")

    latest: dict[str, tuple[str, str | None]] = {}
    for review in sorted(reviews, key=lambda item: item["id"]):
        user = review["user"]
        login = user.get("login")
        if not isinstance(login, str) or not login:
            raise ValueError("Review is missing user login")
        if user.get("type") != "User" or login == "dependabot[bot]":
            continue
        state = review.get("state")
        if state in MEANINGFUL_STATES:
            latest[login] = (state, review.get("commit_id"))

    # Refuse if any reviewer currently requests changes to this exact head;
    # GitHub ruleset still determines reviewer permissions and thread state.
    if any(state == "CHANGES_REQUESTED" and sha == head_sha
           for state, sha in latest.values()):
        return False
    return any(state == "APPROVED" and sha == head_sha
               for state, sha in latest.values())


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: check-dependabot-approval.py EXACT_HEAD_SHA < reviews.json", file=sys.stderr)
        return 2
    try:
        reviews = json.load(sys.stdin)
        approved = has_independent_approval(reviews, sys.argv[1])
    except (ValueError, json.JSONDecodeError, TypeError) as exc:
        print(f"dependabot approval gate: INVALID EVIDENCE — {exc}", file=sys.stderr)
        return 2
    if not approved:
        print("dependabot approval gate: WAITING — independent APPROVED review of exact head required")
        return 3
    print("dependabot approval gate: PASS — exact-head independent approval present (ruleset still enforced)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
