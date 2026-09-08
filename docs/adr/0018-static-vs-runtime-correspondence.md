# ADR 0018 — Static versus runtime correspondence

## Context
Declared MCP capabilities may be incomplete or dishonest.
## Decision
Record declared/observed capabilities separately and classify match, declared-but-unobserved, mismatch, or unknown. Mismatch emits CTX445.
## Alternatives considered
Trust declarations completely; infer permanent truth from one run.
## Consequences
Observed mismatch becomes explicit evidence, not silent trust.
## Compatibility impact
Adds CTX445 only; M10a remains unchanged.
## Security impact
Observed excess capability blocks continuation.
## Testing strategy
A deliberately misdeclared bounded fixture proves the path.
