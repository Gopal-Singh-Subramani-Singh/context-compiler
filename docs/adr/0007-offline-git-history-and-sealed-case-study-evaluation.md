# ADR 0007: Offline Git History and Sealed Case-Study Evaluation

- Status: accepted
- Date: 2026-09-03

## Context

M11 needs real pre-fix repository states and genuine fix evidence while preserving offline use,
reproducibility, evaluator isolation, and the rule that repository code is never executed during
indexing. Hand-recreated snapshots would weaken provenance, and fetching GitHub during each run
would make network state part of the benchmark.

## Decision

Package a complete, SHA-256-pinned Git bundle of the MIT-licensed python-humanize repository.
Materialize full revisions only into temporary detached checkouts. Require every fix to have the
recorded pre-fix revision as its single parent, and require changed files and labeled source spans
to validate against Git and the pre-fix tree.

Keep public task loading separate from evaluator label and review loading. Compile all compared
strategies from one sealed static index and analysis map before opening evaluator files. Reuse M5
selection, M6 equal-footing fingerprints, M6 metrics, and M6 SQLite storage unchanged at the
case-study boundary.

## Consequences

- Historical runs are offline and tied to exact upstream objects.
- The reference bundle adds approximately one megabyte to the distribution and requires a local
  Git executable for M11 commands.
- Task review remains explicit human evidence; extraction tooling cannot approve labels.
- Results are reproducible and auditable but remain bounded to eight tasks in one repository.
- Physical creation-order determinism can be tested using temporary reordered copies without
  mutating the reference source.
