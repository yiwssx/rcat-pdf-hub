# Supply-chain policy

RCAT PDF Hub uses a zero-cost, self-hosted-friendly supply-chain gate based on a pinned Trivy container.

## Scanner baseline

- Scanner: Trivy
- Reviewed image tag: `aquasec/trivy:0.75.0`
- Frontend dependency graph: committed npm lockfile
- Python dependency graph: committed hash-pinned requirements lock
- SBOM format: CycloneDX JSON

## Release artifacts

The supply-chain gate writes machine-readable artifacts to `artifacts/supply-chain/`:

- `source.cdx.json`
- `source-vulnerabilities.json`
- `config-findings.json`
- `api-image.cdx.json`
- `api-image-vulnerabilities.json`
- `web-image.cdx.json`
- `web-image-vulnerabilities.json`

These files are generated artifacts and are not committed to the repository.

## Severity policy

- **Fixable CRITICAL dependency/image vulnerabilities:** blocking.
- **Unfixed CRITICAL vulnerabilities:** reported, but do not automatically block because no remediation is available; they require operator risk review before production release.
- **HIGH vulnerabilities:** reported and reviewed, but are not an automatic Phase 6A blocker.
- **Configuration findings:** reported during Phase 6A. Phase 6B container/network hardening may promote specific configuration classes to blocking policy.

The policy is intentionally explicit rather than silently raising thresholds to make a release pass.

## Commands

Source dependency/config scan and source SBOM:

```bash
make validate-supply-chain-source
```

Production image scans and image SBOMs:

```bash
make validate-supply-chain-images
```

Full supply-chain gate:

```bash
make validate-supply-chain
```

The production release-readiness path runs the source gate and the image gate. No paid scanning service is required.
