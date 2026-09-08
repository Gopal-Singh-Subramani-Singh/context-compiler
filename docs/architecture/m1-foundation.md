# M1 Foundation Architecture

The M1 application path is:

```text
repository bytes
  -> static parser
  -> immutable ContextNode tuple
  -> separate NodeAnalysis tuple
  -> deterministic SelectionResult
  -> Generic smoke renderer
  -> CompiledContext
```

Canonical serialization and structured diagnostics are shared infrastructure. Optional feature
discovery uses module metadata only and does not import optional packages during core startup.

Source IR identity includes stable provenance, content, classifications, metadata, and schema
versions. Task text, relevance, token counts, optimizer output, and selection state never enter
`ContextNode`.

