# HDA-06 — RCAT PDF HUB private signed OCI candidate (STAGING ONLY)

**Owner decision:** approved a staging-only signed release candidate. Do not deploy, restart, retag, load, push or replace any Production container/image. This document concerns **new images only**, not retroactive provenance for the three existing Production Image IDs.

## Reuse already accepted evidence

- [GitHub source + build-input signer Run #43819808546](https://github.com/yiwssx/rcat-pdf-hub/actions/runs/43819808546), source `645de50a9205f5b54455ea78d8fef26e97640e9c`, operator-reported independent verification PASS. Do not redispatch.
- [One-time Production Host Image-ID and 57/57 running-font audit](https://github.com/yiwssx/rcat-deployment-control/issues/15#issuecomment-6908958254) accepted. **Do not repeat**.
- The reviewed initial candidate deliberately uses frozen signed source `645de50a...`; later main also contains web dependency changes. This is historical staging-only source, not a claim to include those later updates or certify current Production. The build script uses `git archive` of the **exact previously signed source commit**, never a mutable HEAD or a dirty live checkout.

## Strict staging trust boundary

The operator must separately provision **a Docker Engine/context that is NOT the Production/default Docker endpoint**, plus its named `docker-container` Buildx builder. A distinct named context is not proof of host separation: before accepting, the operator must establish independently that its endpoint is an authorized isolated staging environment. The script checks the endpoint differs from the default endpoint and its Buildx builder is attached to that staging context; it **refuses** to create builders/contexts on Production.

Preconditions on an authorized staging operator machine (not the live PDF HUB app directory):

- Docker CLI + Buildx + Python 3 + OpenSSL + Git. An existing nondefault staging Docker context and named Buildx `docker-container` builder; configure by an authorized staging administrator, **not by the script**.
- A fresh Git clone including signed source commit `645de50a...`; no credentials or private fonts committed. Source code for the build is taken from that earlier commit even though this script lives on a later reviewed main.
- A private local directory containing **the approved 57 institution-licensed TTF files**, separate from any public repository or artifact store. It must pass the existing filename/content SHA-256 fingerprint validator. The source files are copied only to a temporary restricted private staging build context and then removed. The resulting Gotenberg OCI tar **contains the licensed fonts**, so remains strictly local/private.
- A **pre-existing/owner-approved operator signing private key** (PEM; permission 0600 or 0400) and its independently trusted public key. The public-key SHA-256 fingerprint should be accepted through the institution's normal out-of-band process. This is an OpenSSL operator signature, **not a Sigstore GitHub OIDC identity**. The private key is never copied or uploaded.
- A user-owned output directory with permission `0700` outside the Git checkout, adequate free storage, disk and memory. Three builds may be resource-intensive: do not use a Docker Engine shared with Production. BuildKit must support explicit SLSA v1 output; the verifier does not accept the default v0.2 predicate.

### Configure and inspect (no build)

Use names/paths that really exist in the private staging environment:

```bash
cd /path/to/private/staging/rcat-pdf-hub

export PDFHUB_STAGE_DOCKER_CONTEXT=pdfhub-staging
export PDFHUB_STAGE_BUILDER=pdfhub-stage-builder
export PDFHUB_STAGE_OUTPUT_ROOT=/path/to/private/candidate-output
export PDFHUB_STAGE_FONTS_DIR=/path/to/private/13fonts
export PDFHUB_STAGE_SIGN_KEY=/path/to/private/approved-signing-key.pem
export PDFHUB_STAGE_VERIFY_KEY=/path/to/trusted/approved-public-key.pem

bash scripts/pdfhub-stage-signed-candidate.sh --preflight
```

`PDFHUB_STAGE_PREFLIGHT=PASS` means only the isolated context, available key, signed source commit and staged font inputs meet the preconditions. It does not start a build or claim a released OCI image.

### Build exactly one private staging candidate

After the operator has validated the **actual remote staging endpoint** is distinct from Production:

```bash
PDFHUB_STAGE_APPROVAL=APPROVED_PRIVATE_STAGE_BUILD_ONLY \
  bash scripts/pdfhub-stage-signed-candidate.sh --build
```

This runs **three builds** in the dedicated staging BuildKit context, using `--provenance=mode=max,version=v1`, `--platform linux/amd64`, and `--output type=oci,dest=...`. No `--push`, `--load`, Compose or Production operation. It checks each private OCI tar's runtime image manifest/config revision labels, all referenced layer digests, image-linked BuildKit in-toto SLSA v1 provenance and subject digest. Then it signs the complete digest receipt with the approved local private key; verification immediately re-reads all three OCI archives. Temporary extracted source/font inputs are removed; the Gotenberg OCI output **must remain private**.

**Do not run `--build` twice solely for another PASS.** If one component fails, record the exact failure; don't change release scope or call it successful.

### Independent candidate verification on the authorized private staging storage

```bash
PDFHUB_STAGE_VERIFY_KEY=/path/to/trusted/approved-public-key.pem \
  bash scripts/pdfhub-stage-signed-candidate.sh --verify /path/to/private/candidate-output/pdfhub-stage-<candidate-id>
```

Expected **only after actual successful build and verification**:

```text
PDFHUB_STAGE_OCI_PROVENANCE_PASS=api sha256:...
PDFHUB_STAGE_OCI_PROVENANCE_PASS=web sha256:...
PDFHUB_STAGE_OCI_PROVENANCE_PASS=gotenberg sha256:...
PDFHUB_STAGE_OPERATOR_SIGNATURE=PASS signer_pubkey_sha256=...
PDFHUB_SIGNED_STAGING_CANDIDATE=PASS_3_OF_3
PDFHUB_EXISTING_PRODUCTION_IMAGE_PROVENANCE=NOT_CLAIMED
PDFHUB_PRODUCTION_MUTATION=NONE
```

**Evidence handling:** Save `candidate.json`, `candidate.sig`, verified public-key fingerprint, exact staging source SHA and CI evidence in the existing HDA-06 Issue. Do not upload `api.oci.tar`, `web.oci.tar`, `gotenberg.oci.tar`, private signing key, institutional fonts, staging environment variables, or a private build-context export to GitHub. Do not claim that BuildKit provenance is itself a GitHub-issued Sigstore signature; the detached receipt is signed by the **separate operator key** and must be verified with the **trusted public key**.

**Acceptance boundary:** PASS for a new **private staging candidate** does not grant permission to load/publish it, change Production, alter 90 tools/auth/infra, or claim source provenance for the pre-existing running Production images. Further rollout requires its own approval, existing backup/rollback gates and exact Artifact/Digest checks. Stop after this gate; do not create additional QA campaigns.
