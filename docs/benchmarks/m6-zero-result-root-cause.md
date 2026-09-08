# M6 Zero-Result Root-Cause Analysis

## Reproduction

The controlled `01_direct_file` task deliberately stores `legacy-auth-node` as debug metadata.
The one-task report shows that this ID is absent from the current IR while both evaluator and IR
normalize to `repo://direct-file/auth.py:1-2`.

## Root cause

Node IDs are content-, source-, and revision-derived compiler identities. They legitimately change
when chunking, normalized content, source revision, or identity formats change. Treating a saved
node ID as evaluator ground truth therefore turns valid selections into false zero-recall results.
Repository authority/path spelling differences can cause the same failure before node comparison.

## Repair

Ground truth is now a union of canonical 1-based inclusive source spans. Node IDs remain in debug
reports only. Compiler `repo:///path` locations receive the public task's repository namespace
after compilation. Equal-footing checks prevent cross-strategy input drift, and evaluator labels
remain unavailable to compilation. Metrics were not loosened; the compared identity was repaired.

The report includes task text, expected URIs/spans, debug-only expected IDs, actual IR IDs and
normalized locations, plus selected IDs/spans per strategy. Tests assert the stale ID mismatch and
the canonical span match simultaneously.
