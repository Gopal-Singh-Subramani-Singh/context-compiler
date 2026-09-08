# ADR 0016 — Live MCP validation boundary

## Context
M9/M10a were intentionally static, but the project needs evidence that their assumptions correspond to a real bounded MCP exchange.
## Decision
Add a narrow optional `contextc.live_mcp` integration layer that reuses M9/M10a models and only permits marked local fixture servers.
## Alternatives considered
Generic MCP executor; bespoke JSON-RPC; no live validation.
## Consequences
Real protocol evidence without converting Context Compiler into an agent/gateway.
## Compatibility impact
Core startup remains MCP-SDK independent.
## Security impact
Arbitrary servers are rejected; sink invocation stays policy-gated.
## Testing strategy
Unit normalization/enforcement plus real stdio fixture tests.
