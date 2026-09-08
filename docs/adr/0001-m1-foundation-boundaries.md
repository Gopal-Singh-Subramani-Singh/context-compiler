# ADR 0001: Preserve source IR and optional-dependency boundaries from M1

- Status: Accepted
- Date: 2026-08-28

## Context

Later milestones add task analysis, target-specific tokenization, security policy, caching, and
optional integrations. Placing those values on source nodes or importing optional packages at
startup would make source identity unstable and make the core unavailable in minimal installs.

## Decision

`ContextNode` is a frozen Version-2 source-fact record. `NodeAnalysis` and `SelectionResult` are
separate frozen records. Core startup uses only the Python standard library and checks optional
module availability without importing optional packages.

Canonical semantic serialization normalizes textual newlines, sorts object keys, rejects
non-finite floats, and hashes bytes with SHA-256.

## Consequences

Later passes must return separate analysis maps and selection results. Optional target adapters
must fail explicitly when their extras are missing. Schema-affecting changes require versioned
migration rather than convenience-field mutation.

