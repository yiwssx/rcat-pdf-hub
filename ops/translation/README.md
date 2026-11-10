# M05 Offline Argos / LibreTranslate — source only

**This change does not install, start, deploy or enable a model.**

M05 already supports a bounded owner-scoped API/Worker plus TXT and newly typeset
PDF outputs. This development-only optional overlay supplies a path to a real
self-hosted translation model, and a private bilingual capability probe.

## Model candidates verified in the official Argos Package Index

- English to Thai: `translate-en_th-1_9.argosmodel`
- Thai to English: `translate-th_en-1_9.argosmodel`
- LibreTranslate v1.9.6 is a version candidate, **not an approved image**.
- LibreTranslate uses AGPLv3. Package-specific licenses, provenance, data
  rights and redistribution terms must also be verified separately.
- The repo intentionally ships neither licensed model weights nor institutional
  content. No internet downloads or image pulls have been performed.

## Development-only source integration

- `compose.translation.dev.yaml` requires an explicit `m05-offline-dev`
  profile AND an approved immutable image digest in
  `PDFHUB_M05_LIBRETRANSLATE_IMAGE`; there is no default container image.
- Only combine with base `docker-compose.yml`, NOT the Production overlay;
  the Production network topology differs and needs separate review.
- The model container only joins its Docker `internal: true` network; no
  host ports, no external network, no automatic model updates.
  `worker-heavy` joins this network to use the existing fixed endpoint
  at `http://pdf-translate:5000/translate`.
- Mount `ops/translation/offline-models/` as read-only installed Argos
  package directories. These are intentionally ignored by Git.
  Raw `.argosmodel` archives must be verified and installed into the
  Argos package directory structure **before** staging, not merely copied.
- The model can fail to start if its offline packages are absent. Do not
  temporarily enable internet egress to bypass that condition.
- This source-only overlay does not turn on either M05 API/Worker or Web
  Feature Flag, change RBAC or alter the default/Production Compose files.

## Model evidence check

The module `app.services.m05_offline_model_probe` sends two fixed public
sentences only. It validates both direct language paths through
`GET /languages` and `POST /translate`, rejects empty, echo, bad JSON or
wrong-script results. It never sends real PDFs or institutional material.
Unit tests use mock HTTP transport. Passing this probe is NOT evidence of
acceptable translation accuracy or license compliance.

**Before CODE COMPLETE:** separately authorize model provisioning, verify
actual local Thai/English translations and package licenses, assess latency
and memory, and visually check Thai font shaping and PDF re-layout.
M05 stays PARTIAL. Independent QA and Production remain deferred.

Sources:
- https://docs.libretranslate.com/guides/supported_languages/
- https://docs.libretranslate.com/guides/installation/
- https://github.com/argosopentech/argospm-index/blob/main/index.json
- https://github.com/LibreTranslate/LibreTranslate/releases
