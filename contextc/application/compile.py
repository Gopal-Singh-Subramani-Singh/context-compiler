"""Repository-to-exact-target compilation with M4 transactional evidence."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import cast

from contextc.application.graphing import graph_repository_index
from contextc.cross_domain.adapters import load_source_context
from contextc.cross_domain.conflicts import ConflictResult, analyze_conflicts
from contextc.cross_domain.supersession import (
    SupersessionPolicy,
    SupersessionResult,
    analyze_supersession,
)
from contextc.errors import OptimizerInfeasibleError, SecurityPolicyBlockedError
from contextc.hashing import semantic_hash
from contextc.ir.analysis import NodeAnalysis
from contextc.ir.compilation import CompilationUnit, SelectionResult, SelectionStatus
from contextc.ir.graph import ContextGraph
from contextc.optimization.cascade import DeterministicOptimizerCascade
from contextc.optimization.models import OptimizerConfiguration
from contextc.parsers import IndexResult, RepositoryParser
from contextc.security import (
    ANALYSIS_VERSION as SECURITY_ANALYSIS_VERSION,
)
from contextc.security import (
    SecurityPolicy,
    SecurityResult,
    SecurityService,
    apply_security_result,
    load_policy,
)
from contextc.security import (
    policy_identity as security_policy_identity,
)
from contextc.source_rules import SourceFactRule, source_rules_identity
from contextc.targets import (
    RenderedContext,
    TargetId,
    TargetRenderRequest,
    lower_generic,
    lower_llama,
    lower_qwen,
    lower_structured_json,
    render_structured_record,
)
from contextc.targets.rendering import render_node_segment
from contextc.tokenizers import (
    GenericTokenizer,
    LlamaTokenizerAdapter,
    QwenTokenizerAdapter,
    StructuredJsonTokenizer,
    TargetTokenizer,
)
from contextc.tokenizers.types import ChatTemplateTokenizer, TokenizerIdentity
from contextc.version import __version__

_TERM = re.compile(r"[A-Za-z0-9_]+")


@dataclass(frozen=True, slots=True)
class CompileRepositoryRequest:
    repository: Path
    task: str
    target_id: TargetId
    token_budget: int
    time_anchor: datetime
    tokenizer_model_id: str | None = None
    tokenizer_revision: str | None = None
    tokenizer_local_files_only: bool = True
    source_revision: str | None = None
    policy_id: str = "policy:default"
    policy_version: str = "1.0.0"
    random_seed: int = 0
    system_instruction: str = ""
    developer_instruction: str = ""
    policy_instruction: str = ""
    tool_schema_text: str = ""
    add_generation_prompt: bool = True
    security_policy: SecurityPolicy | None = None
    source_adapter_id: str = "repository"
    source_rules: tuple[SourceFactRule, ...] = ()
    supersession_policy: SupersessionPolicy = field(default_factory=SupersessionPolicy)
    optimizer: OptimizerConfiguration = field(default_factory=OptimizerConfiguration)

    def __post_init__(self) -> None:
        if not self.task:
            raise ValueError("compile task must not be empty")
        if self.token_budget < 1:
            raise ValueError("compile token budget must be positive")
        if self.target_id in {TargetId.QWEN, TargetId.LLAMA} and not self.tokenizer_model_id:
            raise ValueError(f"{self.target_id.value} requires --tokenizer-model")
        if not self.policy_id or not self.policy_version:
            raise ValueError("compile policy identity and version must not be empty")
        if self.security_policy is not None and not isinstance(
            self.security_policy, SecurityPolicy
        ):
            raise ValueError("compile security_policy must be SecurityPolicy or None")
        if not self.source_adapter_id:
            raise ValueError("compile source_adapter_id must not be empty")
        if not all(isinstance(rule, SourceFactRule) for rule in self.source_rules):
            raise ValueError("compile source_rules must contain SourceFactRule values")
        if not isinstance(self.supersession_policy, SupersessionPolicy):
            raise ValueError("compile supersession_policy must be SupersessionPolicy")
        if not isinstance(self.optimizer, OptimizerConfiguration):
            raise ValueError("compile optimizer must be OptimizerConfiguration")


@dataclass(frozen=True, slots=True)
class TargetCompilation:
    index: IndexResult
    source_graph: ContextGraph
    graph: ContextGraph
    security: SecurityResult
    supersession: SupersessionResult
    conflicts: ConflictResult
    security_token_deltas: Mapping[str, tuple[int, int]]
    analyses: tuple[NodeAnalysis, ...]
    selection: SelectionResult
    rendered: RenderedContext


@dataclass(frozen=True, slots=True)
class PreparedTargetInputs:
    """Repository facts and post-security analysis shared across strategies."""

    request_identity: str
    index: IndexResult
    source_graph: ContextGraph
    graph: ContextGraph
    security: SecurityResult
    supersession: SupersessionResult
    conflicts: ConflictResult
    security_token_deltas: Mapping[str, tuple[int, int]]
    analyses: tuple[NodeAnalysis, ...]
    tokenizer: TargetTokenizer


def _load_tokenizer(request: CompileRepositoryRequest) -> TargetTokenizer:
    if request.target_id is TargetId.GENERIC:
        return GenericTokenizer()
    if request.target_id is TargetId.STRUCTURED_JSON:
        return StructuredJsonTokenizer()
    if request.target_id is TargetId.QWEN:
        return QwenTokenizerAdapter(
            model_id=request.tokenizer_model_id or "",
            revision=request.tokenizer_revision,
            local_files_only=request.tokenizer_local_files_only,
        )
    return LlamaTokenizerAdapter(
        model_id=request.tokenizer_model_id or "",
        revision=request.tokenizer_revision,
        local_files_only=request.tokenizer_local_files_only,
    )


def effective_security_policy(request: CompileRepositoryRequest) -> SecurityPolicy:
    """Resolve the deterministic policy used by this compilation."""

    return load_policy() if request.security_policy is None else request.security_policy


def _render_node_for_target(node: object, target_id: TargetId) -> str:
    from contextc.ir import ContextNode

    if not isinstance(node, ContextNode):
        raise AssertionError("expected ContextNode")
    if target_id is TargetId.STRUCTURED_JSON:
        return render_structured_record(node)
    return render_node_segment(node)


def _security_token_deltas(
    source_graph: ContextGraph,
    secured_graph: ContextGraph,
    tokenizer: TargetTokenizer,
    target_id: TargetId,
) -> Mapping[str, tuple[int, int]]:
    deltas: dict[str, tuple[int, int]] = {}
    for node_id in source_graph.node_ids:
        before_node = source_graph.get_node(node_id)
        after_node = secured_graph.get_node(node_id)
        if before_node.normalized_content_hash == after_node.normalized_content_hash:
            continue
        deltas[node_id] = (
            tokenizer.count(_render_node_for_target(before_node, target_id)),
            tokenizer.count(_render_node_for_target(after_node, target_id)),
        )
    return dict(sorted(deltas.items()))


def pipeline_configuration_identity(
    request: CompileRepositoryRequest, tokenizer_identity: TokenizerIdentity
) -> str:
    """Hash every target-lowering configuration input with explicit semantics."""

    return semantic_hash(
        {
            "target_id": request.target_id,
            "tokenizer": tokenizer_identity,
            "system_instruction": request.system_instruction,
            "developer_instruction": request.developer_instruction,
            "policy_instruction": request.policy_instruction,
            "tool_schema_text": request.tool_schema_text,
            "add_generation_prompt": request.add_generation_prompt,
            "security_policy_identity": security_policy_identity(
                effective_security_policy(request)
            ),
            "security_analysis_version": SECURITY_ANALYSIS_VERSION,
            "source_adapter_id": request.source_adapter_id,
            "source_rules_identity": source_rules_identity(request.source_rules),
            "supersession_policy_identity": request.supersession_policy.identity,
            "optimizer": request.optimizer,
        }
    )


def policy_identity(request: CompileRepositoryRequest) -> str:
    """Return the semantic policy identity independently of source IR."""

    return semantic_hash(
        {
            "policy_id": request.policy_id,
            "policy_version": request.policy_version,
            "policy_instruction": request.policy_instruction,
        }
    )


def analyze_node_for_task(
    node: object,
    *,
    task: str,
    tokenizer: TargetTokenizer,
    target_id: TargetId,
    time_anchor: datetime,
    token_count: int | None = None,
) -> NodeAnalysis:
    """Compute the canonical task analysis for one node.

    M8 reuses this exact function while caching target token counts separately.
    """

    from contextc.ir import ContextNode

    if not isinstance(node, ContextNode):
        raise AssertionError("expected ContextNode")
    terms = tuple(term.lower() for term in _TERM.findall(task))
    lowered = node.content.lower()
    relevance = sum(term in lowered for term in terms) / max(1, len(terms))
    freshness = 0.0
    if node.created_at is not None:
        created = datetime.fromisoformat(node.created_at.replace("Z", "+00:00"))
        if created.tzinfo is None or created.utcoffset() is None:
            raise ValueError("node created_at must be timezone-aware")
        if time_anchor.tzinfo is None or time_anchor.utcoffset() is None:
            raise ValueError("compile time_anchor must be timezone-aware")
        age_seconds = max(0.0, (time_anchor - created).total_seconds())
        freshness = 1.0 / (1.0 + age_seconds / 86400.0)
    count = (
        tokenizer.count(_render_node_for_target(node, target_id))
        if token_count is None
        else token_count
    )
    return NodeAnalysis(
        node_id=node.node_id,
        relevance=relevance,
        freshness=freshness,
        token_counts={tokenizer.identity.tokenizer_id: count},
        metadata={
            "analysis": "m3_bounded_lexical_baseline",
            "task_term_count": len(terms),
        },
    )


def _analyze(
    graph: ContextGraph,
    *,
    task: str,
    tokenizer: TargetTokenizer,
    target_id: TargetId,
    time_anchor: datetime,
) -> tuple[NodeAnalysis, ...]:
    return tuple(
        analyze_node_for_task(
            node,
            task=task,
            tokenizer=tokenizer,
            target_id=target_id,
            time_anchor=time_anchor,
        )
        for node in graph.nodes
    )


def _prepared_request_identity(request: CompileRepositoryRequest) -> str:
    return semantic_hash(
        {
            "task": request.task,
            "target_id": request.target_id,
            "token_budget": request.token_budget,
            "time_anchor": request.time_anchor,
            "tokenizer_model_id": request.tokenizer_model_id,
            "tokenizer_revision": request.tokenizer_revision,
            "tokenizer_local_files_only": request.tokenizer_local_files_only,
            "source_revision": request.source_revision,
            "policy_id": request.policy_id,
            "policy_version": request.policy_version,
            "security_policy_identity": security_policy_identity(
                effective_security_policy(request)
            ),
            "security_analysis_version": SECURITY_ANALYSIS_VERSION,
            "source_adapter_id": request.source_adapter_id,
            "source_rules_identity": source_rules_identity(request.source_rules),
            "supersession_policy_identity": request.supersession_policy.identity,
            "random_seed": request.random_seed,
            "system_instruction": request.system_instruction,
            "developer_instruction": request.developer_instruction,
            "policy_instruction": request.policy_instruction,
            "tool_schema_text": request.tool_schema_text,
            "add_generation_prompt": request.add_generation_prompt,
            "objective_weights": request.optimizer.objective_weights,
            "optimizer_limits": request.optimizer.limits,
            "source_content_allowance": request.optimizer.source_content_allowance,
            "mandatory_node_ids": request.optimizer.mandatory_node_ids,
            "blocked_node_ids": request.optimizer.blocked_node_ids,
            "policy_eligible_node_ids": request.optimizer.policy_eligible_node_ids,
        }
    )


def prepare_source_target(request: CompileRepositoryRequest) -> PreparedTargetInputs:
    """Parse any registered source domain and analyze it on the shared pipeline."""

    adapted = load_source_context(
        request.source_adapter_id,
        request.repository,
        revision=request.source_revision,
        source_rules=request.source_rules,
    )
    return _prepare_index_and_graph_target(request, adapted.index, adapted.graph)


def prepare_repository_target(request: CompileRepositoryRequest) -> PreparedTargetInputs:
    """Compatibility wrapper for repository-domain callers."""

    if request.source_adapter_id != "repository":
        return prepare_source_target(request)
    index = RepositoryParser(
        revision=request.source_revision, source_rules=request.source_rules
    ).parse(request.repository)
    return prepare_repository_index_target(request, index)


def prepare_repository_index_target(
    request: CompileRepositoryRequest, index: IndexResult
) -> PreparedTargetInputs:
    """Analyze an already sealed repository index exactly once."""

    return _prepare_index_and_graph_target(request, index, graph_repository_index(index))


AnalysisResolver = Callable[
    [ContextGraph, str, TargetTokenizer, TargetId, datetime], tuple[NodeAnalysis, ...]
]
SecurityResolver = Callable[[ContextGraph, SecurityPolicy], SecurityResult]
SupersessionResolver = Callable[[ContextGraph, SupersessionPolicy], SupersessionResult]


def prepare_adapted_target(
    request: CompileRepositoryRequest,
    index: IndexResult,
    source_graph: ContextGraph,
    *,
    analysis_resolver: AnalysisResolver | None = None,
    security_resolver: SecurityResolver | None = None,
    supersession_resolver: SupersessionResolver | None = None,
) -> PreparedTargetInputs:
    """Prepare already-adapted source facts through the shared compiler pipeline.

    M8 uses this boundary to reuse content-addressed parse/graph results while
    preserving exactly the same downstream compiler implementation.
    """

    return _prepare_index_and_graph_target(
        request,
        index,
        source_graph,
        analysis_resolver=analysis_resolver,
        security_resolver=security_resolver,
        supersession_resolver=supersession_resolver,
    )


def _prepare_index_and_graph_target(
    request: CompileRepositoryRequest,
    index: IndexResult,
    source_graph: ContextGraph,
    *,
    analysis_resolver: AnalysisResolver | None = None,
    security_resolver: SecurityResolver | None = None,
    supersession_resolver: SupersessionResolver | None = None,
) -> PreparedTargetInputs:
    tokenizer = _load_tokenizer(request)
    supersession = (
        analyze_supersession(source_graph, request.supersession_policy)
        if supersession_resolver is None
        else supersession_resolver(source_graph, request.supersession_policy)
    )
    conflicts = analyze_conflicts(source_graph)
    active_security_policy = effective_security_policy(request)
    security = (
        SecurityService(active_security_policy).scan_graph(source_graph)
        if security_resolver is None
        else security_resolver(source_graph, active_security_policy)
    )
    if security.blocked:
        raise SecurityPolicyBlockedError(
            blocked_node_ids=security.blocked_node_ids,
            rule_ids=tuple(
                sorted(
                    {
                        decision.rule_id
                        for decision in security.decisions
                        if decision.node_id in security.blocked_node_ids
                    }
                )
            ),
        )
    graph = apply_security_result(source_graph, security)
    token_deltas = _security_token_deltas(source_graph, graph, tokenizer, request.target_id)
    analyses = (
        _analyze(
            graph,
            task=request.task,
            tokenizer=tokenizer,
            target_id=request.target_id,
            time_anchor=request.time_anchor,
        )
        if analysis_resolver is None
        else analysis_resolver(
            graph, request.task, tokenizer, request.target_id, request.time_anchor
        )
    )
    return PreparedTargetInputs(
        request_identity=_prepared_request_identity(request),
        index=index,
        source_graph=source_graph,
        graph=graph,
        security=security,
        supersession=supersession,
        conflicts=conflicts,
        security_token_deltas=token_deltas,
        analyses=analyses,
        tokenizer=tokenizer,
    )


def compile_prepared_target(
    request: CompileRepositoryRequest, prepared: PreparedTargetInputs
) -> TargetCompilation:
    """Select and lower from sealed shared inputs without reparsing sources."""

    if _prepared_request_identity(request) != prepared.request_identity:
        raise ValueError("prepared target inputs do not match compile request")
    tokenizer = prepared.tokenizer
    index = prepared.index
    source_graph = prepared.source_graph
    graph = prepared.graph
    security = prepared.security
    supersession = prepared.supersession
    conflicts = prepared.conflicts
    analyses = prepared.analyses
    return _compile_prepared_target_body(
        request,
        tokenizer=tokenizer,
        index=index,
        source_graph=source_graph,
        graph=graph,
        security=security,
        supersession=supersession,
        conflicts=conflicts,
        security_token_deltas=prepared.security_token_deltas,
        analyses=analyses,
    )


def compile_source_target(request: CompileRepositoryRequest) -> TargetCompilation:
    """Compile any registered source domain without writing."""

    return compile_prepared_target(request, prepare_source_target(request))


def compile_repository_target(request: CompileRepositoryRequest) -> TargetCompilation:
    """Compatibility wrapper preserving the repository compilation API."""

    if request.source_adapter_id == "repository":
        return compile_prepared_target(request, prepare_repository_target(request))
    return compile_source_target(request)


def _compile_prepared_target_body(
    request: CompileRepositoryRequest,
    *,
    tokenizer: TargetTokenizer,
    index: IndexResult,
    source_graph: ContextGraph,
    graph: ContextGraph,
    security: SecurityResult,
    supersession: SupersessionResult,
    conflicts: ConflictResult,
    security_token_deltas: Mapping[str, tuple[int, int]],
    analyses: tuple[NodeAnalysis, ...],
) -> TargetCompilation:
    analysis_map = {analysis.node_id: analysis for analysis in analyses}
    compilation = CompilationUnit(
        task_id=semantic_hash({"task": request.task}),
        task_description=request.task,
        target_id=request.target_id.value,
        tokenizer_id=tokenizer.identity.tokenizer_id,
        token_budget=request.token_budget,
        policy_id=request.policy_id,
        source_revision=request.source_revision,
        time_anchor=request.time_anchor,
        random_seed=request.random_seed,
        compiler_version=__version__,
        pipeline_config_hash=pipeline_configuration_identity(request, tokenizer.identity),
        optimizer=request.optimizer,
    )
    empty_selection = SelectionResult(
        selected_node_ids=(),
        requested_strategy_id=request.optimizer.requested_strategy,
        strategy_id="naive",
        optimizer_status=SelectionStatus.FEASIBLE,
        available_tokens=request.token_budget,
    )
    empty_request = TargetRenderRequest(
        graph=graph,
        selection=empty_selection,
        compilation=compilation,
        system_instruction=request.system_instruction,
        developer_instruction=request.developer_instruction,
        user_instruction=request.task,
        policy_instruction=request.policy_instruction,
        tool_schema_text=request.tool_schema_text,
        add_generation_prompt=request.add_generation_prompt,
    )
    if request.target_id is TargetId.GENERIC:
        empty_rendered = lower_generic(empty_request, tokenizer=cast(GenericTokenizer, tokenizer))
    elif request.target_id is TargetId.STRUCTURED_JSON:
        empty_rendered = lower_structured_json(
            empty_request, tokenizer=cast(StructuredJsonTokenizer, tokenizer)
        )
    elif request.target_id is TargetId.QWEN:
        empty_rendered = lower_qwen(empty_request, tokenizer=cast(ChatTemplateTokenizer, tokenizer))
    else:
        empty_rendered = lower_llama(
            empty_request, tokenizer=cast(ChatTemplateTokenizer, tokenizer)
        )
    target_allowance = empty_rendered.budget_evidence.source_allowance_tokens
    configured_allowance = request.optimizer.source_content_allowance
    effective_allowance = (
        target_allowance
        if configured_allowance is None
        else min(configured_allowance, target_allowance)
    )
    security_blocked = tuple(
        sorted(
            set(request.optimizer.blocked_node_ids)
            | set(security.excluded_node_ids)
            | set(supersession.superseded_node_ids)
        )
    )
    effective_optimizer = replace(
        request.optimizer,
        source_content_allowance=effective_allowance,
        blocked_node_ids=security_blocked,
    )
    compilation = replace(compilation, optimizer=effective_optimizer)
    selection = DeterministicOptimizerCascade().select(graph, analysis_map, compilation)
    if selection.optimizer_status is SelectionStatus.INFEASIBLE:
        raise OptimizerInfeasibleError(
            selection.fallback_reason or "mandatory selection cannot fit"
        )
    lowering_request = TargetRenderRequest(
        graph=graph,
        selection=selection,
        compilation=compilation,
        system_instruction=request.system_instruction,
        developer_instruction=request.developer_instruction,
        user_instruction=request.task,
        policy_instruction=request.policy_instruction,
        tool_schema_text=request.tool_schema_text,
        add_generation_prompt=request.add_generation_prompt,
    )
    if request.target_id is TargetId.GENERIC:
        if not isinstance(tokenizer, GenericTokenizer):
            raise AssertionError("Generic target did not load GenericTokenizer")
        rendered = lower_generic(lowering_request, tokenizer=tokenizer)
    elif request.target_id is TargetId.STRUCTURED_JSON:
        if not isinstance(tokenizer, StructuredJsonTokenizer):
            raise AssertionError("structured-json target did not load StructuredJsonTokenizer")
        rendered = lower_structured_json(lowering_request, tokenizer=tokenizer)
    elif request.target_id is TargetId.QWEN:
        rendered = lower_qwen(
            lowering_request,
            tokenizer=cast(ChatTemplateTokenizer, tokenizer),
        )
    else:
        rendered = lower_llama(
            lowering_request,
            tokenizer=cast(ChatTemplateTokenizer, tokenizer),
        )
    return TargetCompilation(
        index=index,
        source_graph=source_graph,
        graph=graph,
        security=security,
        supersession=supersession,
        conflicts=conflicts,
        security_token_deltas=security_token_deltas,
        analyses=analyses,
        selection=selection,
        rendered=rendered,
    )


def compile_source_to_path(
    request: CompileRepositoryRequest,
    output_path: Path,
    *,
    manifest_path: Path | None = None,
    fault_at: str | None = None,
) -> TargetCompilation:
    """Compile and transactionally commit an artifact/manifest pair."""

    from contextc.errors import ArtifactTransactionError
    from contextc.reproduction.service import write_compilation_transaction

    if fault_at == "render":
        raise ArtifactTransactionError("render", RuntimeError("injected render failure"))
    result = compile_source_target(request)
    write_compilation_transaction(
        request=request,
        result=result,
        artifact_path=output_path,
        manifest_path=manifest_path,
        fault_at=fault_at,
    )
    return result


def compile_repository_to_path(
    request: CompileRepositoryRequest,
    output_path: Path,
    *,
    manifest_path: Path | None = None,
    fault_at: str | None = None,
) -> TargetCompilation:
    """Compatibility wrapper for the original repository-domain public API."""

    return compile_source_to_path(
        request, output_path, manifest_path=manifest_path, fault_at=fault_at
    )


CompileSourceRequest = CompileRepositoryRequest
