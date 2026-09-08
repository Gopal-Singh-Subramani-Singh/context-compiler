# ADR 0021 — Semantic reproduction for live MCP

## Context
Process timestamps and durations make byte-identical runtime traces inappropriate.
## Decision
Compare a semantic form excluding duration/cache hit/runtime path while retaining declarations, static decisions, observations, correspondence, blocked sinks and containment outcomes.
## Alternatives considered
Byte-identical runtime logs; no reproduction model.
## Consequences
Deterministic claims are limited to semantics rather than wall-clock operations.
## Compatibility impact
M4 byte reproduction remains unchanged for compiler artifacts.
## Security impact
Semantic evidence avoids persisting unnecessary runtime details.
## Testing strategy
Repeated fixture/fake runs compare semantic forms and declaration hashes.
