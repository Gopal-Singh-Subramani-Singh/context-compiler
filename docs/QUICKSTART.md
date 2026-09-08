# Quickstart

This guide shows the shortest path from a source repository to deterministic model input with a manifest.

## 1. Index a repository

```bash
contextc index ./repo --json > index.json
```

Use the index output to inspect what files and graph structures Context Compiler discovered.

## 2. Compile context under a token budget

```bash
contextc compile ./repo \
  --source-adapter repository \
  --task "Explain the checkout bug and include the implementation and relevant tests" \
  --target generic \
  --token-budget 1200 \
  --optimizer auto \
  --output compiled-context.txt \
  --manifest compiled-context.manifest.json \
  --json > compile.json
```

The compilation path may include:

- source loading
- parsing/indexing
- dependency and provenance tracking
- conflict and supersession handling
- security analysis and transformations
- token counting
- evidence selection under budget
- lowering into final model input
- manifest generation

## 3. Inspect the result

The JSON result records evidence such as:

- configured and final token counts
- selected and excluded evidence
- dependency-forced selections
- diagnostics
- security transformations
- optimizer strategy/status
- provenance identities
- manifest/artifact identities

## 4. Verify reproducibility

```bash
contextc reproduce compiled-context.manifest.json --verify --json
```

For a deterministic rebuild:

```bash
contextc reproduce compiled-context.manifest.json \
  --rebuild \
  --output rebuilt-context.txt \
  --json
```

Then compare:

```bash
cmp compiled-context.txt rebuilt-context.txt
```

## 5. Incremental compilation

```bash
contextc compile ./repo \
  --source-adapter repository \
  --task "Explain checkout behavior" \
  --target generic \
  --token-budget 800 \
  --incremental \
  --verify-incremental \
  --cache-root .contextc-cache \
  --output compiled.txt \
  --json > incremental.json
```

A second unchanged run can reuse cached stages while still checking incremental/full equivalence.

## 6. Static MCP capability analysis

```bash
contextc mcp plan validate plan.json \
  --tools ./declarations \
  --json
```

```bash
contextc mcp plan analyze plan.json \
  --tools ./declarations \
  --json > capability-analysis.json
```

A blocked plan returns a policy/block exit code rather than executing tools.

## 7. Live local MCP validation

With a local stdio MCP server:

```bash
contextc mcp live inspect \
  --server ./tiny_server.py \
  --sandbox ./sandbox \
  --timeout 8 \
  --json
```

Then execute a plan through the live enforcement boundary:

```bash
contextc mcp live plan execute plan.json \
  --server ./tiny_server.py \
  --sandbox ./sandbox \
  --timeout 8 \
  --audit-output live-audit.json \
  --json
```

Use the live mode only with servers you intentionally choose to invoke.
