# CI-LEAN-01 — isolated automated recovery evidence (no production deployment)

Tracks [#323](https://github.com/yiwssx/rcat-pdf-hub/issues/323). This
is **code preparation**, not proof of a working DR machine or successful restore.

## Trigger and safe default

The `Isolated DR evidence` GitHub Actions workflow is defined in
`.github/workflows/isolated-dr.yml`. It has only two triggers:
a **weekly schedule** (Monday 03:30 Asia/Bangkok) and an optional deliberate
`workflow_dispatch`. It has **no pull_request, push, or pull_request_target**.
The job is disabled unless the repository configuration variable
`RCAT_DR_RUNNER_READY` equals `true`. Skipped ≠ PASS.

The scheduled workflow needs a dedicated, **self-hosted** runner labeled
`rcat-dr-isolated` (Linux x64). The runner must be bound to trusted
protected-`main` code only. It must not share the institution's normal
production Docker daemon, and must not be exposed to public PR jobs.

## Required isolated host boundary

An authorized infrastructure agent must provision and establish all of these
facts **before enabling** `RCAT_DR_RUNNER_READY`:

1. A dedicated unprivileged Linux user runs GitHub Actions and its **own
   rootless Docker daemon** at `unix:///run/user/UID/docker.sock`; never
   `/var/run/docker.sock` and never a remote Production daemon. The daemon
   starts with no running containers. Use a separate VM or a strongly
   segregated user/daemon with bounded CPU/RAM on existing RCAT hardware.
2. A root-owned, non-group-writable/non-world-writable approval marker at
   `/etc/rcat-pdf-hub/dr-isolated-runner.enabled` has *exactly* one line:
   `RCAT_DR_ISOLATED_RUNNER_V1`. Its presence represents a reviewed host
   boundary, **not** an automated security proof.
3. An **actual read-only filesystem mount** of approved backup snapshot
   copies exists at `/mnt/rcat-dr-backups`. Direct child directories use
   UTC `YYYYMMDDTHHMMSSZ`, each holding `manifest.env`, `SHA256SUMS`,
   `postgres.dump` and the corresponding storage archive. Root and snapshot
   paths must not be symlinks. A standard writable backup directory, a
   checkout of Production data, or a normal writable Docker bind mount is
   not acceptable.
4. The isolated Actions checkout contains **no deployment `.env`**. The
   recovery script passes a narrow, clean environment to `dr-drill.sh`,
   overrides restore credentials with disposable values and never loads
   Production OAuth, database, or other deployment secrets.
5. Workflows only run on protected `refs/heads/main` from the exact
   `yiwssx/rcat-pdf-hub` repository. Before restore, the runner checks that
   HEAD matches the live main SHA and that `ci/required` and CodeQL for
   Python/JS succeeded on this **same SHA**.
6. Raw backup data, worker/API logs, `.env`, tokens and restored school
   records must **never** be sent to GitHub. The private runner keeps
   restricted local logs at `~/.local/state/rcat-pdf-hub-dr`; Actions
   uploads only `dr-evidence.json` with PASS/FAIL, SHA, backup stamp,
   checksum-manifest digest, timestamp, and exit code.
7. In an isolated Docker project, the existing DR script verifies checksums,
   restores PostgreSQL + object data into disposable volumes, runs migrations,
   waits for `/healthz` and `/readyz`, performs local load smoke and
   tears down containers/volumes. On nonzero exit, the workflow reports
   **FAIL**, not a green release.

This workflow does not trigger any deployment, disable backups, or authorize
Production release. Security gates for build images/antivirus/migration must
still be satisfied separately. The isolated DR run **does not** test a live
Production antivirus policy: it uses a clean, default-disabled AV configuration
to avoid crossing into Production services. A recovery PASS is only evidence
of a successful backup/restore/readiness drill, not full Production security
acceptance.

## Host provisioning and GitHub activation

- Provisioning requires access to the authorized non-Production runner host
  or a separate rootless daemon. A GitHub repository commit alone cannot
  install rootless Docker, mount backups read-only, or register a runner.
- After host-side boundary checks and runner registration, the repository
  administrator sets `RCAT_DR_RUNNER_READY=true` in GitHub Actions variables.
  This is an **enablement switch**, not a secret. It must remain unset until
  the runner is ready and dedicated.
- The weekly schedule then performs unattended DR and reports a sanitized
  GitHub Actions artifact/summary. A blocked/skipped workflow must never be
  used as a DR PASS.
- For failures, the infrastructure agent reviews private logs locally,
  corrects the cause, and only reports a new PASS after an actual rerun.
- To pause automatically, set `RCAT_DR_RUNNER_READY=false` or disconnect
  the dedicated runner; **do not** bypass branch protections or share
  Production Docker/socket access.

## Completion criteria

Do not close #323 or the related outstanding item in #318 until an actual
scheduled or authorized DR run with the private runner has reported PASS,
the result is bound to a main SHA and backup manifest, the real runner host
and backup mount isolation have been verified, and the original daily Backup
Timer is confirmed unaffected.
