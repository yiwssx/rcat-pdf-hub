# M05 Offline Argos / LibreTranslate — source only

**This change does not install, start, deploy or enable a model.**

M05 already supports a bounded owner-scoped API/Worker plus TXT and newly typeset
PDF outputs. This development-only optional overlay supplies a path to a real
self-hosted translation model, and a private bilingual capability probe.

## Model candidates verified in the official Argos Package Index

- English to Thai: `translate-en_th-1_9.argosmodel`
- Thai to English: `translate-th_en-1_9.argosmodel`
- The exact LibreTranslate Docker digest was exercised on isolated CI in PR #368; it is **not a Production-approved deployment image**.
- LibreTranslate and MiniSBD are AGPLv3; the Argos maintainer confirmed `.argosmodel` binaries MIT/CC0 in https://github.com/argosopentech/argos-translate/issues/533 (Aug 2, 2026). Package metadata itself has no license field. Third-party training-data and redistribution obligations remain subject to operator review.
- No model weights or RCAT documents are committed. Disposable CI downloaded fixed public model binaries and pinned SHA-256. No on-premise installation, Production image pull or model service activation was performed.

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
- Mount `ops/translation/offline-minisbd/` with `en.onnx` and `th.onnx`, downloaded from the pinned MiniSBD v0.0.1 release, hash-verified per the CI script; these are both required and mounted read-only. The Compose profile provides only disposable writable caches. Never fall back to internet downloads in the private network.
- The model can fail to start if its offline packages are absent. Do not
  temporarily enable internet egress to bypass that condition.
- This source-only overlay does not turn on either M05 API/Worker or Web
  Feature Flag, change RBAC or alter the default/Production Compose files.

## Model evidence check

The module `app.services.m05_offline_model_probe` sends two fixed public
sentences only. It validates both direct language paths through
`GET /languages` and `POST /translate`, rejects empty, echo, bad JSON or
wrong-script results. It never sends real PDFs or institutional material.
Unit tests use mock HTTP transport; independent disposable [real-model PR #368](https://github.com/yiwssx/rcat-pdf-hub/pull/368) also installs both Argos model binaries plus two MiniSBD ONNX splitters on an offline Docker internal network, asserts real bilingual translations using public agricultural sentences and checks no source PDF is sent. Output is clearly machine translation and Thai spacing remains imperfect. This is not institution-specific translation quality or Production acceptance.

**Engineering MAC:** authentic isolated bilingual model and source-grounded proof may justify CODE COMPLETE *for selectable-text machine translation only*, after exact-head protected PR checks and merge. Installed host model, institutional review, performance/Thai typography, licensing notices, security/DR and real-user QA remain Production acceptance gates; flags stay OFF. Never conflate a disposable CI image with an installed RCAT model.

Sources:
- https://docs.libretranslate.com/guides/supported_languages/
- https://docs.libretranslate.com/guides/installation/
- https://github.com/argosopentech/argospm-index/blob/main/index.json
- https://github.com/LibreTranslate/LibreTranslate/releases
