# ADR-0001: Deepen the Tool Workspace module

- Status: Accepted
- Date: 2026-10-06

## Context

The V3 Workspace accumulated tool-specific state in `PdfHubApp`: watermark settings, page-number settings, image conversion settings, signed-link state, stamp settings, merge ordering, and payload construction. The same state was forwarded through a very wide `ToolPanel` interface.

This made the application shell shallow: callers had to know details that only the active document tool needed. It also increased the blast radius of adding or changing a tool option.

## Decision

Introduce `ToolWorkspace` as the stable seam between the application shell and tool implementation.

`PdfHubApp` remains responsible for authenticated workspace concerns: selected file, global jobs, global busy/message state, downloads, retention, and API job registration.

`ToolWorkspace` owns transient tool configuration and translates that configuration into operation payloads. The existing `ToolPanel` remains an internal presentation implementation behind this seam.

The application shell interacts with the Tool Workspace through a small interface:

- current tool and selected file context
- available PDF/image files
- integration status and busy state
- submit-job callback
- signed-link callback
- archive callback
- status-message callback
- close callback

Heavy admin and tool modules are loaded dynamically because they are not required for the initial Workspace path.

## Consequences

- Adding a new tool option no longer requires adding state and setter props to `PdfHubApp`.
- Job payload rules live next to the tool configuration that produces them.
- The application shell becomes easier to understand and test.
- Tool settings are stored as one opaque snapshot by the application shell so reopening a tool preserves the existing user experience without exposing individual fields to the shell.
- The internal `ToolPanel` interface is still broad, but it is no longer an application-wide seam. It can be simplified later without touching the shell.

## Validation

Browser regression coverage must verify at least one stateful tool payload end-to-end. Existing smoke tests continue to validate navigation, previews, job handling, downloads, uploads, file routes, organizer behavior, and admin login.
