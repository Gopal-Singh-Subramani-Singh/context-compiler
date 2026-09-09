# M15 Worked Example — Checkout Latency Incident

The packaged `checkout-latency-001` demo is a deterministic offline incident-response fixture with
21 retained source files producing 22 IR nodes and 12 typed graph edges.

At the default 4000-token `structured-json` budget, `relevance_greedy` selects evidence covering:

- the active incident report;
- checkout deployment timing and deploy manifest;
- checkout latency, error-rate, and cache-hit observations;
- service ownership / on-call handoff evidence;
- the current rollback procedure;
- the operations conversation;
- the malicious retained MCP result, transformed by M9 security.

The explicit `SUPERSEDES` edge from rollback v1 to rollback v2 emits `CTX210`; rollback v1 is
ineligible and consumes no final target budget. A normal database-CPU observation contradicts the
database-saturation hypothesis through `CONTRADICTS` and yields non-blocking `CTX200` evidence.

The malicious MCP source keeps `instruction_authority=none`, emits M9 `CTX400`, `CTX420`, and
`CTX425`, and is rendered as quoted source data. M15 does not perform capability analysis and does
not emit `CTX440`.

The same M4 manifest can then be verified and deterministically rebuilt. The M15 demo service also
runs the unchanged M5 strategy registry against a shared prepared analysis and evaluates outputs
only after compilation using isolated evaluator labels.
