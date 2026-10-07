# Domain Glossary

## Workspace
The authenticated user-facing area where files, processing jobs, previews, and document tools are coordinated.

## Tool Workspace
The module that owns transient configuration for one document-processing tool session and translates user choices into PDF Hub job payloads. The application shell supplies identity, selected files, integration status, and a small set of callbacks; it does not own individual tool form fields.

## Job
An asynchronous document-processing request submitted to the API. Jobs expose operation, status, progress, input files, and an optional output file.

## Service Key
A machine-to-machine credential used by external systems. Human browser access uses authenticated sessions instead of Service API Keys.

## Integration
An optional external capability exposed to the Workspace, such as Paperless archival, LDAP/OIDC authentication, or storage/observability backends.

## Human Role
An explicit authorization role for browser users. `viewer` is read-only, `operator` receives the configured human workflow scopes, and `admin` receives administrative wildcard access. Institutional groups select roles through fail-closed mappings.

## Workload Queue Class
The scheduling class for asynchronous document jobs: `interactive`, standard `pdf`, or `heavy`. Each class maps to one RQ queue and a dedicated worker pool/time-out policy.

## File Library Query
The server-side search/filter/sort/pagination contract used by the dedicated Files route. It returns a bounded page plus total count rather than requiring the browser to preload the complete library.

## Storage Reconciliation
A read-only comparison between database file metadata and managed local/NAS or self-hosted S3 objects. It reports missing, orphaned, duplicate or size-mismatched objects and never repairs/deletes automatically.

## Release Readiness
The repository release gate. Code mode validates repository state and source supply chain; production mode additionally requires local-CI enforcement, production image scanning, verified backup, isolated DR drill and target load/latency smoke.
