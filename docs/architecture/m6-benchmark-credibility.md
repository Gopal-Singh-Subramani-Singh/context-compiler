# M6 Benchmark Credibility

M6 evaluates canonical repository locations, not content-derived node IDs. Public task input and
evaluator labels are physically separated as `public/task.yaml` and `evaluator/labels.yaml`.
`compile_public_task` belongs to the public-input runner and neither imports nor accepts ground
truth. Only the evaluator module attaches labels after compilation completes.

## Canonical identity and spans

Evaluator locations use `repo://<repository-id>/<path>`. Compiler-local `repo:///path` values are
namespaced after compilation. Dot and repeated-slash spellings normalize; traversal, encoded,
backslash, whitespace, query, fragment, credential, and ambiguous authority forms are rejected.
Line spans are 1-based inclusive. Required and selected overlaps are unioned as `(URI, line)` units,
so overlapping chunks cannot double-count recall.

The equal-footing fingerprint covers task, revision, graph, analysis, target/tokenizer, budget,
fixed overhead, effective source allowance, objective, optimizer limits, dependency policy,
requirements, policy, and random seed. It excludes only strategy identity and evaluator labels.
Cross-strategy comparison fails if task, fingerprint, or evaluator-label identity differs.

## Ten raw metrics

No headline score replaces these fields:

1. Required-file recall: selected required files / required files.
2. Required-file precision: selected files accepted by required or accepted spans / selected files.
3. Required-span recall: unioned selected required line units / unioned required line units.
4. Dependency-closure coverage: evaluator-required relations with both endpoints represented.
5. Useful-token ratio: first coverage of accepted line units / selected source tokens.
6. Redundant-token ratio: repeated coverage of already-covered accepted lines / source tokens.
7. Unsupported-context ratio: tokens allocated to lines outside accepted regions / source tokens.
8. Budget utilization: exact final emitted target tokens / configured final target budget.
9. Compilation latency: `perf_counter` around compilation only; fixture setup/evaluation excluded.
10. Optimizer runtime: the selection strategy's stored solver runtime.

Target-specific per-node optimizer token cost is allocated evenly over its inclusive source lines.
Each selected location is processed in final render order. A useful line is useful on first
appearance, redundant on later appearances, and unsupported when outside all accepted spans.
With no selected source tokens, useful ratio is `1.0` (no useful budget was wasted) and redundant
and unsupported ratios are `0.0`. Empty required sets have recall `1.0`; empty selected sets have
file precision `1.0`. Runtime fields are operational and excluded from benchmark run identity.

## Evidence and persistence

SQLite schema version 1 has `benchmark_runs`, `benchmark_metrics`,
`benchmark_selected_nodes`, and `top_k_candidates`. Writes use parameters and one transaction.
An identical semantic run ID is idempotent and keeps the first runtime observation; a conflicting
payload for the same ID is rejected. Evaluator sentinel text is never persisted—only its canonical
label identity is stored.

Top-K traces contain the public query, immutable embedding identity, ordered candidates and
scores, selection/removal decisions, and evaluator overlap attached afterward. When embeddings
are absent, the trace stores fallback status and zero candidates rather than fabricated retrieval.

The controlled suite contains eight physical tasks: direct match, dependency chain,
distractor-heavy, duplicate-heavy, tight budget, configuration dependency, conflict-bearing, and
infeasible mandatory selection. Raw reports preserve every task/strategy row.
