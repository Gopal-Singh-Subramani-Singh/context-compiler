# Troubleshooting

## `contextc` not found

If installed with pipx:

```bash
pipx ensurepath
```

Open a new shell and run:

```bash
contextc version
```

For a virtual environment, make sure it is activated.

## Wrong Python environment

Check:

```bash
which python3
which contextc
python3 --version
contextc version
```

The certified campaign used Python 3.11.

## MCP plan analyze returns exit 3

This can be an expected policy result. Inspect the generated JSON for:

```text
blocked: true
pending_approval: true/false
diagnostics
rule_ids_triggered
decisions
```

Do not classify exit code `3` as a crash without inspecting the result.

## `CTX443` explicit approval required

Generate approval evidence for the exact `flow_identity`. Approval is not plan-global; multiple flows may require multiple approval files.

## `CTX444` capability policy/evidence failure

Check for:

- plan id mismatch
- untrusted approver domain
- `approved: false`
- unknown flow identity

## `CTX445` runtime mismatch

Observed live behavior did not match the declared capability. Treat the tool declaration as unreliable until corrected and revalidated.

## `CTX600` during reproduce verify

Source graph/content changed after the manifest was created. Restore the original source or rebuild from the current source and generate a new manifest.

## `CTX610` during reproduce verify

Artifact bytes changed after the manifest was created. Restore the original artifact or rebuild from the manifest/source.

## Incremental differences

Use:

```bash
contextc cache --root .contextc-cache verify --json
```

and compile with:

```text
--verify-incremental
```

If equivalence fails, preserve the result and investigate rather than deleting evidence first.

## Ollama demo cannot connect

Check:

```bash
ollama list
```

and confirm the local endpoint is running. The validated local model was `llama3.2:3b`.
