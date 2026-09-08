# ADR 0005: One Selection Problem and Honest Optimizer Status

- Status: accepted
- Date: 2026-08-31

## Decision

All optimizers consume `ContextGraph`, the complete `NodeAnalysis` mapping, and an immutable
`CompilationUnit` containing `OptimizerConfiguration`. `SelectionProblem` exclusively owns the
objective, constraints, closure semantics, costs, stable tie key, selected-set evaluation, and
result validation.

Exact strategies may emit `OPTIMAL` only inside their proven formulation and bounds. Timed-out
feasible ILP incumbents use `FEASIBLE_TIMEOUT`. Strategy substitution uses `FALLBACK` with CTX520
and a reason. Mandatory infeasibility uses `INFEASIBLE` with CTX530. Heuristic success uses
`HEURISTIC`.

## Consequences

Strategies cannot quietly solve different problems or bypass policy and dependency checks.
Brute force can serve as an executable oracle for DP and ILP fixtures. Solver availability and
resource bounds are observable decisions rather than hidden environment-dependent behavior.
Measured runtime remains useful operational evidence but is not part of reproducible build
identity.
