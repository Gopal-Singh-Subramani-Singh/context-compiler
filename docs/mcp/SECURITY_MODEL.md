# MCP Security Model

M9 models trust, sensitivity, instruction authority, injection signals and taint. M10a models dangerous declared capability compositions and exact approvals. M10b validates those assumptions against a bounded local real-MCP exchange.

The separation is intentional:

- protocol/server identity is provenance, not authority;
- tool output is data by default;
- `verified_tool` is not `system` or `developer` authority;
- unverified output remains `unverified_tool` with authority `none`;
- dangerous sink calls are gated before invocation;
- correspondence mismatch (`CTX445`) reduces confidence and blocks continuation;
- persistent evidence is secret-safe.
