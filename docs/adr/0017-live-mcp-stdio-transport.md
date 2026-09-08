# ADR 0017 — Stdio transport for M10b

## Context
M10b needs a real transport with zero public-network dependency.
## Decision
Use the maintained MCP Python SDK over stdio first.
## Alternatives considered
Local HTTP; custom wire protocol; external hosted MCP.
## Consequences
The SDK owns protocol framing/lifecycle; the server is a local child process.
## Compatibility impact
Live MCP is an optional extra.
## Security impact
No listener and no external network are required.
## Testing strategy
Lifecycle/discovery/read/call/timeout/shutdown tests on the tiny server.
