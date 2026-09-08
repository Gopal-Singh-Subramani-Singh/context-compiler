# ADR 0003: Recount complete configured targets and trim closure-safe clusters

- Status: Accepted
- Date: 2026-08-29

## Context

Pre-render node counts cannot include target chat templates, role markers, source annotations,
policy/tool text, special tokens, or generation prompts. Treating those counts as final would
permit successful artifacts to exceed the requested model budget. Substituting a Generic
estimate when a model tokenizer is unavailable would make the result look valid under the wrong
token semantics.

## Decision

Each target lowerer receives typed inputs and a tokenizer with recorded semantic identity. Qwen
and Llama render through the actual configured tokenizer chat template; optional dependencies and
models load lazily and failure is explicit. The full final string is counted with the same
tokenizer after every render.

If it exceeds budget, a bounded deterministic pass removes optional dependency-safe clusters,
re-renders, and recounts. Mandatory nodes and their dependency closure remain protected.
Selection evidence is not mutated; trim evidence is stored separately. Only a fully successful
render may atomically replace the output file.

## Consequences

Successful target packages carry a hard target-budget guarantee and complete tokenizer,
budget, trim, and source-map evidence. Fixed overhead reporting can guide the M5 optimizer but
cannot replace final validation. Model-specific compilation requires the configured optional
runtime and may fail offline if the requested tokenizer is not already available. M4 now records
this evidence in a strict transactional manifest and verifies/rebuilds it without altering M3
selection or trim semantics.
