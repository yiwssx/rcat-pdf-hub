# Conservative cleanup of merged GitHub branches

This utility deletes **remote topic branches**, never files or release tags. It is
dry-run only by default and deliberately excludes the default/protected branch,
dependabot branches, release/hotfix branches, active PR branches, branches whose
latest PR was closed without merging, branches without PR evidence, and branches
that advanced after their merged PR.

Prerequisites: `gh auth status` succeeds and the operator has permission to
delete repository refs. Run from a trusted workstation with Python 3.11+.

```bash
python3 scripts/prune_merged_branches.py
# Review candidates before granting deletion:
python3 scripts/prune_merged_branches.py --execute --yes
# Optional: require the merge to be at least one week old:
python3 scripts/prune_merged_branches.py --execute --yes --min-age-days 7
```

The tool rechecks remote SHA, the last immutable reviewed PR commit, merged PR, and open PRs immediately before each
DELETE. It cannot prove deployment provenance or the absence of references in
external automation; review its printed list before using --execute. No workflow
or scheduled job runs this script automatically.

Tests: `python3 -m unittest discover -s scripts/tests -p 'test_prune_merged_branches.py'`.
