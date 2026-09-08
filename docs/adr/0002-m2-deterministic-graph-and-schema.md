# ADR 0002: Use explicit schema families and deterministic standard-library graph semantics

- Status: Accepted
- Date: 2026-08-28

## Context

M2 must stabilize source, analysis, graph, compilation, selection, and explanation contracts.
Depending on incidental container iteration or silently coercing version fields would make
identities and rebuild evidence unreliable. Adding NetworkX to the core would also add a runtime
dependency without being necessary for the required semantics.

## Decision

Semantic artifacts use structured major/minor schema versions with explicit compatibility
allowlists and an explicit M1 integer-major migration function. A standard-library typed
multigraph stores nodes and deterministic edge identities while every public operation sorts by
documented semantic keys.

Dependency closure uses a configured relationship subset. Cycles are exposed as deterministic
strongly connected components, and only APIs requiring acyclicity fail when cycles exist.
Explanation generation consumes stored graph, analysis, selection, and diagnostic evidence;
terminal formatting is a separate operation.

## Consequences

The core remains dependency-free and offline-capable. Parallel edges require distinct semantic
evidence, identical duplicates are idempotent, and unsupported schemas fail before a graph is
returned. Later target, optimizer, reproduction, and cache milestones must consume these
contracts rather than adding state to source nodes.
