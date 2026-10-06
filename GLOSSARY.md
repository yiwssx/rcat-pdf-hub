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
