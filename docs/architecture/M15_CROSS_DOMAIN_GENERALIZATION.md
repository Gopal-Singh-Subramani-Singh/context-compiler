# M15 Cross-Domain Generalization

## Purpose

M15 demonstrates that Context Compiler is source-neutral rather than repository-only. The second
bounded domain is an offline incident-response investigation assembled from retained markdown,
JSON, JSONL, YAML, conversation, procedure, observation, event, record, and static MCP sources.

The incident domain does not introduce a second compiler. Domain-specific behavior stops at the
source-adapter boundary and evaluator boundary.

## Shared compiler invariants

| Concern | Repository domain | Incident-response domain |
| --- | --- | --- |
| Source boundary | `RepositoryAdapter` | `IncidentAdapter` |
| Immutable IR | `ContextNode` / `SourceReference` | same |
| Graph | `ContextGraph` / `ContextEdge` | same |
| Task analysis | shared lexical/freshness analysis | same |
| Security | M9 `SecurityService` | same |
| Supersession | explicit `SUPERSEDES` edges | same generic pass |
| Selection | M5 strategy registry | same |
| Dependency closure | configured dependency edge types only | same |
| Budget | target-specific exact final recount | same |
| Artifact transaction | M4 transaction | same |
| Manifest | BuildManifest schema 1.3 | same |
| Verify / rebuild | M4 reproduction service | same |

No optimizer contains an incident-specific branch.

## Source adapter contract

`SourceAdapter` produces an `AdaptedContext` containing a normalized `IndexResult` and a typed
`ContextGraph`. The compiler receives only those universal structures. `RepositoryAdapter`
continues to reuse `RepositoryParser`; `IncidentAdapter` normalizes the retained incident fixture.

Incident provenance uses stable `incident://<incident-id>/<path>` URIs. Retained MCP JSON is parsed
by the unchanged M9 static MCP parser and therefore retains `mcp://...` provenance and the M9
authority boundary.

## Universal M15 relationships

The incident fixture exercises `REFERENCES`, `CONTRADICTS`, `RESPONDS_TO`, `CAUSES`, `RESOLVES`,
`CORRELATES_WITH`, `SUPPORTS`, `SUPERSEDES`, `REQUIRES`, and M9 `TAINTS` relationships. Only the
configured dependency edge vocabulary participates in dependency closure; informational
relationships never become dependencies merely because they exist.

## Structural supersession

Supersession is explicit and deterministic. An edge `old -> new` with type `SUPERSEDES` means the
old node is structurally ineligible for final selection under the default supersession policy.
The compiler emits `CTX210` with stored old/new/edge evidence. Timestamps and words such as
"latest" or "old" do not create supersession by themselves. A regression test swaps timestamps
and proves the explicit edge still wins.

## Conflict semantics

`CONTRADICTS` and `CONFLICTS` edges emit `CTX200` evidence but do not automatically block
compilation. They are investigative relationships, not hard dependency constraints.

## M9 security reuse

The malicious retained MCP result is processed without any M15-specific security branch. The M9
engine preserves `instruction_authority=none`, emits `CTX400`, `CTX420`, and `CTX425`, and applies
`QUOTE_AS_DATA`. M15 intentionally does not emit `CTX440`; capability-composition analysis remains
owned by M10a.

## Structured JSON target

`structured-json` is an ordinary target lowerer with a dedicated exact tokenizer. It emits a
deterministic ordered record array carrying content, provenance, trust, sensitivity, authority,
transformations, metadata, and source timestamps. It uses the same `enforce_final_budget`
machinery as the other targets, so the final rendered token count is authoritative.

## Evaluator isolation

Incident labels live under the fixture's `evaluator/` directory and are imported only by
`contextc.cross_domain.evaluator`. The compiler, parser, source adapter, security pipeline, and
selection code never read them. The fixture includes an evaluator-only sentinel and tests prove it
is absent from compiler-visible nodes.

M15 reuses the existing M6 raw metric implementation and adds domain-only relation coverage,
superseded-content exclusion, and security-policy correctness metrics. M6 metric definitions are
not changed.

## Equal-footing comparison

All strategies compile one shared prepared source analysis. The equal-footing fingerprint includes
task, graph, analysis, target/tokenizer, exact budget inputs, objective/limits, dependency policy,
security-policy identity, source-adapter identity, supersession-policy identity, and other
semantic inputs while intentionally excluding only strategy identity. `top_k` reports fallback
when semantic scores are unavailable; lexical relevance is never relabeled as semantic.

## Bounded claim

M15 demonstrates source-neutral compiler architecture on one deterministic offline incident fixture.
It is not evidence of universal domain coverage, production incident-response correctness, or
complete security against prompt injection or tool-capability composition.
