# M10a static MCP capability composition

M10a analyzes the declared security implications of a proposed MCP-style call chain before any
call is executed. It is static declaration/plan analysis, not a runtime policy gateway and not a
prediction of actual tool behavior.

## Reused foundations

The analysis reuses M9 `TrustDomain` and `Sensitivity`, the existing CTX440-CTX444 diagnostic
registry, M8 content-addressed cache keys, and source-neutral application-service boundaries.
It does not create a second trust or security model. M9 and M10a answer different questions:

- M9: what content, sensitivity, and instruction authority is flowing through retained context?
- M10a: what could the declared sequence of tools do with declared resources and outputs?

A M10a finding never replaces a M9 CTX410/420/425/430 finding.

## Static declarations

Tool declarations include server/tool identity, trust domain, capabilities, resources read/written,
possible output sensitivity, side-effect status, execution/network flags, and declaration
completeness. Resource declarations independently carry resource kind, sensitivity, trust/owner
metadata, and allowed sinks/actions. Missing required declaration evidence emits CTX441 and a used
incomplete declaration blocks the proposed plan by default.

Capabilities are declarations, not proof of runtime behavior. M10a never opens a network
connection, discovers an MCP server, authenticates, invokes a tool, executes shell/code, or reads a
declared protected resource.

## Plans, graph, and flows

A plan contains an ordered list of call IDs, tool IDs, literal inputs, resource bindings, bindings
to prior call outputs, and requested approval identifiers. CTX442 covers duplicate/unknown call
references, forward/cyclic bindings, unsupported schema versions, unknown tools/resources, and
missing structural fields.

The deterministic capability graph contains resource, tool, call, output, capability, and binding
edges. Bounded provenance propagation builds ordered `CapabilityFlow` evidence without retaining
payload content. The default limits are eight call steps and 64 reported flows.

The required high-risk compositions are:

- sensitive/secret data to external, network, or message write;
- untrusted output to shell/code execution;
- credential/environment access to network send.

The first two require explicit trusted approval under the packaged policy. Credential/environment
to network send is blocked by default.

## Approval evidence

Approval is a separate immutable input scoped to one exact flow identity and plan ID. The analyzer
accepts it only from policy-trusted approval domains and records only its semantic identity. An
approval for one flow does not approve another flow. Invalid/mismatched approval evidence emits
CTX444. Raw payloads and credentials are never stored in approval evidence.

## Cache boundary

The `capability_analysis` M8 cache key depends only on canonical identities of the plan, tool and
resource declarations, capability policy, analysis version, limits, and approval evidence. A tool
declaration change therefore misses the capability stage without invalidating unrelated repository
parse entries. Cached payloads are secret-safe capability manifests, not plan literal values or
resource contents.

## Evidence and CLI

A capability manifest records analysis mode/version, policy and plan identities, declaration
identities, ordered flows, rule IDs, diagnostics, approval requirements/evidence identities,
blocked/pending/allowed state, and cache status. `contextc mcp plan explain` renders one ordered
source -> calls -> sink path from stored evidence.

```bash
contextc mcp plan validate plan.json --tools declarations --json
contextc mcp plan analyze plan.json --tools declarations --policy policy.json --json
contextc mcp plan analyze plan.json --tools declarations --approval approval.json --cache-root .contextc/cache --output capability-analysis.json --json
contextc mcp plan explain capability-analysis.json --flow FLOW_ID --json
```

Every command explicitly remains static; no tool is executed.
