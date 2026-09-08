# M3 Target Token Correctness

M3 adds a target-lowering boundary after M2 selection. `SelectionResult` remains immutable
optimizer evidence; `RenderedContext.trim_evidence` records any deterministic repair required
after adding the real target template.

```text
CompilationUnit + ContextGraph + SelectionResult
  -> target-specific chat/message construction
  -> configured target template rendering
  -> exact tokenizer recount
  -> closure-safe deterministic trimming and re-rendering if needed
  -> exact final recount
  -> RenderedContext + source map + budget/trim evidence
  -> M4 transactional artifact/manifest commit
```

## Tokenizer identity

Every tokenizer records target ID, tokenizer ID, implementation version, optional immutable
revision, and a semantic configuration identity. The Generic tokenizer counts deterministic
regex word/punctuation units and explicitly makes no Qwen/Llama equivalence claim. Qwen and
Llama adapters import Transformers only when instantiated and require an explicitly configured
model ID. Their identity includes the loaded chat template, tokenizer class/path, vocabulary and
special-token data, revision, adapter options, and Transformers version.

## Exact final invariant

The same tokenizer that renders a model-specific target recounts the complete final string after
system/developer/user markers, source annotations, policy text, tool schemas, special markers,
and generation prompt markers are present. A returned `RenderedContext` validates:

```text
exact_token_count == tokenizer.count(rendered_text)
exact_token_count <= CompilationUnit.token_budget
```

Budget evidence separately records configured budget, empty-context fixed overhead, remaining
source allowance, pre-trim full-render count, and final count. The exact final recount—not the
allowance estimate—is authoritative.

## Overflow and atomicity

Final trimming scans the stored selected order deterministically. Removing a dependency also
removes every selected transitive dependent, while mandatory nodes and their dependency closure
are protected. Each batch is re-rendered and recounted within a bounded loop. An unfit protected
closure raises CTX510. Tokenizer initialization failures raise CTX710 with their original cause.
Neither failure writes or overwrites the requested target.

## Provenance

Source-map entries cover the entire rendered string contiguously. Original content regions carry
node ID, source URI/line span, and transformations. Target templates, annotations, and separators
are explicitly compiler-generated regions.
