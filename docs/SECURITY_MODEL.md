# Security Model

## Purpose

Context Compiler treats context construction as a security boundary. Untrusted or sensitive source material is analyzed before it becomes model input or reaches a tool sink.

## Trust and authority

Validated source trust domains include examples such as:

- `local_repository`
- `external_content`
- `verified_tool`
- `unverified_tool`
- `retrieved_document`
- `user_instruction`
- `developer_instruction`
- `system_policy`

Repository source rules can classify content as external/untrusted, but validated policy prevents an untrusted source rule from promoting content into privileged instruction authority.

## Key diagnostics

The v0.18.0 validation campaign exercised these meanings:

| Code | Meaning |
|---|---|
| `CTX400` | injection-risk signal |
| `CTX410` | sensitivity-policy violation |
| `CTX420` | untrusted content entered instruction scope |
| `CTX425` | trust/authority override |
| `CTX430` | sensitive/secret external flow |
| `CTX440` | dangerous capability composition |
| `CTX441` | incomplete capability declarations |
| `CTX442` | invalid capability plan |
| `CTX443` | explicit approval required |
| `CTX444` | capability policy/evidence failure |
| `CTX445` | observed-vs-declared capability mismatch |
| `CTX600` | manifest/source mismatch during reproduction |
| `CTX610` | artifact reproduction mismatch |

## Untrusted instruction handling

The default malicious MCP fixture demonstrated a taint path from an unverified tool result to an instruction sink and triggered:

```text
CTX400
CTX420
CTX425
```

A validated security policy action is:

```text
quote_as_data
```

with a transformation identity such as:

```text
security:untrusted-instruction-flow:quote_as_data
```

This lets the compiler preserve evidence while preventing it from being treated as trusted instruction authority.

## Sensitive external flow

Validated policy can detect sensitive/secret content flowing toward an external sink. A redaction action removed the original sensitive marker and substituted a security-policy redaction marker before model/sink use.

## Capability policy

The default capability policy validated in v0.18.0 distinguishes between approval-gated and non-overridable risks:

```text
sensitive_to_external   -> require_explicit_approval
untrusted_to_execution  -> require_explicit_approval
credential_to_network   -> block
```

Exact approval is not a blanket bypass. It is associated with a specific:

- plan id
- flow identity
- approver identity
- trusted approver domain
- approved boolean

A hard `block` remains blocked even if trusted approval evidence is supplied for that flow.

## Live enforcement

The live MCP validation demonstrated that policy is enforced before prohibited sinks are invoked:

- external-message sink ledger remained empty
- fake execution sink ledger remained empty
- fake network sink ledger remained empty
- real network/message/shell/credential counters remained zero in the bounded fixture

## Security limitations

The validation campaign does not prove safety against every parser exploit, dependency vulnerability, operating-system boundary, adversarial MCP implementation, resource-exhaustion strategy, or future model/tool integration. Treat Context Compiler as one security control in a layered system.
