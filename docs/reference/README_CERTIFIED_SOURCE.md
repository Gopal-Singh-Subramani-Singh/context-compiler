# Context Compiler

Context Compiler is a local-first compiler and static-analysis toolchain for transforming
heterogeneous context into dependency-aware, provenance-preserving, token-budgeted,
reproducible, and policy-constrained model input.

This repository is being built milestone by milestone. The current cumulative implementation is
M15 on top of M1-M6, M11, and M9: typed immutable IR, exact target accounting, transactional
reproduction, optimizer correctness, credible benchmark evaluation, a real-repository case study,
deterministic structural security analysis, and a source-neutral cross-domain incident-response
compiler path. M15 adds retained heterogeneous source adapters, structural supersession/conflict
evidence, a `structured-json` target, isolated incident evaluation, and typed demo services while
reusing the same IR, graph, optimizer, security, budget, manifest, and reproduction machinery.
Incremental compilation, capability composition, and release/Observatory work remain later
milestones.

## Development

```bash
python -m pip install -e '.[dev]'
pytest -q
pytest --cov=contextc --cov-report=term-missing --cov-fail-under=85
ruff check .
ruff format --check .
mypy --strict contextc
```



## M15 cross-domain generalization

M15 proves the compiler core is not repository-specific by compiling a deterministic offline
incident-response fixture through the same universal pipeline. The packaged demo contains 21
retained source files spanning markdown, JSON, JSONL, YAML, monitoring observations, deployment
events, service ownership, procedures, conversation history, and retained static MCP results.

```bash
contextc demo list
contextc demo validate checkout-latency-001
contextc demo compile checkout-latency-001 --strategy relevance_greedy --budget 4000 --target structured-json --json
contextc demo compare checkout-latency-001 --all-strategies --budget 4000 --json
contextc demo graph checkout-latency-001 --selected-only --budget 4000 --json
contextc demo explain checkout-latency-001 --source incident://checkout-latency-001/runbooks/rollback_v1.md --budget 4000 --json
contextc demo reproduce checkout-latency-001 --budget 4000 --json
```

The old rollback procedure is excluded through an explicit `SUPERSEDES` edge and `CTX210`, not
through timestamp or filename heuristics. `CONTRADICTS` evidence emits non-blocking `CTX200`. The
malicious retained MCP source reuses the unchanged M9 security engine and does not perform live MCP
or tool execution. See `M15_WORKED_EXAMPLE.md` and `HANDS_ON_M15.md`.

## M9 structural security and static MCP

M9 keeps trust domain, sensitivity, and instruction authority as immutable source facts while
policy interpretation remains separate. The compile pipeline runs deterministic security
analysis before relevance/token analysis and optimizer selection. `QUOTE_AS_DATA` and `REDACT`
therefore affect the token costs actually optimized; `EXCLUDE` becomes an optimizer eligibility
constraint; and `BLOCK_COMPILATION` fails before the artifact transaction begins.

```bash
contextc compile REPOSITORY \
  --task "Explain the request path" \
  --target generic \
  --token-budget 2000 \
  --security-policy policy.json \
  --time-anchor 2026-09-03T00:00:00Z \
  --output compiled-context.txt --json
contextc reproduce compiled-context.txt.manifest.json --verify --json
contextc explain compiled-context.txt.manifest.json --node NODE_ID --json
```

The static MCP adapter reads retained JSON only. It performs no MCP transport, server discovery,
authentication, network access, live invocation, or tool execution. Tool-result text has
`instruction_authority = none` by default even when it claims higher authority.

## M11 real-repository case study

M11 packages an immutable offline Git bundle of the MIT-licensed
[`python-humanize`](https://github.com/python-humanize/humanize) repository and eight manually
reviewed historical bug/fix tasks. Compilation always uses the exact pre-fix tree and does not
execute repository code or load evaluator labels until all public strategy runs are sealed.

```bash
contextc case-study list
contextc case-study validate --all
contextc case-study extract-labels humanize-empty-natural-list
contextc case-study run --all
contextc case-study report --markdown
contextc case-study verify-determinism --all
```

The default database is `.contextc/case-study.sqlite3`. See `CASE_STUDY.md` for the complete fresh
raw result table, worked example, methodology, determinism evidence, and limitations. The study
does not claim statistical significance or universal retrieval superiority.

## CLI

```bash
contextc --help
contextc version
contextc doctor
contextc index PATH
contextc compile PATH \
  --task "Explain the request path" \
  --target generic \
  --token-budget 2000 \
  --optimizer auto \
  --time-anchor 2026-08-29T00:00:00Z \
  --output compiled-context.txt
contextc reproduce compiled-context.txt.manifest.json --verify
contextc reproduce compiled-context.txt.manifest.json \
  --rebuild --output rebuilt-context.txt
contextc inspect compiled-context.txt.manifest.json
contextc explain compiled-context.txt.manifest.json
contextc explain compiled-context.txt.manifest.json --node NODE_ID --json
contextc policy validate contextc/resources/security/default_policy.yaml --json
contextc security scan contextc/resources/security/fixtures/malicious_mcp.json --json
contextc benchmark debug TASK_DIRECTORY --strategy density_greedy
contextc benchmark suite SUITE_DIRECTORY --database benchmark.sqlite3
contextc benchmark report benchmark.sqlite3
contextc benchmark inspect benchmark.sqlite3 --run-id RUN_ID
```

Repository indexing parses Python with the standard-library `ast` module. It never imports or
executes indexed repository code. Binary, oversized, invalidly encoded, and syntactically
invalid sources receive deterministic policy handling and structured diagnostics.

## M2 core API

M2 adds `ContextGraph`, `CompilationUnit`, `SelectionStrategy`,
`DeterministicBaselineSelection`, and stored node explanations. Graph dependencies are an
explicit subset: `IMPORTS`, `CALLS`, and `REQUIRES` by default. Relationships such as
`CONFLICTS`, `SUPPORTS`, and `TAINTS` never force dependency inclusion merely because they are
present.

```python
from datetime import UTC, datetime
from pathlib import Path

from contextc.application import graph_repository_index
from contextc.hashing import semantic_hash
from contextc.ir import CompilationUnit, DeterministicBaselineSelection, NodeAnalysis
from contextc.parsers import RepositoryParser

index = RepositoryParser(revision="git:known-revision").parse(Path("."))
graph = graph_repository_index(index)
analyses = {node.node_id: NodeAnalysis(node_id=node.node_id, relevance=1.0) for node in graph.nodes}
request = CompilationUnit(
    task_id="inspect",
    task_description="Inspect the repository",
    target_id="generic",
    tokenizer_id="generic:unmeasured",
    token_budget=1000,
    policy_id="policy:default",
    time_anchor=datetime(2026, 1, 1, tzinfo=UTC),
    random_seed=0,
    compiler_version="0.5.1",
    pipeline_config_hash=semantic_hash({"pipeline": "m2-example"}),
)
selection = DeterministicBaselineSelection().select(graph, analyses, request)
```

The M2 baseline remains as a compatibility surface. Normal compilation uses the M5 optimizer
cascade, while M3 retains a closure-safe exact final trim as a last target-level safeguard.

## M3 exact targets

`GenericTokenizer` provides deterministic regex-unit accounting and is explicitly documented as
an approximation rather than a model tokenizer. Qwen and Llama require an explicitly configured
model/tokenizer and use its actual chat template. They never fall back to Generic.

```bash
pip install -e '.[qwen]'
contextc compile . \
  --task "Explain exact budget lowering" \
  --target qwen \
  --tokenizer-model YOUR_QWEN_TOKENIZER_ID \
  --tokenizer-revision YOUR_IMMUTABLE_REVISION \
  --token-budget 4096 \
  --time-anchor 2026-08-29T00:00:00Z \
  --output qwen-context.txt
```

Model downloads are disabled unless `--allow-tokenizer-download` is supplied. Missing or invalid
configured tokenizers fail with typed CTX710 evidence, a nonzero CLI exit, no traceback, and no
artifact overwrite. If mandatory dependency closure plus target overhead cannot fit, compilation
fails with CTX510 and no partial file.

## M4 manifests and reproduction

`contextc compile` now writes `OUTPUT` and `OUTPUT.manifest.json` as one documented transaction.
Both files are staged and flushed before the artifact is replaced; the manifest is committed
last as the validity marker. A failure at rendering, either staging boundary, manifest
serialization, or between the two final replacements restores any previous valid pair and
removes bounded temporary state. A custom `--manifest` must remain beside the artifact.

The strict, versioned manifest stores canonical semantic build inputs separately from its pretty
JSON representation. Machine-specific source/artifact locations are portable relative paths and
do not participate in `build_id`. Artifact bytes, source graph, every node's normalized content,
task, policy, pipeline configuration, target/tokenizer, budget, final trim, selection order,
optimizer status, diagnostics, and compiler implementation all carry explicit identities.

Verification checks stored evidence without compiling or mutating files:

```bash
contextc reproduce compiled-context.txt.manifest.json --verify
```

When the recorded relative source repository remains available, its revision, graph, and node
hashes are also checked. `--source PATH --source-revision REVISION` supplies explicit source
evidence after moving an artifact pair.

Rebuild mode is distinct and never copies the original artifact. It validates compatibility,
re-runs parsing, graphing, analysis, selection, exact lowering, and final recount from recorded
inputs, compares selected nodes/order, bytes, token count, artifact identity, and all semantic
manifest fields, then transactionally commits a fresh destination pair only after exact
agreement.

Deterministic reconstruction requires unchanged source content/revision, compiler pass identity,
policy/configuration, target/tokenizer semantics, optimizer semantics, random seed, and no
unrecorded model/network state. Generic reproduction is fully local. Qwen/Llama rebuild requires
the exact recorded tokenizer to be locally available and an immutable tokenizer revision;
unpinned model-tokenizer manifests are verifiable only to the available evidence and are not
accepted for byte-identical rebuild claims.

## M5 optimizer correctness

All strategies solve one shared, versioned selection problem: source-content allowance,
target-specific token costs, mandatory inclusion, blocked/policy eligibility, transitive
dependency closure, a canonical weighted objective, and deterministic source-aware tie rules.

The nine strategies are `naive`, `recency`, `top_k`, `relevance_greedy`, `density_greedy`,
`brute_force`, `dynamic_programming`, `ilp`, and `graph_closure_greedy`. `auto` uses the central
deterministic cascade. Exact strategies report `optimal` only when they prove optimality for the
actual shared formulation. Heuristics, fallback substitution, infeasibility, and feasible ILP
incumbents after timeout have distinct statuses and stored evidence.

```bash
contextc compile . \
  --task "Explain optimizer selection" \
  --target generic \
  --token-budget 2000 \
  --optimizer density_greedy \
  --time-anchor 2026-08-31T00:00:00Z \
  --output optimized-context.txt
```

The ILP strategy is optional (`pip install -e '.[ilp]'`). If PuLP is unavailable or configured
bounds are exceeded, the result records the substitute strategy, `fallback` status, CTX520,
and the reason. `top_k` likewise never relabels lexical relevance as semantic evidence when
embeddings/scores are unavailable.

## M6 benchmark credibility

Benchmark tasks physically separate `public/task.yaml` from `evaluator/labels.yaml`. Compilation
finishes before labels load, and cross-strategy runs must share an equal-footing semantic
fingerprint. Ground truth uses canonical `repo://fixture/path` locations with 1-based inclusive
line spans; node IDs are debug evidence only.

The evaluator reports ten raw metrics separately and stores run, metric, selected-location, and
Top-K evidence in a versioned SQLite database. Runtime measurements are operational and excluded
from semantic run identity. The packaged controlled suite contains eight tasks:

```bash
contextc benchmark suite \
  contextc/resources/benchmarks/controlled \
  --database benchmark.sqlite3 \
  --strategy naive \
  --strategy density_greedy \
  --strategy brute_force

contextc benchmark report benchmark.sqlite3
```

See `docs/architecture/m6-benchmark-credibility.md` for exact metric definitions and
`docs/benchmarks/m6-zero-result-root-cause.md` for the repaired stale-node-ID failure.

## Optional integrations

Qwen, Llama, tokenizer, embedding, ILP, and UI dependencies are separate extras. Transformers is
not imported by core CLI startup, and model loading occurs only after an explicit model-target
compile request.

## Project-local source classification

Repository builds can classify real filesystem sources before security analysis with ordered
`[[contextc.source_rules]]` entries in `contextc.toml` (or `[[tool.contextc.source_rules]]` in
`pyproject.toml`). Rules may safely downgrade trust to external/retrieved/unverified domains and
raise sensitivity to sensitive/secret; repository-local configuration cannot grant privileged
trust or instruction authority. See `HANDS_ON_M15.md` and the M9 architecture note.

## M8 incremental compilation (v0.15.0)

Repeated builds can use a local content-addressed cache without changing compiler semantics:

```bash
contextc compile REPOSITORY \
  --task '...' --target generic --token-budget 2500 \
  --time-anchor 2026-09-04T00:00:00Z \
  --output ../outputs/context.txt \
  --incremental --verify-incremental
```

`--verify-incremental` also performs a clean build and compares semantic selection/order, security and supersession results, rendered bytes, exact tokens, artifact evidence, and the semantic manifest form. A mismatch is `CTX704`.

Inspect or invalidate cache state explicitly:

```bash
contextc cache stats
contextc cache verify
contextc cache plan-invalidation --source repo:///src/example.py
contextc cache invalidate --source repo:///src/example.py --dry-run
contextc cache invalidate --source repo:///src/example.py --apply
```

Invalidation is a dry-run unless `--apply` is given. M8 does not implement remote caching, filesystem watchers, daemons, eviction, or CAS garbage collection. Cache deletion never invalidates a reproducible build manifest.

See `docs/architecture/m8-incremental-compilation.md` and `HANDS_ON_M8.md`.

## M10a static MCP capability composition (v0.16.0)

M10a analyzes declared MCP-style tools, protected resources, and proposed call plans before any
call is executed. It complements M9 content-flow analysis rather than replacing it. The analyzer
uses CTX440-CTX444 for dangerous compositions, incomplete declarations, invalid plans, explicit
approval requirements, and policy/evidence failures.

```bash
contextc mcp plan validate PLAN.json --tools DECLARATIONS --json
contextc mcp plan analyze PLAN.json --tools DECLARATIONS \
  --cache-root .contextc/cache --output capability-analysis.json --json
contextc mcp plan explain capability-analysis.json --flow FLOW_ID --json
```

The packaged default policy requires exact flow-scoped trusted approval for sensitive data sent
externally and for untrusted content entering shell/code execution, while credential/environment
access flowing to `network_send` is blocked by default. Used incomplete declarations are not safe
by default. Capability analysis is deterministic, bounded, secret-safe, and cached through the M8
content-addressed store using a dedicated semantic stage key. It performs no MCP transport,
authentication, discovery, network access, shell execution, or tool invocation.

See `docs/architecture/m10a-static-capability-composition.md` and `HANDS_ON_M10A.md`.

## M10b live tiny MCP validation (v0.17.4 certified predecessor)

M10b adds an optional **real local MCP** validation boundary after M10a. With the `live-mcp` extra installed, Context Compiler launches only its marked tiny fixture server through the maintained MCP Python SDK over stdio, discovers real MCP tool/resource declarations, maps them into the existing M10a capability model, maps runtime tool outputs into the M9 trust model, and compares declared behavior with bounded observed behavior.

```bash
python -m pip install 'context-compiler[live-mcp]'
contextc mcp live inspect --server contextc/demos/live_mcp/tiny_server.py
contextc mcp live validate --server contextc/demos/live_mcp/tiny_server.py
```

Dangerous proposed plans are still analyzed before unsafe sink invocation. The tiny server's `post_external_message`, `execute_fake_command`, and `fake_http_post` tools only append to sandbox ledgers; they do not send a real message, execute a shell, or make a network request. Runtime declaration drift emits `CTX445` and stops continuation. `contextc mcp live explain RESULT.json` explains persisted evidence without rerunning tools.

M10b is a bounded integration-validation milestone, not a generic MCP executor or production security gateway. See `docs/LIVE_MCP_VALIDATION.md` and `HANDS_ON_M10B.md`.

## M16 local Observatory and packaged release demos

Version 0.18.0 adds presentation and distribution without changing compiler semantics. The wheel
contains four bounded offline release demos plus a read-only optional Streamlit Observatory.

```bash
contextc demo registry list
contextc demo registry verify
contextc demo verify --all
contextc demo run repository-bug
contextc demo run incident-response
contextc demo run incremental-rebuild
contextc demo run capability-composition
```

Install the optional UI extra and launch the loopback Observatory with `contextc ui`. Release demos
materialize package resources into temporary directories and do not depend on the source checkout,
network access, model downloads, live MCP servers, credentials, or tool execution. See
`docs/DEMO_GUIDE.md`, `docs/OBSERVATORY.md`, and `docs/LIMITATIONS.md`.
