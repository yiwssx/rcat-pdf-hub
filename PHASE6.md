# Phase 6 — Production Hardening & Scale

Status: **implementation complete; 0.6.0 release candidate pending production release gate**

Phase 6 hardens RCAT PDF Hub for long-term self-hosted production operation while preserving the zero-paid-cloud policy and Docker Compose deployment model.

## Completed workstreams

### Reproducibility and supply chain
- committed reproducible npm and hash-pinned Python dependency locks;
- `npm ci` / `pip --require-hashes` validation paths;
- pinned Trivy source/image scanning;
- CycloneDX SBOM generation.

### Production runtime hardening
- explicit production Compose override;
- read-only application roots, dropped capabilities and `no-new-privileges`;
- explicit CPU/memory/PID/tmpfs ceilings;
- segmented edge/app/data/management/egress networks.

### Queue and worker isolation
- deterministic interactive / standard / heavy job classification;
- dedicated RQ worker pools;
- workload-specific timeouts and scaling;
- per-queue metrics and starvation/backlog alerts.

### Operations visibility
- bundled Alertmanager;
- persistent Tempo trace backend;
- provisioned Grafana operations dashboard;
- Prometheus/OTel integration on the private management plane.

### Human RBAC
- explicit `viewer`, `operator`, and `admin` roles;
- fail-closed OIDC/LDAP group-to-role mapping;
- role-bearing sessions with centrally recomputed scopes;
- Admin Console visibility for effective identity, role, groups and scopes.

### File-library scale and storage integrity
- server-side file search/filter/sort/pagination;
- measured query indexes including PostgreSQL trigram filename search;
- scalable paged Files UI;
- administrator-only dry-run DB ↔ storage reconciliation.

### Quality gates
- FastAPI OpenAPI ↔ frontend contract drift detection;
- backend statement-line coverage floor of **61.36%**;
- browser accessibility regression gate for critical/serious findings;
- measured browser performance budgets for `/` and `/files`.

## Release validation

Code and production readiness remain separate by design.

Code gate:

```bash
PDFHUB_RELEASE_MODE=code make release-readiness
```

Production gate requires operator-selected deployment evidence:

```bash
BACKUP=/path/to/verified-backup \
URL=https://intended-pdf-hub-endpoint \
make release-readiness
```

The production gate runs full zero-cost validation, source/image supply-chain checks, local-CI enforcement checks, backup verification, an isolated DR drill, and deployment-target load/latency smoke.

`v0.6.0` must not be tagged until the production gate succeeds for the intended deployment target.

## Architecture decisions

- [ADR-0001 — Tool Workspace seam](docs/adr/0001-tool-workspace-seam.md)
- [ADR-0002 — Workload queue classes](docs/adr/0002-job-queue-classes.md)
- [ADR-0003 — Dedicated worker pools](docs/adr/0003-dedicated-worker-pools.md)
- [ADR-0004 — Human RBAC](docs/adr/0004-human-rbac.md)

The canonical task/evidence log remains [the Phase 6 tracker](docs/workstreams/phase6-production-hardening-tracker.md).
