# Validation Evidence

## Release baseline

Certified v0.18.0 engineering baseline included:

- 364 tests passing
- 85.50% coverage
- Ruff pass
- `ruff format --check` pass across 289 files
- strict mypy pass across 164 source files
- 4 packaged offline demos
- frozen dependency-complete environment validated
- core/UI isolation tests passing
- Streamlit Observatory AppTest with zero exceptions and all four demo cards

## 20-scenario production-oriented campaign

The campaign was designed to build end-to-end confidence, not to claim universal production readiness.

### Batch 1 — repository, graph, conflict, supersession

1. focused repository bug
2. multi-file dependency chain
3. large repository with budget/noise pressure
4. conflicting evidence
5. superseded guidance

Result: **5/5 pass**.

### Batch 2 — static security and capability policy

6. untrusted document injection
7. static MCP instruction flow
8. sensitive-to-external flow
9. dangerous static capability composition
10. exact approval vs non-overridable hard block

Result: **5/5 pass**.

### Batch 3 — real live MCP enforcement

11. real stdio lifecycle + safe public read
12. secret to external-message pre-sink block
13. untrusted content to execution pre-sink block
14. credential to network hard block
15. observed-vs-declared capability mismatch (`CTX445`)

Result: **5/5 pass**.

The live-MCP regression module also passed 11/11 tests. Safety counters for real external network, messages, shell commands, credentials, secret leaks and orphan processes were all zero in the bounded fixture.

### Batch 4 — incremental, reproduction and local model

16. unchanged incremental warm-cache reuse
17. one-source selective invalidation and restoration
18. deep dependency invalidation
19. reproduction and tamper detection
20. local Ollama A/B under approximately equal prompt-token pressure

B4-16, B4-17, B4-19 and B4-20 passed directly.

B4-18's original acceptance harness contained one over-specific assertion requiring non-leaf `token_count` or `analysis` recomputation. The original failure was preserved. A predeclared V2 adjudication then made a real deepest-leaf content change and validated dependency closure, global dependency-sensitive recomputation, incremental/full equivalence, clean-build byte identity, cache validity and source immutability. V2 passed.

Final campaign status: **20/20 adjudicated scenario passes**.

## Local Ollama A/B

Final bounded run:

```text
Model: llama3.2:3b
Temperature: 0
Seed: 42
num_predict: 500
Raw prompt tokens: 1468
Context Compiler prompt tokens: 1472
Raw checklist: 7/7
Context Compiler checklist: 7/7
```

The Context Compiler path additionally demonstrated pre-inference security diagnostics (`CTX400`, `CTX420`, `CTX425`), supersession (`CTX210`), provenance and reproduction evidence.

Do not infer accuracy or latency superiority from this one run.

## Defensible release claim

> v0.18.0 is a production-oriented, end-to-end validated compiler prototype/release candidate with 20/20 adjudicated validation scenarios passed.

## What remains unproven

The campaign does not establish:

- broad multi-OS support
- fuzzing coverage
- long-duration soak/stress behavior
- resource-exhaustion/crash-recovery behavior
- complete dependency/security scanning
- arbitrary third-party MCP ecosystem compatibility
- universal model quality or latency improvements
