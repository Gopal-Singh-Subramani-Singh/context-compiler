# Changelog

## 0.18.0 - M16 release candidate

- Added a package-resource release-demo registry with four bounded offline demonstrations.
- Added installed-wheel demo verification and run commands.
- Added an optional local read-only Streamlit Observatory behind the `ui` extra.
- Added typed Compile, Comparison, Verification, and Demo service boundaries for presentation use.
- Added wheel/sdist release auditing, package-content narrowing, and distribution comparison tools.
- Added M16 CI jobs for quality, regressions, demos, packaging, installed core/UI, security, and
  clean-build validation.
- Added installation, demo, Observatory, limitations, and release-process documentation.
- No new compiler semantics were introduced.


## 0.17.4 - 2026-09-04

- Completed M10b real local MCP acceptance on macOS with MCP SDK 2.1.1.
- Certified 35/35 live-MCP tests, 350/350 cumulative tests, 86.11% coverage, Ruff,
  Ruff format, strict mypy, current uv lock, frozen install, semantic reproduction, build,
  and distribution metadata checks.
- Preserved the bounded M10b claim: real local stdio protocol validation with pre-sink
  enforcement, CTX445 correspondence drift detection, synthetic-secret-only approval testing,
  and zero real external network or shell execution.


## 0.17.3 - 2026-09-04

- Release-polish candidate after successful real/live M10b acceptance on macOS.
- Narrowed JSON/cache/live-MCP boundaries for strict typing without changing security semantics.
- Removed remaining targeted Ruff structural issues and made bounded MCP metadata line-safe while preserving exact runtime descriptions.
- Preserved the v0.17.2 initialization/operation-timeout behavior and all M10b pre-sink enforcement semantics.
- Author environment: 24 SDK-independent live-MCP tests pass; focused changed-code matrix 154 passes with only the live SDK test skipped; whole suite remains limited by unavailable PuLP/MCP SDK.
- Final M10b completion remains pending macOS `ruff check`, `ruff format --check`, `mypy --strict`, full 350-test/coverage, and live-SDK certification on this exact candidate.

## 0.17.2 - 2026-09-04

- Separate live MCP startup/initialization timeout from per-operation timeout so real stdio startup can have a generous bound while `tools/call` remains tightly bounded.
- Add `--operation-timeout` to live MCP CLI commands; when omitted it inherits `--timeout`.
- Correct the real delayed-tool timeout fixture to stay inside the server's 2000 ms bounded-delay safety limit while still timing out at the client boundary.

## 0.17.1 - 2026-09-04

- Fix the real MCP stdio error boundary discovered by Mac acceptance: AnyIO/MCP task-group teardown can wrap Context Compiler typed live-MCP errors in nested `ExceptionGroup` instances. The client adapter now restores the original typed `ContextCompilerError` before it crosses the application boundary.
- Preserve an existing `MCPToolInvocationError` instead of wrapping it a second time when the MCP SDK returns an error result.
- Make the live timeout acceptance exercise an actual `tools/call` timeout rather than relying on an unrealistically small 50 ms subprocess-initialization budget.
- Add an SDK-independent regression that simulates nested session/stdio exception groups and proves `MCPResourceReadError` is surfaced directly.
- Real-Mac live MCP acceptance must be rerun before M10b may be declared complete.

## 0.17.0 - 2026-09-04

- Add M10b bounded **real local MCP** validation through the maintained Python MCP SDK over stdio.
- Add a marked tiny fixture server with sandbox-only reads/writes and fake external/message, execution, and network sinks; no real network request or shell execution occurs.
- Normalize live tool/resource declarations into the existing M10a capability model and runtime tool results into M9 source facts with instruction authority `none`.
- Add pre-sink live enforcement that reuses M10a flow-scoped approvals and hard-block semantics.
- Add runtime declaration correspondence and CTX445 for observed behavior that exceeds or contradicts the live declaration snapshot.
- Add secret-safe runtime observations, audit evidence, stored-evidence explanation, semantic reproduction forms, bounded timeouts, typed live-MCP errors, and M8-backed static declaration/capability caching.
- Add real-stdio integration tests for lifecycle, discovery, resource reads, safe calls, sensitive/external, untrusted/execution, credential/network, approval, mismatch, traversal, timeout, and failure behavior.
- Keep live MCP optional via the `live-mcp` extra; core Context Compiler startup does not require the MCP SDK.

## 0.16.0 - 2026-09-04

- Add M10a static MCP capability/composition analysis without live tool execution.
- Add typed tool/resource declarations, the stable capability vocabulary, proposed call plans, deterministic capability graphs, bounded ordered flows, and flow-scoped approval evidence.
- Detect sensitive/secret -> external/message/network composition, untrusted output -> shell/code execution, and credential/environment access -> network send using CTX440.
- Emit CTX441 for incomplete declarations, CTX442 for structurally invalid plans, CTX443 for exact explicit approval requirements, and CTX444 for policy/evidence failures.
- Add a versioned canonical capability policy and packaged default policy.
- Add `contextc mcp plan validate|analyze|explain` with explicit static/no-execution evidence.
- Add M8 capability-stage cache keys over declaration, plan, policy, analysis-version, limit, and approval identities; declaration changes do not invalidate unrelated parser stages.
- Add secret-safe capability manifests/explanations and tests proving raw literal secrets are absent from diagnostics, manifests, and cache payloads.
- Add deterministic graph/flow ordering, bounded traversal, approval scoping, cache reuse/invalidation, and M9/M8 regression coverage.

## 0.14.0 - 2026-09-03

- Complete the remaining M9 real-filesystem ingestion gap on top of M15.
- Add deterministic `contextc.toml` / `[tool.contextc]` `source_rules` for repository-relative path classification.
- Allow safe trust downgrades (`external_content`, `retrieved_document`, `unverified_tool`) and sensitivity escalation (`sensitive`, `secret`) while preventing repository-local privilege promotion, declassification to public, or instruction-authority grants.
- Apply source rules during `contextc index` and normal repository compilation before M9 security analysis.
- Persist ordered source-rule semantics in build manifests and reproduction requests; changing classified files or classification config invalidates source verification.
- Add real-file tests proving `SECRET -> CTX410 -> REDACT`, external-content classification driving policy transforms, canary non-retention, and byte-identical verify/rebuild.
- Bump BuildManifest schema to 1.4.


## 0.13.0 - 2026-09-03

- Add a source-neutral `SourceAdapter` boundary and route repository and incident sources through
  the same compile/analyze/select/lower/reproduce pipeline.
- Add a deterministic 21-source offline incident-response fixture spanning retained markdown, JSON,
  JSONL, YAML, monitoring, service ownership, procedures, conversation history, and static MCP.
- Add universal cross-domain relationships and deterministic structural supersession: explicit
  `SUPERSEDES` marks stale content ineligible and records `CTX210`; `CONTRADICTS`/`CONFLICTS` record
  non-blocking `CTX200` evidence.
- Reuse the M9 security engine unchanged for retained malicious MCP content and deliberately defer
  `CTX440` capability-composition analysis to M10a.
- Add the deterministic `structured-json` target with target-specific exact token accounting and the
  existing authoritative final-budget enforcement.
- Extend BuildManifest to schema 1.3 with `source_adapter_id` so incident builds verify and rebuild
  through the same M4 reproduction service.
- Add isolated incident evaluator metrics, shared M6 raw metrics, equal-footing strategy comparison,
  and a typed `contextc demo` application/CLI surface.

## 0.12.1 - 2026-09-03

- Complete M9 integration by running structural security before task analysis, token costing,
  optimizer selection, target lowering, and artifact commit.
- Make security exclusions optimizer-ineligible without deleting structural dependency evidence;
  mandatory dependency closure now fails rather than silently reintroducing an excluded node.
- Recalculate target-specific node token costs after quote/redact transformations and preserve
  exact final target recounting as the authoritative budget check.
- Abort blocking policies before the artifact transaction and return the dedicated CLI exit code
  `3` without leaving an artifact, manifest, or staged temporary file.
- Extend the M4 manifest/reproduction contract with canonical M9 policy identity, analysis
  version, diagnostic/rule IDs, taint summaries, transformations, exclusions, immutable source
  security facts, and token deltas; rebuild replays the stored policy and compares bytes and
  semantic evidence.
- Extend stored `explain --node` evidence with trust domain, sensitivity, instruction authority,
  security decisions, transformations, exclusion state, and token impact without rerunning the
  compiler.
- Emit the promised `CTX410` diagnostic for local secret/sensitivity policy redaction and add
  regressions proving redacted payloads do not enter artifact, manifest, or stored explanation
  evidence.

## 0.11.1 - 2026-09-03

- Corrected the setuptools build-backend floor for the PEP 639 SPDX license string.
- Added the compatible setuptools backend to development extras so `python -m build
  --no-isolation` works after a clean `pip install -e '.[dev]'` on Python 3.11.
- Restricted package discovery to `contextc` and `contextc.*`, preventing transient
  historical checkouts whose names share the prefix from entering a distribution.

## 0.11.0 - 2026-09-03

- Add an eight-task historical case study from the MIT-licensed python-humanize repository,
  backed by an immutable offline Git bundle and exact pre-fix/fix revisions.
- Add separated public tasks, evaluator labels, approved manual reviews, canonical source spans,
  real fix-diff validation, and evaluator-sentinel leakage checks.
- Reuse the M5 strategy contract, M6 equal-footing fingerprints, and all ten M6 raw metrics for
  real-repository comparisons; correct only floating-point boundary drift in proportional M6
  attribution exposed by long real files.
- Add shared sealed parsing/analysis for equal-footing strategy runs, reverse-creation-order and
  repeated-run determinism checks, raw JSON/Markdown reporting, and review-only label extraction.
- Add `contextc case-study list`, `validate`, `extract-labels`, `run`, `report`, and
  `verify-determinism` commands.

## 0.6.0 - 2026-09-02

- Replace node-ID benchmark labels with canonical repository URIs and inclusive source spans.
- Add ten separately reported raw metrics with hand-calculated overlap, duplicate, distractor,
  empty-set, and infeasible policies.
- Enforce cross-strategy equal-footing fingerprints and a physical public/evaluator boundary.
- Add evaluator-isolated Top-K tracing with explicit no-embedding fallback evidence.
- Add versioned transactional SQLite storage, raw reports, one-task debug inspection, and an
  eight-task controlled suite covering all nine M5 strategies.

## 0.5.1 - 2026-09-01

- Derive a deterministic minimal dependency-closure seed set for exact solver selections so ILP
  manifests report dependency-forced nodes consistently with brute-force and closure strategies.
- Add an exact brute-force/ILP forced-inclusion agreement regression exposed by the public M5
  hands-on strategy comparison.

## 0.5.0 - 2026-08-31

- Add one versioned weighted objective and shared constraint/closure/allowance validator for all
  optimizer strategies.
- Add deterministic `naive`, `recency`, `top_k`, relevance/density greedy, bounded brute-force,
  bounded dependency-free DP, optional ILP, and graph-closure greedy strategies.
- Add the central deterministic optimizer cascade, source-aware tie rules, bounded tie evidence,
  explicit infeasibility, fallback, heuristic, timeout-incumbent, feasible, and optimal statuses.
- Reserve exact target overhead before selection and use target-specific rendered-segment costs.
- Extend manifests, rebuild inputs, stored inspection, and node explanations with complete M5
  optimizer evidence while keeping measured runtime outside semantic build identity.
- Add exact-method oracle agreement, three greedy counterexamples, transitive/shared-dependency,
  policy, mandatory overflow, insertion-order determinism, real CBC, and forced-timeout tests.

## 0.4.0 - 2026-08-29

- Add a strict versioned `BuildManifest` with canonical semantic identity, portable paths,
  source/node/configuration/tokenizer/selection/budget/optimizer/diagnostic evidence, and
  cryptographic artifact identity.
- Commit artifacts and manifests through a staged, flushed, rollback-capable two-file transaction
  with the manifest as the final validity marker.
- Add read-only `contextc reproduce MANIFEST --verify` checks for schema, artifact bytes, exact
  token recount, internal consistency, semantic inputs, and available source evidence.
- Add source-driven `--rebuild --output DEST` with explicit compatibility gates and exact
  comparison of selection, ordering, rendered bytes, token counts, identities, and semantic
  manifest fields before committing a fresh pair.
- Add stored-evidence `inspect` and `explain` commands, a local regression fixture, tamper tests,
  and fault injection across rendering, staging, serialization, and commit boundaries.

## 0.3.1 - 2026-08-29

- Include Jinja2 in the Qwen and Llama extras after real public-tokenizer verification exposed
  the missing chat-template runtime.
- Report missing chat-template runtimes as typed CTX710 failures with installation guidance and
  preserved causes.
- Preserve configured developer, policy, and tool-schema text for model templates that do not
  define a dedicated developer role by labeling and lowering it into the system message.
- Add packaging, missing-runtime, and target-message preservation regression tests.

## 0.3.0 - 2026-08-29

- Add strict tokenizer identity/count/encode contracts and an honestly named Generic
  approximation.
- Add lazy configured Qwen and Llama adapters using actual tokenizer chat templates, with typed
  CTX710 failures and no Generic fallback.
- Add typed Generic/Qwen/Llama lowering, exact fully rendered recounting, fixed-overhead and
  source-allowance evidence, deterministic closure-safe final trimming, and CTX510 failure.
- Add complete source maps, separate final-trim evidence, atomic target writes, and M4-ready
  target manifest fields.
- Add the `contextc compile` command and target-focused boundary, invariant, determinism, and
  atomic-failure tests.

## 0.2.0 - 2026-08-28

- Add explicit major/minor schema policies and typed CTX720 rejection.
- Finalize source-neutral nodes, bounded task analysis, compilation requests, and selection
  evidence contracts.
- Add deterministic typed multigraph semantics, dependency closure, stable cycle evidence, and
  topological dependency ordering.
- Add the non-optimizing deterministic selection protocol baseline.
- Add stored-evidence node explanations with separate terminal formatting.
- Add static local import/call/definition graph construction and M2 end-to-end integration.

## 0.1.0 - 2026-08-28

- Establish the M1 installable Python package and CLI.
- Add canonical semantic JSON and SHA-256 identities.
- Add immutable Version-2 source IR and separate task-analysis/selection types.
- Add structured diagnostic models and the authoritative registry.
- Add deterministic, non-executing Python and generic-text repository indexing.
- Add the dependency-light Generic compilation smoke path.

## 0.12.0 — M9 security policy and static MCP source analysis

- Added partial trust-relation policy semantics over the established immutable `TrustDomain` facts.
- Added typed security policy actions, deterministic pattern signals, bounded TAINTS/ENABLES traversal, decisions, transformations, and result evidence.
- Added CTX400/CTX420/CTX425/CTX430 analysis behavior without changing their established registry meanings.
- Added local secret redaction that applies even without an external-flow path.
- Added a static MCP-shaped JSON parser with stable `mcp://` provenance and `instruction_authority=none` by default.
- Added malicious and benign offline MCP fixtures plus CLI `policy validate`, `security scan`, and `security explain` surfaces.
- Added M9 true-positive, false-positive, policy-variation, taint-cycle, secret-leak, and parser tests.

## 0.15.0 - M8 incremental compilation

- Added local content-addressed cache objects and canonical computation metadata with atomic writes and corruption quarantine.
- Added narrow pass-versioned stage keys, dependency index, source URI index, and dependency-aware dry-run/apply invalidation.
- Added verified incremental compilation with actual reuse of parse/static graph, security, supersession, target-token, and per-node task-analysis stages.
- Added semantic incremental/full equivalence checks including rendered bytes, exact tokens, selection/order, security/supersession evidence, and `BuildManifest.semantic_form()`; divergence is CTX704.
- Added CTX700-CTX704 cache/incremental diagnostics.
- Added `contextc compile --incremental --verify-incremental --cache-root ...` and `contextc cache stats|inspect|verify|plan-invalidation|invalidate`.
- Added whole-line policy comments so comment-only policy edits preserve canonical M9 policy identity.
- Added fresh M8 baseline index, M11 real-repository incremental equivalence, M15 incident incremental equivalence, corruption recovery, cache-independent reproduction, and secret non-disclosure tests.
