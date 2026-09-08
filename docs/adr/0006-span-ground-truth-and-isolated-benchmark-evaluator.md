# ADR 0006: Span ground truth and an isolated benchmark evaluator

## Status

Accepted for M6.

## Context

Compiler node IDs are stable only for identical content, provenance, revision, and chunking.
Benchmark labels tied to those IDs can silently report zero coverage after a legitimate compiler
change. Evaluator labels also risk contaminating retrieval and optimization if loaded too early.

## Decision

Authoritative labels are canonical repository URIs plus inclusive line spans. Public task loading,
compilation, and evaluator loading are separate modules and physical task directories. Compilation
finishes before labels are opened. One explicit fingerprint proves equal semantic compiler inputs
across strategies. Runtime observations are stored but excluded from semantic run IDs.

Benchmark evidence uses a versioned normalized SQLite schema and exposes raw rows. Top-K overlap
is attached only after retrieval. Missing embeddings produce M5 fallback evidence and no invented
candidates.

## Consequences

Results survive node-ID and chunking changes when the same source lines remain authoritative.
Span granularity and proportional token attribution are visible limitations rather than hidden in
a composite score. The evaluator cannot optimize against its own labels, and comparisons with
different fingerprints fail instead of producing misleading tables.
