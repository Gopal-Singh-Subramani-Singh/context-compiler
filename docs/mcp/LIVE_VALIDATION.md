# Live Tiny MCP Validation (M10b)

M10b validates Context Compiler's existing M9 trust/security and M10a capability analysis against a real, local, bounded MCP protocol exchange. It is an integration-validation layer, not a production MCP gateway.

## Architecture

```text
official MCP Python SDK (optional live-mcp extra)
  -> real local stdio child process
  -> LiveMCPClientAdapter
  -> normalized tool/resource snapshots
  -> existing M10a ToolDeclaration / ResourceDeclaration
  -> existing M10a plan analysis
  -> M10b enforcement gate
  -> only explicitly allowed bounded fixture tool calls
  -> runtime observations
  -> existing M9 ContextNode trust/security scan
  -> declaration/runtime correspondence + CTX445
  -> secret-safe audit/report evidence
```

Core Context Compiler startup does not require the MCP SDK. Install `context-compiler[live-mcp]` (or the development extras) to use live validation.

## Transport and server

M10b supports **stdio only**. The client launches a marked local fixture server as a subprocess through the maintained MCP SDK. The CLI refuses arbitrary unmarked server files. The child receives a constrained environment and a sandbox HOME.

The fixture exposes nine intentionally small tools: the eight required safe/fake-sink tools plus one deliberately misdeclared reader used for correspondence testing. It exposes three resources backed only by sandbox files.

## Sandbox and synthetic data

Every fixture run uses a dedicated sandbox. Path handling rejects absolute paths, parent traversal, and resolved symlink escapes. The fixture never reads the real HOME, Desktop, SSH/AWS/config directories, browser profiles, or real credentials.

Synthetic sentinels are:

- `CONTEXTC_TEST_SECRET_7F31`
- `CONTEXTC_TEST_CREDENTIAL_A91C`
- `CONTEXTC_TEST_INTERNAL_RECORD_C442`

Persistent observations/audit/cache evidence stores hashes, byte counts, generic sentinel-presence flags, sensitivity, trust, and diagnostics rather than raw secret values.

## Static vs runtime

M10a answers: **what could this declared composition do?**

M10b answers: **for this bounded fixture, did observed behavior align with the declarations, and did enforcement stop unsafe sinks before invocation?**

A declared capability that is not exercised is `declared_but_unobserved`, not disproven. Behavior that exceeds a declaration is `observed_mismatch`, emits `CTX445`, and blocks subsequent execution.

## Enforcement

The live plan path is:

```text
proposed plan
  -> live declaration discovery
  -> M10a static analysis
  -> M10b sink gate
  -> ALLOW / REQUIRE_APPROVAL / BLOCK
  -> bounded fixture invocation
```

Dangerous source calls may run so their runtime behavior can be validated, but a protected sink cannot run until the exact M10a flow requirements are satisfied. Hard-block rules remain hard blocks. Approval evidence reuses the M10a typed, flow-scoped approval model.

## Required demonstrations

- public read: allowed and observed as `LOCAL_FILE_READ`;
- public read -> local write: allowed inside sandbox;
- secret read -> fake external message: source may run, sink is stopped before the outbound ledger changes without approval;
- untrusted text -> fake execution: execution ledger remains empty without approval;
- credential -> fake network: network ledger remains empty under the configured hard block;
- misdeclared reader: `CTX445`, observed mismatch, future operation blocked.

The fake outbound, execution, and network sinks only append to sandbox ledgers. They make no network request and spawn no shell.

## Cache semantics

M8 caching is reused only for **static** declaration/capability analysis. The M10b cache namespace includes server identity and fixture semantic version; M10a's key includes normalized tool/resource declarations, policy, plan, approvals, limits and pass version. Runtime observations remain run-specific evidence and are not cached as timeless truth.

Temporary sandbox paths are excluded from normalized declaration hashes.

## Audit and explanation

Plan execution returns auditable events with plan/server/transport/tool, arguments hash, result hash, sensitivity/trust, static decision, approval state, invocation attempted/performed, policy identity, diagnostics, duration and error fields. Raw secret payloads are excluded.

`contextc mcp live explain RESULT.json --json` explains stored evidence only and never reruns MCP tools.

## Determinism / semantic reproduction

Operational duration/process lifecycle is not byte-reproducible. M10b therefore defines semantic forms that exclude cache-hit status and runtime duration while retaining server/declaration identity, static policy result, observed capability/sensitivity identities, correspondence, blocked/invoked calls, diagnostics and containment outcomes.

## Failure posture

Live operations have bounded timeouts and typed connection, initialization, discovery, read, invocation and timeout errors. SDK absence produces the standard optional-dependency error with installation guidance rather than a raw traceback.

## Telemetry

Telemetry: **none**.

## Limitations

M10b validates a bounded local fixture server, not arbitrary MCP servers. Observing one scenario is not proof of future behavior. Static declarations may be dishonest. There is no OAuth/OIDC, internet-facing MCP server, production external write, real shell execution, real credential access, autonomous planning, or production enforcement proxy. M10b is not a full MCP conformance suite.
