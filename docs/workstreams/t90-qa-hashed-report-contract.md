# T90-5 independent acceptance — hashed report contract

**Updated 2026-11-09.** Source of truth: `contracts/t90-rcat-pilot-acceptance.v1.json`; validator: `scripts/validate-t90-rcat-pilot-acceptance.py`; canonical tracker: [#262](https://github.com/yiwssx/rcat-pdf-hub/issues/262).

## Current evidence boundary

The canonical ledger currently has 40 `IMPLEMENTED`, 1 `STAGED` (T21 Publisher), 49 `UNASSESSED`, **0 `VERIFIED` and 0 `RELEASED`**. These are 90 independent engineering/acceptance entries, separate from the nine operational R1 tools. Never equate a green PR or a working Google Login with institutional acceptance.

## Schema for independently reviewed reports

For `VERIFIED`, these **four** fields each require a **structured object** with an explicit `PASS` result, SHA-256 of the preserved report, an opaque pointer to approved restricted RCAT evidence storage, and an exact UTC validation timestamp:

- `source_vs_output_report` — original vs actual output; Thai fonts/layout and visible content as applicable
- `security_isolation_report` — malicious/invalid sources, egress/SSRF, AV and resource isolation
- `owner_scope_test_report` — real RCAT user vs another user; scope, session and download rejection
- `thai_fidelity_report` — authentic Thai original and rendered/converted result comparisons

Example of **schema shape only** (not real approval):

```json
{
  "result": "PASS",
  "artifact_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "evidence_ref": "rcat-evidence:synthetic-example-not-real-qa",
  "checked_at": "2026-11-09T00:00:00Z"
}
```

Each real report must use a different independently preserved artifact where applicable, with its true digest and internal reference. The `rcat-evidence:` identifier is **not** a public URL; keep private documents and actual student/staff contents off GitHub. Text such as `"passed"`, `"pending"`, a random URL, a missing digest, `result=PENDING`, or an invalid UTC date **must be rejected** by the validator.

A `RELEASED` entry also requires a hashed `institutional_sso_report` using this same structure, approved operator identity and time, intended cohort and a documented rollback plan.

**Limitations:** This is a **format/integrity gate**, not an online verifier of an internal evidence store. A well-formed JSON object is not by itself proof that a report exists or is true. The operator/reviewer must check the private artifact, digest, actual RCAT host, real file output and exact feature flag at review time before advancing the state. PRs may not promote all 90 entries automatically.

## Verification before acceptance

Run the validator and targeted tests on the reviewed commit, and attach actual restricted evidence, not sensitive originals, to the internal audit system. Keep legacy R1 authorization acceptance in [#308](https://github.com/yiwssx/rcat-pdf-hub/issues/308), new-engineering backlog in [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172), and this independent per-tool certification in [#262](https://github.com/yiwssx/rcat-pdf-hub/issues/262).
