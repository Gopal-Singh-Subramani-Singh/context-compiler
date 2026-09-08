# ADR 0010: Analyze declared capability composition before execution

## Status

Accepted for M10a.

## Context

M9 can classify and taint retained tool-result content, but it cannot answer whether a proposed
sequence of declared tools could read a protected resource and later send it externally, or feed
untrusted output into privileged execution. Runtime MCP invocation is intentionally outside the
current product boundary.

## Decision

Add a separate static capability-analysis pass over declared tools, resources, a proposed ordered
call plan, a versioned capability policy, and explicit approval evidence. Reuse M9 trust and
sensitivity enums and the reserved CTX440-CTX444 diagnostics. Build deterministic bounded flow
paths and store only secret-safe evidence. Flow approvals are exact-identity inputs rather than an
analyzer boolean. Cache the capability stage through M8 semantic content-addressed keys.

Do not execute or contact tools as part of analysis.

## Consequences

The compiler can reject or require approval for dangerous declared compositions before runtime
without claiming that declarations prove real behavior. Incomplete declarations remain unsafe by
default. M9 content-flow and M10a capability-flow diagnostics stay distinct. A later runtime
gateway could consume this evidence, but M10a itself is not that gateway.
