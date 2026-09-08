# MCP and Capability Enforcement

## Two layers

Context Compiler validates MCP/tool usage at two different layers:

1. **Static capability composition** — what the declared plan could do.
2. **Live runtime enforcement** — what an actual local MCP server reports/does at execution time.

## Static declarations

A declaration directory contains tool/resource declarations. A plan references those tools and binds outputs between calls.

Example concepts:

```text
read_customer_export
  capability: local_file_read
  output sensitivity: sensitive

post_partner_webhook
  capabilities: external_write, message_send
  side_effecting: true
  allows_network: true
```

A plan binding the read result into the external sender creates a sensitive-to-external flow.

## Static analysis lifecycle

```text
plan validate
      ↓
flow enumeration
      ↓
policy evaluation
      ↓
allow / require approval / block
```

A blocked policy result can still be a successful analysis artifact; in the validated CLI contract, policy blocking returned exit code `3`.

## Approval evidence schema

Validated JSON fields:

```json
{
  "approval_id": "approval-1",
  "plan_id": "plan-id",
  "flow_identity": "sha256:...",
  "approver_identity": "user:operator",
  "approver_trust_domain": "user_instruction",
  "approved": true,
  "evidence_uri": "approval://example/1"
}
```

The trusted default approval domains observed in v0.18.0 were:

```text
user_instruction
developer_instruction
system_policy
```

Approval is exact-flow scoped. If a plan has multiple approval-required flows, each flow requires matching approval evidence.

## Non-overridable hard block

For `credential_to_network`, default policy action is `block`. Supplying trusted approval evidence does not change that decision to allow.

## Live stdio MCP

Validated live commands initialize a real stdio MCP process, discover tools/resources, and execute through the enforcement layer.

```bash
contextc mcp live inspect \
  --server ./server.py \
  --sandbox ./sandbox \
  --timeout 8 \
  --json
```

## Runtime correspondence

A tool can declare one capability and exhibit another at runtime. The live validation exercised a misdeclared reader whose declared capability was local-file-read while observed behavior indicated credential access. Context Compiler produced an observed mismatch and `CTX445`, then blocked the runtime decision.

## Safety boundary

The certified campaign used a bounded local test server with synthetic/fake sinks. That validates the enforcement mechanism under the tested fixture; it is not a claim that arbitrary third-party MCP servers are trustworthy.
