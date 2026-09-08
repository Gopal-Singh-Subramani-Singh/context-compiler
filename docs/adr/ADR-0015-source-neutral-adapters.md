# ADR-0015: Source-neutral adapters for cross-domain compilation

- Status: Accepted
- Milestone: M15
- Date: 2026-09-03

## Context

The repository parser had become the practical entry point to the compiler. M15 must prove that
repository syntax is an adapter concern rather than a compiler invariant, while preserving M4
reproduction, M5 optimization, M9 security, and M11 behavior.

## Decision

Introduce a small `SourceAdapter` boundary returning universal `IndexResult` and `ContextGraph`
structures. Keep `CompileRepositoryRequest` as a backward-compatible request name, add the
source-adapter identity to semantic inputs, and route both repository and incident compilation
through the same prepare/analyze/select/lower/reproduce pipeline.

Structural supersession and conflict analysis operate on universal graph edges, not incident file
names. Incident evaluator labels stay outside the adapter and compiler.

## Consequences

- Existing repository call sites remain valid.
- M15 can compile heterogeneous incident sources without optimizer or security forks.
- Reproduction stores `source_adapter_id`, so rebuild reopens the correct source domain.
- Future adapters must satisfy deterministic provenance and graph contracts.
- Incremental caching in M8 can key on the same source-neutral boundary.
