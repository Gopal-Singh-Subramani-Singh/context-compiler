# M2 Core IR and Compiler Invariants

M2 establishes stable semantic boundaries without adding target-token or optimizer claims.

```text
static repository index
  -> immutable source-neutral ContextNode records
  -> deterministic typed ContextGraph
  -> task-specific NodeAnalysis map
  -> immutable CompilationUnit
  -> SelectionStrategy protocol
  -> stored SelectionResult evidence
  -> Generic lowering / stored node explanation
```

## Graph semantics

- Public node and edge order is explicit and independent of insertion order.
- Identical edges are idempotent; semantically distinct parallel edges are retained.
- All current edge relationships reject self-edges.
- `IMPORTS`, `CALLS`, and `REQUIRES` are dependency relationships by default.
- Conflict, support, supersession, taint, and other relationships do not enter dependency
  closure unless a future configuration explicitly changes the dependency set.
- Dependency edges point from a dependent node to the node it depends upon.
- Topological dependency order places dependencies before dependents.
- Cycles are reported as stable strongly connected node components. Inspection remains usable,
  while acyclic-order requests raise a typed `DependencyCycleError` carrying CTX320 evidence.

## Schema policy

Semantic artifacts carry structured `{major, minor}` versions. Unsupported majors and minors
outside an explicit compatibility allowlist raise `SchemaVersionError` with CTX720. The M1
integer-major representation can only be converted through the named
`migrate_legacy_major_version` function; deserializers never coerce it silently.

## Source normalization

CRLF and bare CR line endings normalize to LF. Other whitespace, including trailing spaces and
the presence or absence of a final newline, participates in content identity.

## Bounded baseline

`DeterministicBaselineSelection` selects mandatory and positive-relevance seeds, closes only
configured dependencies, and records exclusions, forced inclusions, ordering trace, diagnostics,
and deterministic sentinel runtime evidence. It does not enforce exact target budgets or claim
optimization.
