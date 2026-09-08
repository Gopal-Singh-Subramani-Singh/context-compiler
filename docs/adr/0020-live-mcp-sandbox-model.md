# ADR 0020 — Live MCP sandbox model

## Context
A real local server process must not gain unrestricted host access during validation.
## Decision
Use a dedicated sandbox root, set child HOME to it, allow only marked fixture code, and reject absolute/traversal/symlink escapes.
## Alternatives considered
Run against real repositories/home; containers as a mandatory dependency.
## Consequences
Tests stay portable and local.
## Compatibility impact
None outside live validation.
## Security impact
Fixture file operations are path-contained; no real credentials are used.
## Testing strategy
Traversal, absolute path, symlink, source scan and synthetic-secret checks.
