# M8 Incremental Compilation and Local Cache

M8 adds local content-addressed reuse without changing compiler semantics. The authoritative invariant is:

```text
incremental result == clean full-build result
```

## Cache layout

The default repository cache lives under `.contextc/cache/`:

```text
objects/          immutable content-addressed payloads
metadata/         canonical computation-key records
quarantine/       corrupt metadata/object evidence
source-index/     source URI -> computation-key mappings
dependency-index.json
```

Objects are addressed by SHA-256 content identity. Metadata writes use temporary files plus atomic rename. Cache metadata contains hashes, stage identities, dependencies and source URIs; it does not contain raw source content.

## Stage reuse

M8 uses narrow semantic stage versions for `source_content`, `parse`, `static_graph`, `analysis`, `security`, `supersession`, `token_count`, `selection`, `lowering`, and `artifact` compatibility. The implemented incremental path actually reuses:

- source-content fingerprints;
- adapted parse/static graph results when safe;
- security results keyed by canonical security policy identity;
- supersession results;
- target-specific token counts;
- per-node task analyses.

Selection and final lowering are deliberately rerun and final target validation remains authoritative. Their stage records still participate in the dependency index so source invalidation reaches all semantic downstream computations.

Raw adapted graph payloads are not persisted when any source node is classified `secret`. Security-cache payloads contain the transformed/redacted result only.

## Invalidation

Semantic inputs are stage-specific:

- source bytes -> source/parse and downstream;
- task -> analysis/selection/lowering while parse/security can be reused;
- policy formatting or whole-line comments -> same canonical policy identity and security reuse;
- policy semantic change -> security and downstream recomputation;
- target/tokenizer -> target token counts and downstream;
- budget or optimizer objective/version -> selection/lowering, while parse and valid analysis/token stages remain reusable;
- evaluator labels -> no compiler cache effect.

Source invalidation is planned from a persisted source index and traverses the dependency index deterministically. `invalidate` is dry-run unless `--apply` is explicitly passed. Applying invalidation removes computation metadata; immutable CAS objects may remain as orphaned content because M8 does not implement garbage collection or eviction.

## Corruption

Payload hash mismatch, malformed metadata, missing objects and incompatible cache schema are never reused. Bad entries are quarantined/rejected and the stage is recomputed. `CTX700`-series diagnostics reserve stable meanings for cache/incremental behavior; `CTX704` is semantic incremental/full mismatch.

## Semantic equivalence

`contextc compile --incremental --verify-incremental` runs the incremental build and a clean full build and compares source/secured graph identity, security decisions, supersession, analyses, semantic selection evidence, target render order, rendered bytes, exact token count and `BuildManifest.semantic_form()`. Solver runtime and storage locations are operational rather than semantic.

The final lowering order is target-defined and represented by `RenderedContext.ordered_node_ids`; optimizer discovery/tie traces remain evidence rather than an alternate render ordering.
