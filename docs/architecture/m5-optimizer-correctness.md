# M5 Optimizer Correctness

M5 defines selection once and makes every strategy operate on that same model. `SelectionProblem`
validates graph/analysis identity, target-token costs, source-content allowance, mandatory nodes,
blocked and policy-eligible nodes, and transitive dependency closure before strategy-specific
logic runs. It also owns the canonical objective, exact selected-set evaluation, deterministic
tie key, ordering, and final constraint validation.

## Objective and constraints

`ObjectiveWeights` schema 1.0 has bounded, finite weights for positive relevance, trust,
freshness, and dependency coverage, plus negative redundancy and security-risk penalties. The
complete optimizer configuration enters the pipeline identity and reproduction inputs.
Benchmark labels or ground-truth rewards are never read from node metadata.

Dependencies are only edges configured by `ContextGraph.dependency_edge_types`. Closure is
transitive, shared dependencies are charged once, and support/conflict/supersession edges do not
force inclusion. Mandatory closure is reserved before optional decisions. A blocked mandatory
dependency or mandatory cost above allowance produces `INFEASIBLE` with CTX530 evidence.

## Strategies and guarantees

The common `SelectionStrategy` contract has nine implementations:

- `naive`, `recency`, `relevance_greedy`, `density_greedy`, and
  `graph_closure_greedy` are deterministic heuristics;
- `top_k` requires actual stored semantic scores and otherwise records a fallback rather than
  relabeling lexical relevance;
- `brute_force` is the bounded small-instance oracle;
- `dynamic_programming` is exact only for its bounded dependency-free formulation; and
- `ilp` uses optional PuLP/CBC and reports optimality only when the solver proves it.

A feasible incumbent after an ILP timeout is `FEASIBLE_TIMEOUT`; no incumbent, missing solver,
solver failure, or an unsafe exact-method bound yields explicit CTX520 fallback evidence. The
central `choose_optimizer` cascade selects small brute force, safe DP, bounded available ILP,
dependency-closure greedy, or density greedy in that order.

## Determinism and reproduction

The shared tie key sorts by descending utility and relevance, ascending target cost, source URI,
source start/end line, and node ID. No strategy depends on insertion order, set iteration,
built-in hashes, solver return order, or randomness. Tie evidence is bounded to 64 entries.

The schema-1.1 manifest records requested and used strategy, version, status, objective, measured
runtime, configured timeout, fallback reason, selected/excluded/forced/mandatory IDs, and tie
trace. Runtime is operational evidence and is excluded from `build_id`; all semantic optimizer
configuration and outcomes remain identity-bearing, preserving deterministic M4 rebuilds.
