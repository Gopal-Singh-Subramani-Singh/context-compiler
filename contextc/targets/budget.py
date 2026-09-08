"""Exact final-target budget enforcement with deterministic closure-safe trimming."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from contextc.diagnostics import Diagnostic, DiagnosticCode, get_definition
from contextc.errors import FinalBudgetOverflowError, GraphInvariantError, TargetLoweringError
from contextc.ir.graph import ContextGraph
from contextc.targets.rendering import RenderDraft, source_map_for_draft
from contextc.targets.types import (
    RenderedContext,
    TargetId,
    TargetRenderRequest,
    TokenBudgetEvidence,
    TrimEvidence,
)
from contextc.tokenizers.types import TargetTokenizer

RenderFunction = Callable[[TargetRenderRequest, Sequence[str]], RenderDraft]


def _validate_request(
    *, target_id: TargetId, request: TargetRenderRequest, tokenizer: TargetTokenizer
) -> None:
    compilation = request.compilation
    if compilation.target_id != target_id.value:
        raise TargetLoweringError("compilation target does not match target lowerer")
    if compilation.tokenizer_id != tokenizer.identity.tokenizer_id:
        raise TargetLoweringError("compilation tokenizer does not match target tokenizer")
    selected = request.selection.selected_node_ids
    for node_id in selected:
        request.graph.get_node(node_id)
    blocked = set(request.blocked_node_ids)
    if blocked & set(selected):
        raise TargetLoweringError("blocked nodes may not enter target lowering")
    closure = request.graph.dependency_closure(selected)
    missing_from_selection = set(closure.node_ids) - set(selected)
    if closure.missing_node_ids or missing_from_selection:
        raise GraphInvariantError(
            f"selected nodes do not preserve dependency closure: {sorted(missing_from_selection)}"
        )


def _dependent_cluster(graph: ContextGraph, candidate: str, selected: set[str]) -> tuple[str, ...]:
    """Return a node and every selected node transitively depending on it."""

    cluster = {candidate}
    pending = [candidate]
    while pending:
        dependency = pending.pop()
        dependents = sorted(
            {
                edge.source_node_id
                for edge in graph.incoming_edges(dependency, kinds=graph.dependency_edge_types)
                if edge.source_node_id in selected
            }
        )
        for dependent in dependents:
            if dependent not in cluster:
                cluster.add(dependent)
                pending.append(dependent)
    return tuple(sorted(cluster))


def _trim_diagnostic(evidence: TrimEvidence) -> Diagnostic:
    definition = get_definition(DiagnosticCode.EXCLUDED_BY_TOKEN_BUDGET)
    return Diagnostic(
        code=definition.code,
        severity=definition.default_severity,
        message=definition.title,
        node_ids=evidence.removed_node_ids,
        evidence={
            "iteration": evidence.iteration,
            "token_count_before": evidence.token_count_before,
            "token_count_after": evidence.token_count_after,
            "reason": evidence.reason,
        },
        owning_pass="target_budget",
    )


def _overflow(
    target_id: TargetId, request: TargetRenderRequest, final_count: int, reason: str
) -> FinalBudgetOverflowError:
    return FinalBudgetOverflowError(
        target_id=target_id.value,
        token_budget=request.compilation.token_budget,
        final_token_count=final_count,
        reason=reason,
    )


def enforce_final_budget(
    *,
    target_id: TargetId,
    request: TargetRenderRequest,
    tokenizer: TargetTokenizer,
    render_draft: RenderFunction,
) -> RenderedContext:
    """Render, recount, and deterministically trim until the final package fits."""

    _validate_request(target_id=target_id, request=request, tokenizer=tokenizer)
    budget = request.compilation.token_budget
    selected = list(request.selection.selected_node_ids)
    selected_set = set(selected)
    protected = set(request.graph.dependency_closure(request.selection.mandatory_node_ids).node_ids)

    empty_draft = render_draft(request, ())
    fixed_overhead = tokenizer.count(empty_draft.text)
    draft = render_draft(request, selected)
    current_count = tokenizer.count(draft.text)
    pre_trim_count = current_count
    trims: list[TrimEvidence] = []

    for iteration in range(1, request.max_trim_iterations + 1):
        if current_count <= budget:
            break
        removable: tuple[str, ...] | None = None
        for candidate in reversed(selected):
            cluster = _dependent_cluster(request.graph, candidate, selected_set)
            if not (set(cluster) & protected):
                removable = cluster
                break
        if removable is None:
            raise _overflow(
                target_id,
                request,
                current_count,
                "mandatory dependency closure and fixed target overhead cannot fit",
            )
        before = current_count
        removed = set(removable)
        selected = [node_id for node_id in selected if node_id not in removed]
        selected_set.difference_update(removed)
        draft = render_draft(request, selected)
        current_count = tokenizer.count(draft.text)
        trims.append(
            TrimEvidence(
                iteration=iteration,
                removed_node_ids=tuple(
                    node_id for node_id in request.selection.selected_node_ids if node_id in removed
                ),
                token_count_before=before,
                token_count_after=current_count,
            )
        )
    else:
        raise _overflow(
            target_id,
            request,
            current_count,
            "bounded trim iteration limit was reached",
        )

    final_count = tokenizer.count(draft.text)
    if final_count > budget:
        raise _overflow(target_id, request, final_count, "exact final recount failed")
    diagnostics = request.selection.diagnostics + tuple(_trim_diagnostic(item) for item in trims)
    return RenderedContext(
        target_id=target_id,
        rendered_text=draft.text,
        exact_token_count=final_count,
        ordered_node_ids=tuple(selected),
        source_map=source_map_for_draft(draft),
        trim_evidence=tuple(trims),
        diagnostics=diagnostics,
        tokenizer_identity=tokenizer.identity,
        budget_evidence=TokenBudgetEvidence(
            configured_budget=budget,
            fixed_overhead_tokens=fixed_overhead,
            source_allowance_tokens=max(0, budget - fixed_overhead),
            pre_trim_selected_tokens=pre_trim_count,
            final_token_count=final_count,
        ),
    )
