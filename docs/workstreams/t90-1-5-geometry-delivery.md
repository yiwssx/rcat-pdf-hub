# T90-1.5 M11/M28 — opt-in end-to-end engineering contract

- Implemented **M11 Crop PDF** and **M28 Resize PDF** as static allowlisted operations in a new geometry-specific API (not the existing 13-tool paths) using one explicitly OFF-by-default backend flag: `PDFHUB_GEOMETRY_TOOLS_ENABLED=false`.
- Geometry-specific owner, expiry and verified MIME checks before enqueue AND again at worker dispatch; require explicit `pdf:crop` or `pdf:resize` scopes. Neither scope is silently added to default human/service roles.
- Output PDF, original preservation and owner-scoped JobOutputArtifact follow the existing queue/scan/quota/audit/expiry/cancel/download pipeline. Worker kill switch fails queued jobs closed; unknown operation or arbitrary parameters rejected.
- Crop takes user-space PDF-point rectangle left/bottom/right/top, optionally 1-based selected pages, and changes CropBox only. **Crop does not redact content**. Coordinate origin and rotation must be understood before selecting a rectangle.
- Resize takes exact page dimensions in points, scaling independent X/Y axes. **Not aspect-ratio preserving**.
- Independent staged Web route (also OFF-by-default) never appears in the 13-tool catalog. Explicitly opt in to `PDFHUB_STAGED_GEOMETRY_WEB_ENABLED=true` and backend flag in isolated tests only.
- Binary, API scope, owner isolation, negative/invalid input, queue routing, persisted output, original immutability and feature rollback are covered by automated tests. Full authenticated production-like Docker Compose browser/mobile, matrix signoff and T90-5 rollout remain pending.
- No migration or production deployment. **No additional T90 tool is RELEASED** by code merge.
