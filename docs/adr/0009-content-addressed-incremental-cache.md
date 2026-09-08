# ADR 0009: Content-addressed incremental cache with verified clean-build equivalence

## Decision

Use a local content-addressed store keyed by narrow semantic stage identities, with explicit dependency/source indexes and a clean-build equivalence checker.

The cache is an optimization only. It never becomes an authority for source truth, policy interpretation, selection, target budget validation, or reproduction.

## Consequences

A no-op build can reuse parse/security/supersession/token/analysis intermediates. A one-source edit recomputes the aggregate parse graph but retains source fingerprints and per-node target/task results for unchanged nodes whose semantic identities remain valid. Budget/task/policy/target changes invalidate only the stages whose semantic inputs changed.

Cache deletion cannot break M4 reproduction. Corrupt entries are rejected and quarantined. Remote/distributed caches, watchers, daemons and cache garbage collection remain out of scope.
