"""Source-neutral explicit conflict/contradiction evidence analysis for M15."""

from __future__ import annotations

from dataclasses import dataclass

from contextc.diagnostics import Diagnostic, DiagnosticCode, Severity
from contextc.ir import ContextGraph, EdgeType


@dataclass(frozen=True, slots=True)
class ConflictResult:
    diagnostics: tuple[Diagnostic, ...]
    relationship_edge_ids: tuple[str, ...]


def analyze_conflicts(graph: ContextGraph) -> ConflictResult:
    """Report explicit CONTRADICTS/CONFLICTS evidence without blocking selection."""

    diagnostics: list[Diagnostic] = []
    edge_ids: list[str] = []
    for edge in graph.edges:
        if edge.edge_type not in {EdgeType.CONTRADICTS, EdgeType.CONFLICTS}:
            continue
        edge_ids.append(edge.edge_id)
        diagnostics.append(
            Diagnostic(
                code=DiagnosticCode.INSTRUCTION_CONFLICT,
                severity=Severity.WARNING,
                message=(
                    "Explicit source relationship records conflicting or contradictory evidence."
                ),
                node_ids=(edge.source_node_id, edge.target_node_id),
                evidence={
                    "edge_id": edge.edge_id,
                    "relationship": edge.edge_type.value,
                    "relationship_evidence": edge.evidence,
                },
                owning_pass="conflict_analysis",
            )
        )
    return ConflictResult(
        diagnostics=tuple(diagnostics),
        relationship_edge_ids=tuple(edge_ids),
    )
