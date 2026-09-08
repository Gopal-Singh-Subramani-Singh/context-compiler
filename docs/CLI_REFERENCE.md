# CLI Reference

This is a practical reference for the command surfaces exercised in v0.18.0 validation. Use `contextc <command> --help` for the authoritative options in the installed build.

## Version

```bash
contextc version
```

## Index

```bash
contextc index SOURCE --json
```

Example:

```bash
contextc index ./repo --json > index.json
```

## Compile

Typical repository compilation:

```bash
contextc compile ./repo \
  --source-adapter repository \
  --task "Explain the relevant checkout behavior" \
  --target generic \
  --token-budget 1200 \
  --optimizer auto \
  --output compiled.txt \
  --manifest compiled.manifest.json \
  --json > compile.json
```

Common validated options:

- `--source-adapter repository`
- `--source-adapter incident`
- `--task TEXT`
- `--target generic`
- `--token-budget N`
- `--optimizer auto`
- `--time-anchor TIMESTAMP`
- `--output PATH`
- `--manifest PATH`
- `--json`
- `--incremental`
- `--verify-incremental`
- `--cache-root PATH`

## Explain

Explanation commands are available for stored compiler/MCP evidence. Exact positional arguments depend on the evidence type; use the relevant `--help` output.

## Reproduce

Verify:

```bash
contextc reproduce manifest.json --verify --json
```

Rebuild:

```bash
contextc reproduce manifest.json \
  --rebuild \
  --output rebuilt.txt \
  --json
```

Observed options:

```text
--verify
--rebuild
--source SOURCE
--source-revision SOURCE_REVISION
--output OUTPUT
--json
```

## Cache

Top-level cache commands:

```text
stats
inspect
verify
plan-invalidation
invalidate
```

Examples:

```bash
contextc cache --root .contextc-cache verify --json
```

```bash
contextc cache --root .contextc-cache \
  plan-invalidation \
  --source repo:///leaf.py \
  --json
```

```bash
contextc cache --root .contextc-cache \
  invalidate \
  --source repo:///leaf.py \
  --dry-run \
  --json
```

```bash
contextc cache --root .contextc-cache \
  invalidate \
  --source repo:///leaf.py \
  --apply \
  --json
```

## Static MCP capability plan

Validate declaration/plan structure:

```bash
contextc mcp plan validate plan.json \
  --tools ./declarations \
  --json
```

Analyze policy:

```bash
contextc mcp plan analyze plan.json \
  --tools ./declarations \
  --json > capability-analysis.json
```

Supply exact trusted approval evidence:

```bash
contextc mcp plan analyze plan.json \
  --tools ./declarations \
  --approval approval-01.json \
  --approval approval-02.json \
  --json
```

Explain a stored flow:

```bash
contextc mcp plan explain capability-analysis.json \
  --flow sha256:... \
  --json
```

## Live MCP

Observed live subcommands:

```text
inspect
tools
resources
validate
explain
plan
```

Inspect server:

```bash
contextc mcp live inspect \
  --server ./tiny_server.py \
  --sandbox ./sandbox \
  --timeout 8 \
  --json
```

List tools:

```bash
contextc mcp live tools \
  --server ./tiny_server.py \
  --sandbox ./sandbox \
  --timeout 8 \
  --json
```

List resources:

```bash
contextc mcp live resources \
  --server ./tiny_server.py \
  --sandbox ./sandbox \
  --timeout 8 \
  --json
```

Execute a live plan through enforcement:

```bash
contextc mcp live plan execute plan.json \
  --server ./tiny_server.py \
  --sandbox ./sandbox \
  --timeout 8 \
  --audit-output audit.json \
  --json
```

Batch validation:

```bash
contextc mcp live validate \
  --server ./tiny_server.py \
  --sandbox ./sandbox \
  --timeout 8 \
  --cache-root ./cache \
  --json
```

## Exit-code interpretation

Do not assume every non-zero status is a crash. In validated policy-block scenarios, a blocked analysis/execution returned exit code `3` while still producing a complete JSON policy result. Reproduction/tamper mismatch returned exit code `2` with the corresponding diagnostic.
