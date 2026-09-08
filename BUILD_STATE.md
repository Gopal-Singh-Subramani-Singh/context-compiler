# Context Compiler Build State

## Current milestone

- Milestone: M10a cumulative static MCP capability composition
- Status: functional implementation complete in authoring container; Mac hands-on acceptance pending; final release-polish gates deferred
- Date: 2026-09-04 UTC
- Package version: 0.16.0

## M11 preserved M6 baseline

Before M11 source changes, Python 3.12.13 produced:

```text
pytest -q
190 passed

pytest --cov=contextc --cov-report=term-missing --cov-fail-under=85
190 passed
Required test coverage of 85% reached. Total coverage: 86.68%

ruff check .
All checks passed!

ruff format --check .
128 files already formatted

mypy --strict contextc
Success: no issues found in 75 source files

uv lock --check --offline
Resolved 126 packages

contextc version
0.6.0
```

The user's independent macOS/Python 3.11.9 M6 gate also passed 190 tests, 86.68%
coverage, Ruff, formatting, strict mypy, and offline lock validation. Their hands-on
evidence covered all eight controlled tasks, all nine M6 strategies, 63 raw rows,
evaluator isolation, hand-calculated metrics, SQLite idempotence, and semantic
determinism across repeated suite runs.

## M11 repository and task corpus

- The case study uses the small MIT-licensed `python-humanize/humanize` repository.
- A complete, immutable Git bundle is packaged at
  `contextc/resources/case_study/humanize/humanize.bundle` so historical compilation
  requires neither a network connection nor a mutable external checkout.
- Bundle SHA-256: `5e40e011d2b1f87e45e113475f60d659c529e04b10f04263784cada16e285408`.
- Eight genuine fixes provide eight pre-fix revisions and fix-derived labels. Every
  task records the exact single-parent ancestry, changed files, reviewed spans,
  rationale, and source URLs. Two tasks are dependency-sensitive; the corpus also
  includes tight-budget, large-function, distractor-heavy, rounding, timezone, list,
  and unit-rollover cases.
- Public task inputs and evaluator-only labels/reviews are physically separated. The
  compiler receives only the public task and exact pre-fix tree. Evaluator data is
  loaded only after every strategy has completed, and task-specific sentinels are
  checked against compiler requests, results, and rendered context.
- Compilation is static. Exact revisions are materialized from the verified bundle;
  repository code is never imported, executed, installed, or contacted over a
  network.

## M11 architecture and interfaces

- Added immutable, versioned case-study public-task, historical-label, manual-review,
  execution, and determinism schemas.
- Added validated offline historical materialization, including reverse physical file
  creation for discovery-order determinism tests.
- Added a shared prepared-compilation path. Each task is parsed and analyzed once,
  then all strategies receive the same immutable graph, analyses, target parameters,
  and compiler-input fingerprint.
- Case-study evaluation delegates to the M6 raw metric implementation. M11 adds no
  alternate metric formulas. A numerical hardening clamps only sub-picosecond
  floating-point drift at ratio boundaries while still rejecting materially invalid
  ratios.
- Added `contextc case-study list`, `validate`, `extract-labels`, `run`, `report`, and
  `verify-determinism`. Label extraction is a review helper and explicitly refuses to
  write approved ground truth automatically.
- Added `CASE_STUDY.md`, architecture documentation, and ADR 0007. Raw rows remain the
  primary evidence; descriptive strategy means are secondary.

## M11 fresh case-study evidence

The packaged corpus was validated from the bundle, then run with five bounded
strategies (`naive`, `top_k`, `relevance_greedy`, `density_greedy`, and
`graph_closure_greedy`):

```text
tasks=8
strategies=5
stored-raw-rows=40
all-pre-fix-revisions-are-fix-parents=True
all-recorded-changed-files-match-git-diff=True
all-manual-reviews-approved=True
bundle-unchanged=True
evaluator-sentinel-absent=True
```

The results intentionally retain negative findings. Across the eight tasks,
`relevance_greedy` had mean required-file recall 0.75 and required-span recall 0.375;
the density and graph-closure heuristics had 0.25 and 0.0 respectively; naive had
zero required-file/span recall. `top_k` disclosed a density fallback because semantic
embeddings were unavailable. No lexical score was relabeled as semantic evidence.

The tight-budget naturalsize worked example used a 560-token source allowance. The
reviewed 556-token function fit: relevance greedy selected the exact required
`src/humanize/filesize.py:38-102` span, emitted 664/760 final tokens, and achieved
1.0 required-file recall/precision, span recall, and useful-token ratio with 0.0
unsupported context. Naive and density-family strategies selected distractors and
correctly received zero required recall and 1.0 unsupported-context ratio.

Determinism was checked for every task and all five strategies across the normal run,
an identical repeat, and reverse physical file creation order:

```text
tasks=8
strategies-per-task=5
selections-compared=120
repeated-semantics-identical=True
reverse-materialization-semantics-identical=True
```

See `CASE_STUDY.md` for all 40 raw rows, task provenance, the worked example,
dependency evidence, interpretation, and limitations.

## M11 final quality gate

### M11.1 packaging compatibility correction

Independent macOS/Python 3.11.9 verification exposed that the declared
`setuptools>=68` floor did not support the PEP 639 SPDX-string license syntax used by
`pyproject.toml` when building with `--no-isolation`. Editable installation had used an
isolated current backend, so application tests were unaffected. Version 0.11.1 raises
the backend floor to `setuptools>=77` and includes that backend in the development
extra. This preserves all M11 runtime and semantic contracts while making the stated
clean development build command portable. Package discovery is also restricted to the
exact `contextc` package hierarchy so transient historical checkout directories cannot
enter a distribution even if an operating system delays their cleanup.

Fresh corrected-package evidence:

```text
pytest -q (clean non-Git stage)
200 passed in 24.78s

ruff check .
All checks passed!

ruff format --check .
146 files already formatted

mypy --strict contextc
Success: no issues found in 86 source files

uv lock --check --offline
Resolved 126 packages

wheel files=145, historical bundles=1, tasks=8, transient checkouts=0
sdist files=251, historical bundles=1, tasks=8, transient checkouts=0
twine check: PASSED
standalone wheel version=0.11.1, tasks=8, all-valid=True
```

The cumulative gate was executed on Python 3.12.13 after source, tests,
documentation, schemas, packaged Git evidence, metadata, and lock changes:

```text
pytest -q
200 passed in 24.98s

pytest --cov=contextc --cov-report=term --cov-fail-under=85 -q
200 passed in 73.03s
Required test coverage of 85% reached. Total coverage: 85.79%

ruff check .
All checks passed!

ruff format --check .
146 clean-stage files already formatted

mypy --strict contextc
Success: no issues found in 86 source files

uv lock --check --offline
Resolved 126 packages

python -m build --no-isolation
Successfully built context_compiler-0.11.1.tar.gz and
context_compiler-0.11.1-py3-none-any.whl

twine check
PASSED (wheel and source distribution)

clean wheel install --no-deps
contextc version: 0.11.1
standalone working directory is a Git repository: False
packaged tasks: 8
all packaged tasks valid: True
optional heavy modules loaded: none
```

## M11 limitations

- This is one real repository and eight historical tasks; it is evidence, not a claim
  of universal strategy quality.
- Labels are fix-derived and freshly reviewed, but still encode reviewer judgment.
- The bounded five-strategy comparison does not claim semantic Top-K performance;
  the unavailable embedding path is reported as fallback.
- Historical checkout requires the local `git` executable, while compilation itself
  remains offline and static.
- Runtime measurements are operational and environment-dependent; semantic evidence
  excludes elapsed time.

## M6 preserved M5.1 baseline

Before M6 source changes, Python 3.12.13 produced:

```text
pytest -q
172 passed in 0.52s

pytest --cov=contextc --cov-report=term --cov-fail-under=85
172 passed in 1.50s
Required test coverage of 85% reached. Total coverage: 86.20%

ruff check .
All checks passed!

ruff format --check .
166 files already formatted

mypy --strict contextc
Success: no issues found in 54 source files

uv lock --check --offline
Resolved 126 packages in 3ms

contextc version
0.5.1
```

## Preserved M4 baseline

M5 began from the completed cumulative M4 tree. Before any source change, Python 3.12.13
produced:

```text
pytest -q
135 passed in 0.47s

pytest --cov=contextc --cov-report=term-missing --cov-fail-under=85
135 passed in 1.34s
Required test coverage of 85% reached. Total coverage: 85.92%

ruff check .
All checks passed!

ruff format --check .
84 files already formatted

mypy --strict contextc
Success: no issues found in 49 source files

uv lock --check --offline
Resolved 126 packages in 6ms
```

The user's independent macOS/Python 3.11.9 M4 gate also passed 135 tests, 85.92% coverage,
Ruff, formatting, and strict mypy before M5 was authorized. Their hands-on evidence additionally
covered artifact/source/token/schema tampering, all five transaction fault boundaries, and
byte-identical deterministic rebuild.

## Architecture decisions

- `SelectionProblem` is the sole shared objective and constraint layer. It validates the exact
  graph/analysis node domain, target-token costs, source-content allowance, mandatory set,
  blocked and policy-eligible sets, transitive configured dependency closure, valid IDs, unique
  selection, and final feasibility for every strategy.
- `ObjectiveWeights` schema 1.0 is immutable, canonical, configurable, finite, and bounded within
  `[0, 1000]`. Positive relevance/trust/freshness/dependency-coverage and negative
  redundancy/security-risk terms are evaluated centrally. Benchmark ground-truth metadata is
  never read by the objective. The complete optimizer configuration enters pipeline identity.
- Target overhead is exactly rendered and counted before selection. The effective
  source-content allowance is reserved from the final target budget. Per-node costs use the
  configured target tokenizer over deterministic rendered node segments; M3 exact final recount
  and closure-safe trim remain the final target safeguard.
- Dependency pairs are deduplicated and limited to configured dependency edge types. Closure is
  transitive and shared dependencies are charged once. Conflict/support/supersession edges do
  not force selection.
- The common stable key uses descending utility/relevance, ascending target cost, source URI,
  source start/end line, and node ID. Result order and concise tie evidence are bounded and never
  depend on insertion order, set iteration, built-in hashes, solver return order, or randomness.
- Statuses are exactly `OPTIMAL`, `FEASIBLE`, `FEASIBLE_TIMEOUT`, `HEURISTIC`, `FALLBACK`, and
  `INFEASIBLE`. Exact claims occur only in proven supported formulations. A feasible ILP
  incumbent after timeout is never optimal; missing/no-incumbent/error/unsafe exact execution
  records fallback with CTX520. Mandatory closure overflow or policy conflict records CTX530.
- Measured optimizer runtime is stored operational evidence but excluded from semantic
  `build_id`. Strategy/configuration/objective/status/selection evidence remains semantic, so
  source-driven M4 rebuild can compare deterministic outcomes while allowing elapsed time to
  differ honestly.

See `docs/architecture/m5-optimizer-correctness.md` and
`docs/adr/0005-one-selection-problem-and-honest-optimizer-status.md`.

## Public interfaces

- Added versioned `ObjectiveWeights`, `OptimizerLimits`, and `OptimizerConfiguration`.
- Added all nine common-contract strategies: `naive`, `recency`, `top_k`,
  `relevance_greedy`, `density_greedy`, `brute_force`, `dynamic_programming`, `ilp`, and
  `graph_closure_greedy`.
- Added `SelectionProblem`, `OptimizerDecision`, `choose_optimizer`, and
  `DeterministicOptimizerCascade` under the lazily loaded `contextc.optimization` API.
- `contextc compile` now accepts `--optimizer`, `--source-content-allowance`, repeated
  `--mandatory-node`, and repeated `--block-node`; `auto` is the default centralized cascade.
- `SelectionResult` schema 1.1 stores requested/used strategy, exact status, objective, used and
  available tokens, solver runtime, optional timeout, fallback, ordered selected/excluded/forced
  and mandatory IDs, bounded tie trace, diagnostics, and excluded reasons.
- `BuildManifest` schema 1.1 records and replays optimizer configuration and all required
  optimizer evidence. `inspect`/`explain` report proof, heuristic, timeout, fallback, dependency,
  exclusion, and tie evidence without rerunning selection.
- Added CTX530 optimizer-infeasibility diagnostics and package version 0.5.1.

### M5.1 evidence correction

The public macOS strategy comparison exposed that ILP selected the same optimal dependency-closed
set as brute force but reported zero dependency-forced nodes because solver-selected binary
variables had been treated as explicit seeds. Version 0.5.1 derives a deterministic minimal
closure generator for solver results, preserves mandatory seeds, and classifies the regenerated
dependencies as forced. Selection, objective, ordering, artifact bytes, and optimality were not
wrong; the stored forced-inclusion evidence was corrected and regression-tested.

## M5 correctness evidence

The M5 suite adds 37 optimizer/integration cases, including:

- 100% brute-force/DP/real-PuLP-CBC agreement on every supported small dependency-free fixture;
- brute-force/ILP agreement with dependency implications and coverage reward;
- three distinct fixtures where naive, relevance greedy, and density greedy are strictly below
  the brute-force optimum;
- two transitive dependency-chain fixtures of length two, shared-dependency single charging, and
  non-dependency edge exclusion;
- mandatory overflow and blocked mandatory dependency `INFEASIBLE` results with CTX530;
- all nine strategies repeated and run against reversed node/edge insertion order with identical
  ordered IDs and objective evidence;
- forced ILP timeout with a feasible incumbent (`FEASIBLE_TIMEOUT`) and a separate no-incumbent
  fallback case;
- top-k semantic-score absence with explicit density fallback, CTX520, and no fake semantic
  score;
- DP resource-bound fallback without unsafe allocation;
- centralized cascade branches, policy eligibility, ignored benchmark metadata, canonical
  objective validation, public lazy exports, source-aware equality trace, CLI status, manifest
  evidence, explanation evidence, exact target-overhead reservation, and M4 rebuild regression.

## Direct M5 compile/rebuild evidence

A fresh cumulative 0.5.0 pre-correction build compiled the fully local M4 source fixture through the M5 auto
cascade, verified it, rebuilt it from source, and compared artifact and semantic evidence:

```text
compiled 4 nodes for generic
tokens: 274/500
optimizer: auto -> brute_force (optimal)
build: sha256:122cc2d099c18afe75e16197591abcdedbc0ff9fe2b50681a31381de0ec2814a

verified
identity: sha256:720c6417767c311d84b0b4fc5a669206998c042959b0ad0a519f0988a2146c2e
tokens: 274
source checked: True

rebuilt and matched stored semantic evidence
identity: sha256:720c6417767c311d84b0b4fc5a669206998c042959b0ad0a519f0988a2146c2e
tokens: 274

artifact-bytes-identical=True
build-id-identical=True
semantic-manifest-fields-identical=True
optimizer=auto->brute_force
status=optimal
objective=1.4000000000000001
optimizer-selected=4
dependency-forced=2
final-tokens=274/500
```

These identities were generated fresh from the local fixture and are not historical
reproduction claims.

A separate explicit `top_k` build without semantic scores produced:

```text
optimizer: top_k -> density_greedy (fallback)
requested=top_k
used=density_greedy
status=fallback
diagnostic-backed=True
reason=semantic embeddings/scores are unavailable; no lexical score was relabeled semantic
```

The corrected 0.5.1 build then compared explicit brute-force and real ILP runs on the same
dependency fixture:

```text
optimizer: brute_force -> brute_force (optimal)
optimizer: ilp -> ilp (optimal)
selected-identical=True
objective-identical=True
forced-identical=True
brute-forced=('node-03cb6922b740dfa9c0486680', 'node-273557d21b8669efefa57702')
ilp-forced=('node-03cb6922b740dfa9c0486680', 'node-273557d21b8669efefa57702')
```

## Final quality gate

The final source gate was executed on Python 3.12.13 after code, tests, documentation, schemas,
version, metadata, and lockfile changes:

```text
pytest -q
172 passed

pytest --cov=contextc --cov-report=term-missing --cov-fail-under=85
172 passed
Required test coverage of 85% reached. Total coverage: 86.20%

ruff check .
All checks passed!

ruff format --check .
93 files already formatted

mypy --strict contextc
Success: no issues found in 54 source files

uv lock --check --offline
Resolved 126 packages
```

## Packaging and core-only requirements

- Runtime dependencies remain empty. PuLP is optional under `[ilp]` and included only in the
  development gate so the real exact-solver oracle runs.
- Core startup imports none of `pulp`, `transformers`, `tokenizers`,
  `sentence_transformers`, or `streamlit`.
- The wheel and source distribution pass `twine check`; a clean no-dependency wheel install runs
  `contextc version`, `contextc --help`, and `contextc doctor` without optional integrations.

Exact packaging evidence:

```text
python -m build --no-isolation --outdir ../m5-dist
Successfully built context_compiler-0.5.1.tar.gz and
context_compiler-0.5.1-py3-none-any.whl

python -m twine check ../m5-dist/*
context_compiler-0.5.1-py3-none-any.whl: PASSED
context_compiler-0.5.1.tar.gz: PASSED

uv pip install --python ../m5.1-core-venv/bin/python --no-deps \
  ../m5.1-dist/context_compiler-0.5.1-py3-none-any.whl
Installed context-compiler==0.5.1

contextc version
0.5.1

core-only-startup=0.5.1 optional-loaded=[]
installed-from=.../m5.1-core-venv/lib/python3.12/site-packages/contextc/__init__.py
```

The first no-isolation build attempt produced no distribution because the synchronized dev
environment did not retain its declared `setuptools.build_meta` backend. Installing the declared
build requirement `setuptools>=68` into that development environment resolved the incidental
tooling omission; runtime dependency metadata remained empty.

## M6 architecture and interfaces

- Added `contextc.benchmark` with canonical repository URI and inclusive-span contracts,
  evaluator-side ground truth, immutable raw metrics/run/Top-K models, and semantic run IDs.
- Split public task loading/compilation from evaluator label loading/scoring at the module and
  physical fixture-directory boundaries. Public compilation imports no evaluator label API.
- Added an executable equal-footing fingerprint that excludes only strategy identity and
  evaluator labels while covering task, graph, analysis, target/tokenizer, budget/overhead,
  effective source allowance, objective, solver limits, dependency policy, requirements, policy,
  and random seed.
- Added versioned SQLite schema 1 with transactional parameterized writes to `benchmark_runs`,
  `benchmark_metrics`, `benchmark_selected_nodes`, and `top_k_candidates`. Duplicate semantic
  run IDs are idempotent first-write-wins records.
- Added `contextc benchmark debug|run|suite|report|inspect`. Raw reports retain every task and
  strategy row; Top-K fallback traces contain no fabricated candidates.
- Added eight packaged controlled tasks and a hand-calculated direct-file oracle. The evaluator
  sentinel is absent from compiler task/graph/analysis/query/artifact/manifest/diagnostic/
  explanation/fingerprint surfaces and raw SQLite bytes.
- Documented the stale-node-ID zero-result root cause and accepted the canonical-span/evaluator
  isolation design in ADR 0006.

## M6 correctness evidence

The M6 suite adds 18 tests. Hand-calculated cases cover perfect and zero coverage, partial and
duplicate overlap, distractor source, empty required set, dependency endpoints, budget use, and
infeasible/no-selection policy. Integration cases cover invalid URI traversal/ambiguity,
equal-footing rejection, evaluator isolation, Top-K post-compilation overlap annotation, SQLite
reload/idempotency/schema version, CLI inspection, all controlled tasks, and raw reports.

Fresh public CLI evidence over all nine M5 strategies produced:

```text
stale_debug_id_absent= True
canonical_uri_matches= True
tasks= 8
completed= 7
infeasible= 1
raw_rows= 63
strategies= 9
metric_fields= 10
semantic_records= 63
repeat_semantic_records_identical= True
```

The controlled categories are direct file match, dependency chain, distractor-heavy,
duplicate-heavy, tight budget, configuration dependency, conflict-bearing context, and an
explicit mandatory-closure infeasibility.

## M6 final quality gate

Executed on Python 3.12.13 after the final public/evaluator module split:

```text
pytest -q
190 passed in 0.67s

pytest --cov=contextc --cov-report=term-missing --cov-fail-under=85
190 passed in 1.86s
Required test coverage of 85% reached. Total coverage: 86.68%

ruff check .
All checks passed!

ruff format --check .
203 files already formatted

mypy --strict contextc
Success: no issues found in 75 source files

uv lock --check --offline
Resolved 126 packages

contextc version
0.6.0
```

Packaging evidence:

```text
python -m build --no-isolation
Successfully built context_compiler-0.6.0.tar.gz and
context_compiler-0.6.0-py3-none-any.whl

python -m twine check DIST/*
context_compiler-0.6.0-py3-none-any.whl: PASSED
context_compiler-0.6.0.tar.gz: PASSED

controlled_resources_packaged=True
wheel_files=107

clean no-dependency wheel install:
contextc version -> 0.6.0
core_only_version=0.6.0
optional_loaded=[]
```

## Known limitations

- Brute force is intentionally limited to small optional domains; DP is exact only for bounded
  dependency-free integer-cost problems; ILP availability and behavior depend on optional PuLP
  and its solver. These limitations produce explicit cascade/fallback evidence.
- Generic counts remain exact only for the documented regex target, not estimates for a model.
  Qwen/Llama require the actual configured tokenizer and immutable revision for rebuild.
- The M4 two-file transaction still uses the manifest as commit marker and does not claim an
  impossible portable two-path atomic filesystem syscall.
- Benchmark useful/redundant/unsupported attribution distributes each selected node's
  target-specific optimizer token cost evenly over its source lines. It is explicit and
  deterministic, not a lexical or semantic token-to-line alignment claim.
- The controlled suite establishes evaluator correctness, and M11 adds one real-repository
  study; neither supports a universal strategy-ranking claim.
- Python 3.12.13 received the local runtime and packaging gates. Python 3.11 remains the declared
  package, Ruff, and strict-mypy target; the user's macOS runtime gates cover M1-M5 on 3.11.9.

## Deferred work

Security/taint/static-MCP sources, cross-domain generalization, incremental compilation,
static capability composition,
Observatory, packaged demos, CI, and final release acceptance remain deferred in milestone order.

## Next milestone

M9 — Policy and security enforcement. M9 has not started.

---

# M9 — Security Policy, Taint Analysis, and Minimal Static MCP Source Adapter

## Status

Implementation complete as cumulative version `0.12.1` on top of the supplied M11 `0.11.1`
archive. The M9 semantic/integration tests, clean distribution build, and installed-wheel smoke
checks pass. Final locked-development-environment certification remains pending because this
execution runtime cannot install the already-declared PuLP/Ruff/mypy/build/twine dev dependencies
offline; that limitation is recorded rather than weakening any inherited gate.

## Baseline before changes

The supplied M11 archive recorded `200 passed`, >=85% coverage, Ruff, strict mypy, package build,
and clean-wheel installation. The first M9 `0.12.0` pass added standalone structural security but
did not yet integrate security into normal compile/reproduction semantics. Manual hands-on checks
1-25 passed and exposed one evidence inconsistency: local secret redaction recorded `CTX410` on the
decision but did not emit the diagnostic itself.

In this container, the inherited full suite cannot reproduce the five exact ILP status assertions
because PuLP is not installed. Those tests deterministically fall back as designed for a missing
optional solver, while two real-PuLP tests skip explicitly.

## Architecture decisions

- `ContextNode` trust domain, sensitivity, and instruction authority remain immutable source facts.
- Security policy interpretation remains separate under `contextc/security/`.
- Static MCP parsing is retained-data-only and performs no transport, discovery, authentication,
  network call, live tool invocation, or repository-code execution.
- Tool results default to `InstructionAuthority.NONE` even if their text claims system/developer
  authority.
- Pattern matching is bounded signal evidence; matched plaintext is represented by a hash rather
  than retained as diagnostic/explanation payload.
- Taint traversal follows only `TAINTS`/`ENABLES`, is cycle-safe, bounded, and stably ordered.
- Repository compilation runs security immediately after raw graph construction and before task
  analysis/token costing.
- The raw graph remains M4 source/reproduction evidence. A derived post-security graph carries
  quote/redact transformations downstream.
- Security-excluded nodes remain structurally present but are optimizer-ineligible, so dependency
  closure can prove infeasibility instead of silently reintroducing excluded context.
- `BLOCK_COMPILATION` and `REQUIRE_EXPLICIT_ALLOW` abort before artifact transaction staging.
- Quote/redact changes are target-tokenized before selection; M3 exact fully-rendered recount
  remains authoritative after lowering.
- BuildManifest schema is `1.2` and stores canonical, secret-safe M9 evidence plus the full security
  policy input needed for deterministic rebuild.
- Stored `explain --node` reads manifest evidence only and reports source security facts, rule/action,
  transformation, exclusion state, and token impact without rerunning compilation.

See `docs/architecture/m9-security-and-static-mcp.md` and ADR 0008.

## Files/modules added or materially changed

```text
contextc/security/{models,trust,policy,patterns,taint,transform,analysis,apply,service}.py
contextc/parsers/mcp.py
contextc/application/compile.py
contextc/reproduction/{manifest,service}.py
contextc/cli/main.py
contextc/errors.py
contextc/schema.py
contextc/resources/security/default_policy.yaml
contextc/resources/security/fixtures/{benign_mcp,malicious_mcp}.json
tests/security/test_m9_security.py
tests/security/test_m9_compile_integration.py
tests/parsers/test_m9_mcp_parser.py
tests/test_cli.py
docs/architecture/m9-security-and-static-mcp.md
docs/adr/0008-security-before-analysis-with-raw-source-evidence.md
HANDS_ON_M9.md
```

## Public interfaces

```text
SecurityRule
SecurityPolicy
SecurityDecision
SecurityResult
TaintPath
TaintLimits
PolicyAction
SecurityService
StaticMcpParser
load_policy / policy_from_mapping / policy_identity
analyze_security
apply_security_result
find_taint_paths
```

CLI:

```text
contextc policy validate POLICY
contextc security scan STATIC_MCP_JSON [--policy POLICY]
contextc security explain STATIC_MCP_JSON [--policy POLICY]
contextc compile ... [--security-policy POLICY]
contextc explain MANIFEST --node NODE_ID [--json]
contextc reproduce MANIFEST --verify
contextc reproduce MANIFEST --rebuild --output DEST
```

## Required M9 behavior covered

- malicious MCP override: `CTX400`, `CTX420`, `CTX425`;
- benign MCP result and quoted-security-discussion false-positive controls;
- untrusted instruction flow and deterministic taint-path evidence;
- trust/authority self-promotion prevention;
- sensitive external flow: `CTX430`;
- local secret redaction now emits `CTX410` and redacts without needing an external sink;
- allowed local sensitive data remains unchanged;
- policy actions ALLOW, QUOTE_AS_DATA, REDACT, EXCLUDE, BLOCK_COMPILATION,
  REQUIRE_EXPLICIT_ALLOW;
- deterministic path ordering, cycle bounds, and max-path/max-report limits;
- mandatory/dependency interaction with security exclusion;
- transformed token costs recalculated before optimizer selection;
- block before artifact transaction;
- raw secret absence from artifact, manifest, diagnostics/stored explanation evidence;
- manifest policy/analysis/rule/diagnostic/taint/transformation/exclusion/token evidence;
- same-policy/source verify and byte-identical rebuild;
- stored node explanation of trust, authority, sensitivity, rule/action, transform, selection and
  token impact;
- static MCP source URI/provenance and flow-edge restrictions.

## Commands executed and exact evidence

Targeted M9/CLI regression after final integration:

```text
python -m pytest -q tests/test_cli.py tests/security/test_m9_security.py \
  tests/security/test_m9_compile_integration.py tests/parsers/test_m9_mcp_parser.py
28 passed
```

New M9 security/static-MCP module coverage:

```text
28 passed
TOTAL 412 statements, 37 missed, 88% coverage
```

Full inherited suite in this runtime:

```text
215 passed, 5 failed, 2 skipped
```

All five failures are `tests/test_m5_optimizers.py` assertions that require PuLP to report an
`optimal` ILP status; with PuLP absent the existing ILP strategy reports its documented fallback.
The two PuLP integration tests skip with `No module named 'pulp'`. No M9/M4/M6/M11 test fails.

The exact whole-project pytest-cov command was attempted twice but coverage instrumentation over
the historical case-study suite exceeded this container's execution window before completing.
It is therefore not reported as passed. The targeted new-module coverage above is fresh evidence;
the inherited M11 archive records the previous whole-project >=85% gate.

Development-tool availability check:

```text
ruff: missing
mypy: missing
build: missing
pulp: missing
```

Network installation was unavailable, so these were not silently substituted. `python -m
compileall` over `contextc` and tests passed. A source line-length scan found no new >100-character
M9 lines after formatting; the remaining long lines are inherited test lines with type-ignore
comments.

Lock consistency:

```text
uv lock --check --offline
Resolved 126 packages
```

Distribution build using the declared setuptools backend already present in the runtime:

```text
context_compiler-0.12.1.tar.gz
context_compiler-0.12.1-py3-none-any.whl
BUILD_EXIT=0
wheel_bad_cache_files=0
sdist_bad_cache_files=0
```

Wheel content verification confirmed M9 security modules, static MCP parser, default policy,
malicious fixture, and the inherited M11 offline `humanize.bundle` are packaged.

Clean installed-wheel smoke outside the source checkout:

```text
contextc version -> 0.12.1
policy validate -> valid=True
malicious scan -> CTX400, CTX420, CTX425
custom compile -> security rule triggered and quote transformation present
reproduce --verify -> verified
block policy -> exit=3, artifact_exists=no, manifest_exists=no
```

## Regressions preserved

- M4 transactional artifact/manifest, verify, and rebuild tests pass in the inherited suite.
- M5 non-PuLP optimizer semantics and dependency constraints pass; only missing-solver status
  assertions fail in this runtime.
- M6 benchmark/evaluator isolation tests pass.
- M11 real-repository validation/determinism tests pass.
- Evaluator labels remain outside compiler-visible source inputs and M9 evidence.
- No repository code or live MCP/tool behavior is executed.

## Known limitations / bounded claim

M9 performs structural trust, policy, pattern, and taint analysis. It does not claim complete
prompt-injection prevention. At the M9 milestone, no live MCP discovery/auth/transport, capability composition,
cross-server privilege analysis, secret-manager integration, enterprise IAM, or automatic policy
generation was implemented. M10a later adds static declared capability composition only; live MCP remains out of scope.

The final milestone-quality certification must still be rerun in an environment where the declared
`.[dev]` dependencies are available:

```bash
pytest -q
pytest --cov=contextc --cov-report=term-missing --cov-fail-under=85
ruff check .
ruff format --check .
mypy --strict contextc
```

No test should be weakened or skipped to obtain that gate.

## Next milestone

M15 — Cross-domain generalization, only after the final M9 gate above passes in the user's normal
development environment.

# M15 — Cross-Domain Generalization

## Status

Functional implementation complete as cumulative version `0.13.0` on top of M9 `0.12.1`.
M15 demonstrates one bounded offline incident-response domain through the same core compiler
abstractions. Global release-polish gates remain intentionally deferred to final acceptance under
the current project workflow.

## Baseline before M15

The user verified the M9 cumulative build on macOS with PuLP installed:

```text
pytest -q -> 222 passed
pytest --cov=contextc --cov-report=term-missing --cov-fail-under=85
-> 222 passed, 85.48% total coverage
```

The authoring container does not provide PuLP, so the inherited M5 ILP status assertions continue
to report fallback here rather than `OPTIMAL`.

## Architecture decisions

- Added a source-neutral `SourceAdapter` boundary returning universal `IndexResult` and
  `ContextGraph` structures.
- Kept `CompileRepositoryRequest` as a compatibility name while adding `source_adapter_id` and
  source-neutral compile/prepare functions.
- Added deterministic structural supersession from explicit `SUPERSEDES` edges; timestamps and
  keywords do not infer supersession.
- Added non-blocking conflict evidence from `CONTRADICTS` / `CONFLICTS` edges.
- Reused M9 security unchanged for retained static MCP content.
- Added `structured-json` as an ordinary target with target-specific exact tokenization and the
  existing final-budget enforcement.
- Kept evaluator labels outside compiler-visible inputs; incident evaluation imports only after
  compiled strategy results are sealed.
- Extended equal-footing fingerprints with security-policy, source-adapter, and supersession-policy
  identities while excluding only strategy identity.
- BuildManifest schema advanced to `1.3`; stored build inputs now include `source_adapter_id` so
  verify/rebuild reopens the correct source domain.

See `docs/architecture/M15_CROSS_DOMAIN_GENERALIZATION.md` and
`docs/adr/ADR-0015-source-neutral-adapters.md`.

## Public interfaces

```text
contextc.cross_domain.SourceAdapter
contextc.cross_domain.RepositoryAdapter
contextc.cross_domain.IncidentAdapter
contextc.application.prepare_source_target
contextc.application.compile_source_target
contextc.application.compile_source_to_path
contextc.targets.TargetId.STRUCTURED_JSON
contextc.tokenizers.StructuredJsonTokenizer
contextc demo list
contextc demo validate INCIDENT
contextc demo compile INCIDENT --strategy ... --budget ... --target structured-json
contextc demo compare INCIDENT --all-strategies
contextc demo graph INCIDENT --selected-only
contextc demo explain INCIDENT --source URI
contextc demo reproduce INCIDENT
```

## Packaged incident fixture

`checkout-latency-001` contains 21 retained source files producing 22 IR nodes and 12 typed edges.
It covers incident report, deployment timing, monitoring observations, service ownership, current
and superseded rollback procedures, operations conversation, retained malicious and benign static
MCP results, and unrelated distractors. Evaluator labels live separately under `evaluator/`.

At the worked-example budget of 4000 `structured-json` tokens, `relevance_greedy` can retain all
required evidence classes while the structurally superseded rollback v1 remains ineligible and
consumes no final target budget.

## Required M15 behavior covered

- deterministic heterogeneous parse and canonical `incident://` provenance;
- timezone-aware source timestamps normalized deterministically;
- universal `conversation_message`, `event`, `observation`, `record`, `procedure`, and tool-result
  nodes in the existing immutable IR;
- universal cross-domain relationship serialization and graph insertion-order invariance;
- no incident-specific branch in optimizer strategies;
- explicit `SUPERSEDES` -> `CTX210` -> stale-node ineligibility;
- structural supersession wins even when timestamps are swapped;
- `CONTRADICTS` / `CONFLICTS` -> non-blocking `CTX200` evidence;
- unchanged M9 malicious-MCP behavior (`CTX400`, `CTX420`, `CTX425`, quote-as-data,
  `instruction_authority=none`);
- no M15 `CTX440` capability-composition claim;
- exact final token budget for deterministic `structured-json`;
- evaluator-only sentinel remains absent from compiler-visible IR;
- M6 raw metrics reused without changing their definitions plus domain relation/supersession/security
  metrics;
- all strategy comparisons use one shared prepared analysis and one equal-footing fingerprint;
- top-k fallback is explicit when semantic scores are unavailable;
- incident manifest verify and deterministic byte-identical rebuild;
- old-runbook and malicious-MCP explanations read stored manifest evidence;
- typed demo service and CLI surface with no UI/compiler-logic duplication.

## Executed tests in the M15 authoring runtime

Targeted M15 suite:

```text
pytest -q tests/cross_domain
23 passed
```

M15 plus M6 benchmark/fingerprint regressions:

```text
41 passed
```

M15 focused coverage:

```text
23 passed
517 statements, 45 missed, 136 branches, 42 partial
86% focused coverage
```

Full inherited + M15 suite in the authoring container:

```text
238 passed, 5 failed, 2 skipped
```

All five failures and both skips are the same inherited PuLP-dependent M5 checks caused by PuLP
being unavailable in this runtime. No M15, M9, M11, M6, M4 reproduction, CLI, or non-PuLP optimizer
test fails. On the user's macOS environment the pre-M15 suite already demonstrated the PuLP path as
green with PuLP 3.3.2 installed.


Convenience wheel build and clean installed-wheel functional smoke (not the deferred final release certification):

```text
context_compiler-0.13.0-py3-none-any.whl -> built
wheel cache artifacts -> none
contextc version -> 0.13.0
demo list -> checkout-latency-001
demo validate -> 21 sources / 22 nodes / 12 edges
demo compile -> 3928 / 4000 exact tokens; CTX210/200/400/420/425
demo reproduce -> verified=True, rebuilt=True, byte_identical=True
```

## Deferred quality/release cleanup

Per the project decision made after M9, global Ruff formatting/lint, strict mypy cleanup, `uv` lock
certification, distribution polish, and final clean-wheel certification are deferred until all
feature milestones are complete. These are not represented as verified M15 gates.

No test was weakened or deleted to obtain M15 functional evidence.

## Known limitations / bounded claim

At the M15 milestone, the source-neutral architecture was demonstrated on one deterministic offline incident-response
fixture and did not claim universal domain generalization, production incident-response accuracy,
complete prompt-injection prevention, live MCP support, or capability-composition security. M8 and M10a subsequently add incremental compilation and static declared capability composition while live MCP remains out of scope.

## Hands-on acceptance

See `HANDS_ON_M15.md` and `M15_WORKED_EXAMPLE.md`.

## Next milestone at the time

M8 — Incremental compilation and cache invalidation, preserving M11, M9, and M15 semantics.


# v0.14.0 — M15 cumulative with real repository source classification

This cumulative patch closes the remaining M9 real-filesystem ingestion gap discovered during
hands-on testing against a fresh `python-humanize/humanize` checkout. The repository parser
previously assigned every ordinary repository file `local_repository`, `internal`, `none`, so a
physical `private/**` file could not become `secret` and a physical retained vendor/retrieved file
could not be represented as external/untrusted through the normal CLI.

## Added source-fact rule surface

`contextc.toml` and `[tool.contextc]` now accept ordered `source_rules` with POSIX-relative `glob`
patterns. The rules are applied before M9 security analysis by `contextc index` and normal
repository compilation. Later matching rules override earlier matching rules per explicitly set
fact.

Repository-local rules are monotonic and cannot manufacture privilege:

- trust may remain `local_repository` or be downgraded to `external_content`,
  `retrieved_document`, or `unverified_tool`;
- sensitivity may remain `internal` or increase to `sensitive` / `secret`;
- `public` declassification is rejected;
- privileged trust domains are rejected;
- instruction authority may not be granted (only explicit `none` is accepted).

Ordered rule semantics participate in pipeline identity, are stored in
`build_inputs.source_rules`, are replayed during verify/rebuild, and remain visible through stored
node facts. BuildManifest schema is now `1.4`.

## Executed v0.14.0 evidence in the authoring container

Focused M9-real-source + M9 compile + M15 regression set:

```text
47 passed
```

Full cumulative functional suite:

```text
245 passed
5 failed
2 skipped
```

The five failures and two skips are the inherited M5 PuLP-only outcomes because PuLP is absent in
this authoring runtime. No v0.14 source-rule, M15, M9, M11, M6, M4 reproduction, CLI, or
non-PuLP optimizer test fails. The user's macOS development environment already has PuLP 3.3.2;
the expected fully enabled collection is 252 tests, but that result must be verified there rather
than claimed here.

A whole-project coverage run was started after the final test set but exceeded the authoring
container timeout before completion. The previous user-side M9 cumulative gate was 85.48%; the
v0.14 whole-project percentage remains to be rerun on the user's normal dev environment.

Clean wheel build:

```text
context_compiler-0.14.0-py3-none-any.whl
SHA-256 cfde01b7e935a9301830edf6113ca0ddf76f129f18334de7e61f7714057f2c3a
```

Installed-wheel real-filesystem smoke outside the source checkout:

```text
contextc version -> 0.14.0
repo:///external-notes/vendor.md -> external_content / internal / none
repo:///private/deployment_credentials.md -> local_repository / secret / none
security diagnostics -> CTX400, CTX410, CTX425
secret transform -> security:local-secret-redaction:redact
canary in artifact -> false
canary in manifest -> false
reproduce --verify -> verified
reproduce --rebuild -> rebuilt
byte-identical rebuild -> PASS
```

The smoke writes build outputs outside the indexed source root. Writing generated artifact/manifest
files inside the indexed source tree makes them new source inputs on a later verification and
correctly produces `CTX600` source mismatch.

Global Ruff/format/strict-mypy/final sdist/twine/release certification remain deferred by the
project workflow until all feature milestones are complete. No tests were weakened to obtain the
v0.14 evidence.

---

# M8 build state — v0.15.0

Status: **implemented; Mac real-world hands-on functional acceptance passed; final release-polish gates deferred.**

Implemented:

- local content-addressed object store with canonical metadata, atomic writes, hash verification, and quarantine;
- typed computation keys and cache schema compatibility;
- centralized narrow semantic pass versions;
- dependency and source URI indexes;
- dependency-aware invalidation planning and explicit apply;
- actual intermediate reuse for adapted parse/static graph, M9 security, M15 supersession, target token counts, and per-node task analysis;
- stage evidence for selection/lowering while final lowering remains rerun and authoritative;
- secret-safe cache policy (no raw source content in metadata/source objects; no raw secret adapted graph persistence);
- incremental/full semantic comparison including `BuildManifest.semantic_form()` and CTX704 mismatch handling;
- CLI `compile --incremental --verify-incremental --cache-root` and `cache` subcommands;
- whole-line policy comments canonicalized away for policy formatting/comment-only cache reuse;
- fresh machine-readable baseline freeze at `docs/baselines/m8-baseline-index.json`;
- M11 real repository source-change/revert equivalence test and M15 incident observation-change/revert equivalence test.

Fresh pre-cache baseline sub-runs from the v0.14.0 cumulative tree:

- M4: 22 passed
- M5 core/non-PuLP: 28 passed (PuLP unavailable in this container)
- M6: 19 passed
- M11: 9 passed
- M9: 24 passed
- M15: 23 passed

M8 focused cache/incremental tests: **28 passed**, focused cache/incremental coverage **88.53%**.

Whole-project combined coverage evidence: **85%**, with `coverage report --fail-under=85` exiting successfully. The M11 append command reached all nine passing tests but the command wrapper timed out during coverage finalization; the persisted coverage data was then independently validated by the explicit fail-under report.

Full cumulative container run: **273 passed, 5 failed, 2 skipped**. All five failures and both skips are inherited M5 ILP-only outcomes caused by `pulp` being unavailable in this container. No M8, M15, M11, M9, M6, M4, security, reproduction, or non-ILP optimizer regression was observed.

The user Mac acceptance environment had PuLP 3.3.2 and passed **280/280** cumulative tests with **85.95%** whole-project coverage. Real repository cache equivalence/invalidation, corruption recovery, secret non-persistence, M15 incident reuse/mutation, cache-independent reproduction, and installed-wheel smoke were also exercised successfully.

Additional package/smoke evidence generated for the cumulative feature ZIP:

- `uv lock --check --offline` resolved 126 packages successfully;
- wheel built without network/build isolation: `dist/context_compiler-0.15.0-py3-none-any.whl`;
- wheel SHA-256: `82c8c00d05481f30dc26cc08af8f513e12465344f64cacc92e776d821a00bb90`;
- isolated wheel smoke: version `0.15.0`, incremental/full equivalence true, cache verification valid, reproduction verified.

No sdist/twine claim is made here; final release-package certification remains deferred.

Deferred, per project workflow, until final acceptance:

- whole-project Ruff lint/format certification;
- strict mypy certification;
- final release package/twine/clean-wheel certification.


---

# M10a build state — v0.16.0

Status: **implemented; focused M10a functional/coverage gate passed; cumulative container run has only the known optional PuLP environment gap; Mac hands-on acceptance pending.**

Accepted M8 Mac baseline carried into this milestone:

- package `0.15.0`;
- PuLP `3.3.2`;
- M8-focused tests: **28 passed**;
- full cumulative tests: **280 passed**;
- whole-project coverage: **85.95%**;
- real `python-humanize` cold/warm incremental equivalence, source mutation/revert, cache CLI invalidation, task/budget/optimizer/target/policy invalidation, secret non-persistence, corruption quarantine/recovery, real M15 incident mutation/revert, cache-independent reproduction, and installed-wheel smoke all passed hands-on.

M10a implementation:

- typed stable capabilities: local/database/credential/environment/network/external/code/shell/message/user-data/approval declarations;
- independent protected resource declarations with sensitivity, trust/ownership, allowed sinks/actions;
- static MCP-style tool declarations including trust, resources, output sensitivity, side-effect, execution/network and completeness evidence;
- ordered proposed plans with resource/prior-output bindings, literals, requested approvals, schema validation and CTX442;
- deterministic resource/tool/call/output/capability graph and bounded flow enumeration;
- CTX440 dangerous composition for sensitive -> external, untrusted -> execution, and credential/environment -> network;
- CTX441 incomplete declaration handling with used unknown declarations blocked by default;
- canonical versioned capability policy with allow/warn/require-explicit-approval/block actions;
- exact flow-scoped trusted approvals, CTX443 pending requirements, and CTX444 invalid/mismatched policy/evidence;
- secret-safe capability manifest and stored flow explanation;
- `contextc mcp plan validate`, `analyze`, and `explain`;
- M8 `capability_analysis` cache stage keyed by plan/tool/resource/policy/analysis/approval/limit identities without touching unrelated parse-stage entries;
- no live MCP discovery/authentication/transport, network calls, shell/code execution, or tool invocation.

Focused M10a tests: **35 passed**.

Focused `contextc.capabilities` coverage: **89.97%**, above the 85% feature threshold.

M10a + M9 + M8 focused regression matrix before final packaging: **74 passed**.

Full cumulative container run: **308 passed, 5 failed, 2 skipped** across 315 collected tests. All five failures and two skips are inherited M5 ILP-only outcomes because PuLP is unavailable in this authoring container. The expected PuLP-enabled Mac target is therefore **315 passed**; that target must be verified hands-on rather than claimed here.


Combined whole-project coverage evidence was assembled from the full non-M11 suite plus appended M11 case-study coverage chunks to avoid the authoring wrapper timeout. `coverage report --fail-under=85` reports **86%** and exits successfully. The monolithic all-tests coverage command still exceeds the wrapper timeout during the long M11 phase, so no claim is made that one uninterrupted command completed.

Packaging/smoke evidence:

- `uv lock --check --offline`: PASS, 126 packages resolved;
- wheel: `dist/context_compiler-0.16.0-py3-none-any.whl`;
- wheel SHA-256: `ed919ee75c5dd7f0559bd6f2c40f88bafd72bccab0555a628f51c2fdca824409`;
- wheel contents include the full `contextc.capabilities` package and packaged default capability policy;
- wheel rebuilt after removing Python bytecode/cache files; no `__pycache__`, `.pyc`, or `.pyo` entries remain in the wheel;
- isolated wheel smoke: version `0.16.0`, static validation true, dangerous plan CTX440+CTX443, `tool_execution_performed=false`, capability cache valid;
- physical static CLI smoke: sensitive->external pending approval, exact flow approval, warm cache reuse, untrusted->shell, credential->network, invalid binding CTX442, ordered explanation, and raw literal-canary non-persistence all passed.

Release-polish gates remain deferred under the project workflow until final acceptance. The authoring container does not currently provide the `ruff` executable, so no new global Ruff claim is made. Strict mypy, final sdist/twine, and clean release-package certification also remain deferred.

---

# Milestone 10b — Live Tiny MCP Integration and Static-vs-Runtime Validation — v0.17.2

## Status

**IMPLEMENTED; author-side SDK-independent gates pass; real official-SDK stdio acceptance is pending on the Mac because the authoring container cannot download/import the optional `mcp` package. M10b is therefore NOT YET declared complete.**

The implementation follows the M10b master prompt: real local MCP through a maintained SDK, bounded stdio fixture, M9/M10a reuse, correspondence, enforcement, audit, containment and semantic validation. No production MCP gateway or arbitrary executor is introduced.

## Starting baseline

- accepted M8 Mac baseline: 280/280 and 85.95% coverage;
- M10a v0.16.0 focused: 35 passed, 89.97% capability-package coverage;
- M10a author cumulative: 308 passed, 5 failed, 2 skipped, all non-passes from unavailable PuLP;
- expected PuLP-enabled M10a Mac baseline before M10b: 315 passed.

## MCP SDK

Optional extra: `mcp>=2.1,<3`. Core dependencies remain empty. The authoring container has no registry/DNS access for this package, so the real-SDK module is packaged but skipped here. The Mac acceptance must install `.[dev,live-mcp]` and run the real stdio suite.

## Transport

`stdio` only. The maintained SDK owns protocol framing, subprocess lifecycle and MCP initialization/session behavior. No public network is required.

## Tiny server

Packaged at `contextc/demos/live_mcp/tiny_server.py`; marked with `CONTEXTC_TINY_MCP_FIXTURE = True`. The execution CLI refuses unmarked server source files.

## Tools

Nine bounded tools: eight required fixture tools plus one deliberately misdeclared tool used to validate CTX445. External/message, shell, and HTTP names represent **fake sandbox ledgers**, not real-world effects.

## Resources

Three MCP resources: public readme, internal config, secret test-secret, all backed by sandbox fixture files.

## Sandbox design

Sandbox path containment rejects absolute paths, `..` traversal and symlink resolution outside the root. Child HOME is replaced with the sandbox. No fixture tool accepts unrestricted host filesystem access.

## Synthetic secrets

`CONTEXTC_TEST_SECRET_7F31`, `CONTEXTC_TEST_CREDENTIAL_A91C`, and `CONTEXTC_TEST_INTERNAL_RECORD_C442`. Persisted observation/audit evidence records hashes, sizes, sensitivity and generic sentinel flags rather than raw values.

## Static declaration normalization

Live SDK tool/resource objects are normalized into stable snapshots. Temporary sandbox paths, PID and timestamps are absent from declaration identities. Snapshots map directly into the existing M10a `ToolDeclaration`/`ResourceDeclaration` types.

## Runtime observation model

Live tool results become secret-safe `MCPRuntimeObservation` evidence and ordinary M9 `ContextNode` tool-result facts with stable `mcp://.../results/...` provenance and `InstructionAuthority.NONE`.

## Capability correspondence

Declared and observed capabilities/sensitivity are compared as observed-match, declared-but-unobserved, observed-mismatch or unknown. Declared-but-unobserved is not treated as proof of absence.

## Declaration mismatch behavior

New diagnostic `CTX445 MCP_DECLARATION_MISMATCH`. Unexpected observed capability or sensitivity mismatch blocks continuation through the M10b enforcement decision.

## Enforcement gate

M10a analysis runs before runtime sink invocation. Valid dangerous flows may execute source calls for observation while the unsafe sink call is stopped until every exact flow-scoped approval requirement is satisfied. Hard-block flows remain hard blocks.

## Approval model

Reuses M10a `ApprovalEvidence` and trusted-domain semantics; no parallel boolean approval mechanism exists.

## Safe plan results

SDK-independent fake-transport service tests prove public/static paths and bounded source/sink sequencing. Real safe stdio execution is packaged in `tests/live_mcp/test_m10b_live_sdk.py` and awaits Mac execution.

## Secret-to-external flow

Fake-transport service test proves source executes and sink is blocked before invocation without approval. Real stdio test additionally asserts the outbound ledger stays empty and audit omits the raw secret.

## Untrusted-to-execution flow

Fake-transport test proves M9 injection/authority diagnostics are recorded for the unverified source and the execution sink is stopped. Real stdio ledger assertion is packaged and pending Mac execution.

## Credential-to-network flow

Real stdio test is packaged to prove the credential source may run but the fake network sink remains uncalled under the configured hard block. No actual network implementation exists in the fixture.

## Sandbox containment

Unit tests pass for valid read, traversal rejection, absolute-path rejection and symlink escape. Real protocol traversal test is packaged for Mac.

## Real-network denial

The fixture source contains no socket/requests/httpx/urllib network client or subprocess-based sink implementation. Real SDK tests inspect this source. Stdio itself needs no network.

## Real-shell denial

The tiny server has no `subprocess.run`, `subprocess.Popen`, `os.system`, or `shell=True` fixture-tool path. The only subprocess boundary is the SDK launching the controlled MCP server itself.

## Audit evidence

Structured audit records plan/server/transport/operation/tool, argument/result hashes, sensitivity/trust, static decision, approval state, attempted/performed state, policy identity, diagnostics, duration and error. Raw synthetic secret values are excluded.

## Manifest integration

`LivePlanExecutionResult` persists server ID, stdio transport, server declaration hash, fixture version, validation profile, static M10a manifest, runtime correspondence, invoked/blocked calls and audit evidence. It is a bounded M10b validation report; normal M4 compiler manifests remain unchanged.

## Explain integration

`contextc mcp live explain RESULT.json --json` uses stored evidence only and explicitly reports `mcp_rerun_performed=false`.

## Cache integration

M8/M10a capability caching is reused only for static declaration/plan analysis. The M10b namespace includes server ID and fixture semantic version; normalized declarations/policy/plan/approvals remain part of the M10a key. Runtime observations are not cached as timeless truth.

## Determinism

Stable declaration hashes ignore sandbox path. Execution/validation semantic forms exclude duration and cache status while retaining semantic source/result identities, static decisions, correspondence and sink containment evidence.

## Semantic reproduction

`LivePlanExecutionResult.semantic_form()` and `LiveMCPValidationResult.semantic_form()` define runtime semantic comparison separately from M4 byte-identical build reproduction.

## Error handling

Typed live errors cover connection, initialization, protocol/discovery, tool invocation, resource read, sandbox, policy/approval, declaration mismatch and timeout. Missing SDK uses the existing optional-dependency error path.

## Timeout behavior

Initialization is bounded by `timeout_seconds`; list/read/call operations use `operation_timeout_seconds` when configured and otherwise inherit `timeout_seconds`. Unit timeout coverage passes; the real delayed-tool stdio timeout test is packaged for Mac.

## Tests added

`tests/live_mcp`: 35 test functions total. In this authoring environment 24 execute and the 11 real-SDK stdio tests are represented as one module-level skip because `mcp` is unavailable.

Focused author result: **24 passed, 1 module skipped**. Focused `contextc.live_mcp` coverage: **86.48%**, with `--cov-fail-under=85` passing.

M10b + M10a/M9/M8/M15 focused runnable regression: the live-MCP/capability/security/cache/incremental/cross-domain matrix reports **132 passed, 1 live-SDK module skipped**.

## Full test results

Author cumulative after M10b: **332 passed, 5 failed, 3 skipped**. Five failures and two skips are inherited M5/PuLP-only outcomes; the remaining skip is the real-MCP SDK module. No runnable M10b/M10a/M9/M8 regression is present.

With PuLP and the MCP SDK installed, the current Mac target is **350 passing tests**.

## Coverage

Focused live-MCP package coverage: **86.48%**. The monolithic whole-project coverage command again exceeds the authoring wrapper timeout during the long M11 section, so no uninterrupted full-project percentage is claimed yet. Mac must run the required `--cov-fail-under=85` gate.

## Ruff

Not run in this authoring container: `ruff` executable unavailable. Required on Mac before completion.

## Formatting

Not run in this authoring container: `ruff` executable unavailable. Required on Mac before completion.

## Mypy

Not run in this authoring container: `mypy` executable unavailable. Required on Mac before completion.

## Lockfile

`uv lock --check --offline` cannot resolve after adding the optional live-MCP SDK because the authoring container has no registry/cache for required packages. `uv.lock` is intentionally not falsely certified; Mac must refresh/check the lock with network/cache availability before final M10b acceptance.

## M4 regression

Covered by the cumulative runnable suite; no new reproduction failure observed. Final explicit Mac regression required by the M10b master gate remains pending.

## M5 regression

Author environment still lacks PuLP, producing the inherited five failures/two skips. Mac previously had PuLP 3.3.2; final M10b run must prove these green.

## M6 regression

Runnably covered by cumulative suite; no new failure observed.

## M11 regression

Runnably covered until the coverage wrapper timeout; normal pytest cumulative run passes M11.

## M9 regression

Included in the 132-pass focused matrix and cumulative run; live outputs reuse M9 trust/security facts.

## M15 regression

Included in the focused matrix/cumulative run; no adapter regression observed.

## M8 regression

Included in the 132-pass focused matrix; M10b static cache reuses M8/M10a mechanisms.

## M10a regression

Included in the 131-pass focused matrix; M10a remains the sole static capability analyzer/approval model.

## Known limitations

M10b validates a bounded local fixture, not arbitrary MCP servers; observations are scenario-based; declarations may be dishonest; no OAuth/OIDC, internet-facing server, production external service, real shell, real database, real credential, autonomous agent, production enforcement proxy, or full protocol-conformance guarantee exists; transport coverage is stdio only. Author-side real SDK execution is pending solely because the optional package is unavailable in this container.

## Deferred M16 work

M16 may consume the stable live-validation service/results as an optional advanced local mode, but normal product startup must not require a live MCP server or the MCP SDK.

## Next milestone

Do **not** begin M16 until the Mac executes the official-SDK live suite, full 350-test target, coverage >=85, Ruff, format, strict mypy, lock refresh/check, and required real hands-on demonstrations, at which point M10b can be declared complete or complete with genuine documented limitations.
## M10b v0.17.1 live-stdio error-boundary correction

The first real-Mac MCP SDK run on 2026-09-04 executed the official stdio path and produced **8 passed / 3 failed**. The three failures were expected-error scenarios whose correct typed Context Compiler exceptions (`MCPToolInvocationError`, `MCPTimeoutError`, `MCPResourceReadError`) were wrapped by nested AnyIO/MCP `ExceptionGroup` objects during async context teardown. The timeout test also used a 0.05 s global timeout, causing real subprocess initialization to time out before the intended delayed tool call.

v0.17.1 normalizes nested SDK teardown groups back to the first contained `ContextCompilerError`, preserves existing typed tool-invocation failures, and changes the timeout fixture to a 2.0 s operation bound with a 5 s delayed tool. An SDK-independent nested-group regression passes in the author environment.

Author-side evidence after the correction: `24 passed` across the SDK-independent live-MCP unit/service/audit/explain/optional-dependency set. The author environment still cannot execute the official MCP SDK subprocess suite. **M10b remains NOT COMPLETE until the Mac reruns the real live SDK module with zero failures/skips.**

The checked-in `uv.lock` project version was corrected to 0.17.1, but a complete lock re-resolution including the `live-mcp` extra remains a Mac acceptance task because the author environment cannot resolve the registry dependency graph offline.

## M10b v0.17.2 independent operation-timeout correction

The second real-Mac SDK rerun on 2026-09-04 proved the v0.17.1 exception-boundary fix for traversal and unknown-resource paths: **2 passed / 1 failed** across the three previously failing tests. The remaining timeout failure was a fixture-design defect, not a transport failure: `echo_untrusted_text` intentionally rejects delays above 2000 ms, while the test requested 5000 ms, so the server returned a typed tool error before a client timeout could occur.

v0.17.2 keeps the fixture's bounded 2000 ms safety ceiling and instead separates startup/initialization timeout from per-operation timeout. `LiveMCPServerSpec.operation_timeout_seconds` controls list/read/call operations and falls back to `timeout_seconds` when omitted. The CLI exposes `--operation-timeout`. The live timeout test now uses a 5.0 s initialization budget, 1.0 s operation budget, and a valid 1500 ms fixture delay, so it exercises a real `tools/call` timeout without weakening the fixture server.

Author-side evidence after this correction: **24 passed** across SDK-independent `tests/live_mcp`, and **132 passed** across the runnable M10b/M10a/M9/M8/M15 focused matrix. The official SDK live module remains unexecutable in the author container because `mcp` is unavailable there. The Mac full target remains **350 passing tests**. **M10b remains NOT COMPLETE until the Mac real-live module is 11/11 green and the remaining quality/manual gates pass.**


## M10b v0.17.4 release-polish candidate

Status: **CANDIDATE — final release-polish certification pending on macOS.**

User-side v0.17.2 live acceptance established 11/11 real SDK stdio tests, 35/35 M10b tests, 350/350 cumulative tests, 86.15% coverage, real discovery/read/call behavior, pre-sink blocking, exact approval, CTX445 correspondence drift, zero real network/shell/credential effects, and semantic reproduction with identity `sha256:d138529d9563b3baac1e082eb980036c543fc446127b4ec46d1eaae4873b130a`.

v0.17.4 is a release-polish-only candidate. It narrows JSON/cache/runtime types, annotates incremental resolvers/cache APIs, removes remaining structural Ruff findings, and rewrites the fixture's machine-readable `CONTEXTC_META` docstrings as adjacent string literals so their runtime text remains identical while physical source lines remain lintable. No security/capability policy semantics are intentionally changed.

Author-side executable evidence for this candidate:

- SDK-independent M10b: 24 passed, 1 live-SDK module skipped because `mcp` is unavailable.
- Changed-code matrix (`live_mcp`, `capabilities`, `security`, `cache`, `incremental`, `cross_domain`, M4 reproduction): 154 passed, 1 live-SDK skip.
- Whole suite: 332 passed, 5 failed, 3 skipped; all five failures are inherited M5 ILP assertions caused by unavailable PuLP, two skips are PuLP import tests, and one skip is the unavailable live MCP SDK module.
- Runtime `CONTEXTC_META` descriptions were AST-verified to remain valid one-line JSON after the line-length refactor.

Not yet claimed on v0.17.4: macOS live-SDK test execution, whole-project coverage, Ruff clean, Ruff format clean, or strict mypy clean. Those gates must be rerun on the exact candidate before `MILESTONE 10B COMPLETE` is recorded.

## M10b v0.17.4 final polish candidate

v0.17.4 addresses the final macOS post-format residual from v0.17.3: Ruff E501 findings in live MCP fixture metadata docstrings and two strict-mypy TaintPath typing errors. The fixture metadata parser now accepts JSON from the `CONTEXTC_META:` marker through the remainder of the description, allowing formatter-stable multi-line JSON docstrings with unchanged structured metadata values. Security analysis variable naming avoids optional/non-optional type reuse, and cached taint path decoding now rejects null entries explicitly.

Author-side verification for this candidate: 12 fixture metadata docstrings parsed successfully; 24 SDK-independent live MCP tests passed with the one live-SDK module skipped because `mcp` is unavailable in this container; an additional focused M10b/M9 slice passed 30 tests. Ruff, Ruff format, strict mypy, the 11 real stdio MCP SDK tests, the full 350-test macOS suite, and whole-project coverage remain to be certified on the exact v0.17.4 candidate before M10b can be marked complete.


## M10b v0.17.4 certified predecessor

Status: **MILESTONE 10B COMPLETE** based on the final macOS acceptance run.

Final predecessor evidence: MCP SDK 2.1.1; 35/35 live-MCP tests; 350/350 cumulative tests;
86.11% coverage; Ruff, Ruff format, and strict mypy green; current/frozen uv lock green; semantic
reproduction identity `sha256:321a975d170d1fd130653594e49cba6fc6b02158755bfb8cdac64e1864078105`;
Mac-built final wheel SHA-256 `b173c38f6b6ee19517404bf639185cfa6f1f419d1052f63b2b197ade016e0ae2`;
final cumulative M10b source archive SHA-256
`cf047ed5239f92f2a52194904c9a5b6a08ce1f4e4ae4d14659965443c76ed091`.

This section supersedes the earlier candidate/pending M10b status sections retained above as
historical build notes. M16 starts only from the accepted M10b semantics; no M10b behavior is
intentionally changed by M16.

## M16 v0.18.0 release candidate — local Observatory, packaged demos, CI, release engineering

Status: **IN PROGRESS — author-side demo/package regressions are green; final Mac gates remain**.

Implemented:

- typed release-demo registry and `DemoService`;
- four bounded package-resource demos: repository bug, incident response, incremental rebuild, and
  static capability composition;
- `contextc demo registry list|verify`, `contextc demo verify --all`, and `contextc demo run`;
- optional `contextc ui` Streamlit Observatory, imported lazily and bound to loopback by default;
- application-facing Compile/Comparison/Verification service boundaries while preserving all
  predecessor application exports;
- explicit package-data policy, Apache-2.0 license, MANIFEST rules, release audit, and distribution
  comparison tooling;
- M16 CI workflow and required release documentation; installed-UI CI uses Streamlit AppTest to
  verify all four cards from the installed wheel.

Author-side evidence run in this build environment:

- M16 focused: **13 passed, 1 Streamlit-only module skipped** because Streamlit is unavailable;
- release-demo registry generation/check: **PASS**;
- semantic verification/direct run of all four release demos: **PASS**;
- all four release demos with socket network denied: **PASS**;
- focused predecessors: M4 22 pass; M6 19; M11 9; M9 24; M15 23; M8 28; M10a 35;
  M10b 24 pass plus the real-SDK module skipped because `mcp` is unavailable;
- cumulative author suite: **345 passed, 5 failed, 4 skipped**; all five failures are inherited
  M5 ILP assertions caused by unavailable PuLP, two skips are PuLP imports, one is real MCP SDK,
  and one is Streamlit AppTest;
- two independent author distribution builds: wheel and sdist member lists and per-member content
  hashes are identical, but archive bytes are not identical. Wheel variance is timestamps on six
  generated `.dist-info` members; sdist variance is build-time mtime/PAX metadata and gzip-header
  timestamp;
- both compared wheel/sdist pairs pass the release audit;
- final author core-wheel isolation from an unrelated working directory: **PASS** for version,
  registry list/verify, semantic verify-all, and all four demo runs; checkout path absent from
  `sys.path`; core-only UI command produced clean optional-extra guidance;
- author `uv lock --check --offline` remains unclaimable because registry dependencies are absent
  from the offline cache.

Not yet claimed in this environment:

- dependency-complete full suite (Mac target **364 passed**) and >=85% whole-project coverage;
- Ruff, Ruff format, and strict mypy (executables unavailable here);
- regenerated/current 0.18.0 `uv.lock` and frozen-lock install proof;
- installed Streamlit UI startup/AppTest (dependency unavailable here);
- the 11 real M10b stdio SDK tests and M5 ILP tests (dependencies unavailable here);
- authoritative `python -m build` + `twine check` and final hashes on the Mac release toolchain.

Do not declare M16 complete until those gates are run on the exact user-Mac candidate.

## M16 v0.18.0 final macOS certification

Status: **MILESTONE 16 COMPLETE**

This section supersedes the earlier M16 candidate/pending-gate status retained above as
historical build evidence. M16 introduces no new compiler semantics.

Final macOS acceptance evidence:

- dependency-complete cumulative suite: **364 passed**;
- whole-project coverage: **85.50%**, satisfying the >=85% gate;
- Ruff: **PASS**;
- Ruff format: **PASS — 289 files**;
- strict mypy: **PASS — 164 source files**;
- fresh `uv 0.12.10` lock resolution: **140 packages**;
- `uv lock --check`: **PASS**;
- non-editable frozen install from the certified lock: **PASS**;
- frozen-environment full suite: **364 passed**;
- frozen-environment coverage: **85.50%**;
- frozen Ruff, format, and strict mypy: **PASS**;
- M10b real SDK tests execute successfully inside the dependency-complete cumulative suite;
- four packaged release demos verify semantically with no registry problems;
- repository-bug, incident-response, incremental-rebuild, and capability-composition
  hands-on release-demo runs: **PASS**;
- release-demo offline/no-execution boundary: **PASS**;
- Streamlit Observatory hands-on views: **PASS**;
- installed core wheel isolation from the source checkout: **PASS**;
- installed core wheel registry/semantic verification and all four demo runs: **PASS**;
- core-only `contextc ui` optional-extra boundary: **PASS**, expected exit code 2;
- installed `[ui]` wheel isolation: **PASS**;
- installed Streamlit AppTest: **0 exceptions**, all four release-demo cards present;
- final wheel and sdist: `python -m build` **PASS**;
- Twine wheel and sdist checks: **PASS**;
- final wheel and sdist release audit: **PASS**.

Authoritative artifact identities:

- wheel SHA-256:
  `dcee2e233f6ea16101581815a3a634ae6eddb56589783908cc6d1bc9dc678ed3`
- sdist SHA-256:
  `b3835de6c5ca2045475630c3f4130d14d88fd3462809e3ee954341fc8caff2ea`
- certified `uv.lock` SHA-256:
  `f0635e6673fbf46c3ae67792f65c627c54afb81f5c2f59d9c87fceb8db5b91bd`

Package archive byte-reproducibility is deliberately **not claimed**. Earlier independent
author builds produced identical member sets and identical per-member content hashes while the
archive bytes differed because of generated timestamp/mtime metadata. M16 therefore claims
content-equivalent packaging evidence, not byte-identical wheel/sdist archives.

The final M16 completion status is recorded only after the clean cumulative source ZIP has been
constructed and its contents inspected successfully.
