# ADR 0019 — Enforcement before live sink invocation

## Context
Static diagnostics are insufficient if a client can bypass them and invoke a sink directly.
## Decision
Centralize ALLOW/REQUIRE_APPROVAL/BLOCK between M10a analysis and fixture invocation. Exact M10a approvals are reused.
## Alternatives considered
Per-tool policy checks; execute then audit.
## Consequences
Dangerous sources may be observed while unsafe sinks remain uncalled.
## Compatibility impact
No M10a policy semantic change.
## Security impact
Pre-sink blocking is transactional at the operation boundary.
## Testing strategy
Ledger assertions for external/execution/network sinks.
