# ADR 0008: Run security before task analysis while preserving raw source evidence

## Status

Accepted for M9.

## Context

Security actions can quote, redact, exclude, or block source material. Quote/redact changes token
cost, while exclusion must interact correctly with dependency closure. At the same time, M4
reproduction needs source identities derived from the actual repository rather than from a
security-transformed derivative.

## Decision

Run deterministic M9 security analysis immediately after graph construction and before task
analysis/token costing. Preserve the raw graph as source evidence and create a derived
post-security graph for downstream analysis. Retain excluded nodes structurally but mark them
optimizer-ineligible. Abort blocked results before artifact transaction staging.

Store the canonical security policy plus secret-safe decision/taint/transformation/token evidence
in the build manifest. Rebuild reconstructs that policy and requires the fresh security semantics
and bytes to match the stored build.

## Consequences

- Optimizer costs correspond to transformed content rather than stale pre-security text.
- Dependency closure cannot silently bypass an exclusion.
- Source verification remains anchored to repository bytes.
- Blocking is transactional by construction.
- Stored explanation can report security effects without recomputation.
- Manifest schema advances because security evidence is semantic build state.
