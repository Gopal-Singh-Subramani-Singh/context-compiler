"""Stored-evidence explanation models and separate terminal formatting."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from contextc.canonical import freeze_value, to_canonical_primitive
from contextc.diagnostics import Diagnostic, DiagnosticCode
from contextc.errors import SourceValidationError
from contextc.ir.analysis import NodeAnalysis
from contextc.ir.compilation import SelectionResult
from contextc.ir.graph import ContextGraph
from contextc.schema import EXPLANATION_SCHEMA, SchemaVersion, require_schema_version


class NodeStatus(StrEnum):
    INCLUDED = "included"
    EXCLUDED = "excluded"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class NodeExplanation:
    node_id: str
    status: NodeStatus
    summary: str
    diagnostic_codes: tuple[DiagnosticCode, ...] = ()
    evidence: Mapping[str, object] = field(default_factory=dict)
    related_node_ids: tuple[str, ...] = ()
    target_token_count: int | None = None
    schema_version: SchemaVersion = EXPLANATION_SCHEMA

    def __post_init__(self) -> None:
        if not self.node_id or not self.summary:
            raise SourceValidationError("explanation node_id and summary must not be empty")
        object.__setattr__(self, "diagnostic_codes", tuple(self.diagnostic_codes))
        object.__setattr__(self, "related_node_ids", tuple(self.related_node_ids))
        if self.target_token_count is not None and self.target_token_count < 0:
            raise SourceValidationError("explanation target token count must not be negative")
        frozen = freeze_value(self.evidence)
        if not isinstance(frozen, Mapping):
            raise SourceValidationError("explanation evidence must be a mapping")
        object.__setattr__(self, "evidence", frozen)
        require_schema_version(
            self.schema_version,
            expected=EXPLANATION_SCHEMA,
            artifact="NodeExplanation",
        )

    def to_dict(self) -> dict[str, object]:
        primitive = to_canonical_primitive(self)
        if not isinstance(primitive, dict):
            raise AssertionError("node explanation did not canonicalize to an object")
        return primitive


def explain_node(
    *,
    node_id: str,
    graph: ContextGraph,
    analyses: Mapping[str, NodeAnalysis],
    selection: SelectionResult,
    diagnostics: tuple[Diagnostic, ...] = (),
    tokenizer_id: str | None = None,
) -> NodeExplanation:
    """Explain one node exclusively from stored graph/analysis/selection evidence."""

    if node_id in selection.selected_node_ids:
        status = NodeStatus.INCLUDED
        summary = "Node was included by the stored selection result."
    elif node_id in selection.excluded_node_ids:
        status = NodeStatus.EXCLUDED
        summary = "Node was excluded by the stored selection result."
    else:
        status = NodeStatus.UNKNOWN
        summary = "Node has no stored selection outcome."
    analysis = analyses.get(node_id)
    exists = node_id in graph.node_ids
    incoming = graph.incoming_edges(node_id) if exists else ()
    outgoing = graph.outgoing_edges(node_id) if exists else ()
    related = tuple(
        sorted(
            {edge.source_node_id for edge in incoming if edge.source_node_id != node_id}
            | {edge.target_node_id for edge in outgoing if edge.target_node_id != node_id}
        )
    )
    all_diagnostics = selection.diagnostics + tuple(diagnostics)
    codes = tuple(
        sorted(
            {item.code for item in all_diagnostics if node_id in item.node_ids},
            key=lambda code: code.value,
        )
    )
    token_count = None
    if analysis is not None and tokenizer_id is not None:
        token_count = analysis.token_counts.get(tokenizer_id)
    evidence: dict[str, object] = {
        "analysis": None if analysis is None else analysis.to_dict(),
        "dependency_forced": node_id in selection.dependency_forced_node_ids,
        "excluded_reason": selection.excluded_reasons.get(node_id),
        "incoming_edge_ids": tuple(edge.edge_id for edge in incoming),
        "mandatory": node_id in selection.mandatory_node_ids,
        "outgoing_edge_ids": tuple(edge.edge_id for edge in outgoing),
        "selection_strategy_id": selection.strategy_id,
        "selection_strategy_version": selection.strategy_version,
        "optimizer_requested": selection.requested_strategy_id,
        "optimizer_status": selection.optimizer_status.value,
        "objective_value": selection.objective_value,
        "optimality_proven": selection.optimizer_status.value == "optimal",
        "heuristic": selection.optimizer_status.value == "heuristic",
        "timed_out": selection.optimizer_status.value == "feasible_timeout",
        "fallback_reason": selection.fallback_reason,
        "tie_break_trace": selection.tie_break_trace,
    }
    return NodeExplanation(
        node_id=node_id,
        status=status,
        summary=summary,
        diagnostic_codes=codes,
        evidence=evidence,
        related_node_ids=related,
        target_token_count=token_count,
    )


def format_node_explanation(explanation: NodeExplanation) -> str:
    """Format stored explanation evidence without changing or recomputing it."""

    codes = ", ".join(code.value for code in explanation.diagnostic_codes) or "none"
    related = ", ".join(explanation.related_node_ids) or "none"
    token_count = (
        "unknown" if explanation.target_token_count is None else str(explanation.target_token_count)
    )
    return (
        f"{explanation.node_id}: {explanation.status.value}\n"
        f"{explanation.summary}\n"
        f"diagnostics: {codes}\n"
        f"related: {related}\n"
        f"target tokens: {token_count}"
    )
