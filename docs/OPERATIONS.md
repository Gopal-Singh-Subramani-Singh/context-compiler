# Operations and Deployment

## Recommended deployment model

Context Compiler is primarily a CLI/library-style pre-inference component. Deploy it in an isolated Python environment and keep generated caches, manifests and validation artifacts outside the installed package tree.

## Directory separation

Recommended operational separation:

```text
application-source/
contextc-cache/
compiled-artifacts/
manifests/
audit-evidence/
```

Do not write runtime validation fixtures into the certified source checkout.

## Cache hygiene

Use a dedicated cache root per environment or workload class:

```bash
contextc cache --root ./cache verify --json
```

Before deleting cache data, use `plan-invalidation` / dry-run invalidation when source-scoped cleanup is sufficient.

## Reproduction checks

For long-lived artifacts, verify before reuse:

```bash
contextc reproduce artifact.manifest.json --verify --json
```

If `CTX600` or `CTX610` appears, do not treat the stored artifact as verified.

## MCP operations

For live MCP:

- use an explicit server path/configuration
- use a dedicated sandbox
- set bounded timeouts
- write audit output
- prefer pre-analysis of capability plans
- do not assume third-party declarations are correct
- treat `CTX445` as a runtime correspondence failure

## Security logging

Persist structured JSON results and audit outputs for production investigations. Security-relevant fields can include diagnostics, transformations, flow identities, policy decisions, approvals, source trust, sensitivity and sink metadata.

## Failure handling

Non-zero exit status does not always mean process failure. Policy-blocked analysis/execution can intentionally return a non-zero code while still producing valid structured evidence. Always inspect the JSON result and diagnostic code.

## Upgrade process

1. Verify the release checksum.
2. Install into a new isolated environment.
3. Run `contextc version`.
4. Run your own smoke tests against representative sources.
5. Verify cache/reproduction compatibility expectations.
6. Promote only after operational checks pass.
