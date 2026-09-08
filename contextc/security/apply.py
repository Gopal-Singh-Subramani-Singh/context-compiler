"""Apply M9 security results to a graph before task analysis and selection."""

from __future__ import annotations

from contextc.ir import ContextGraph, ContextNode
from contextc.security.models import SecurityResult


def apply_security_result(graph: ContextGraph, result: SecurityResult) -> ContextGraph:
    """Return a graph with deterministic transforms while retaining excluded nodes.

    Excluded nodes remain structurally present so dependency closure can prove that a
    dependent selection would be invalid. Downstream optimizer policy marks those IDs
    ineligible, preventing silent reintroduction through dependency closure.
    """

    transformed = {node.node_id: node for node in result.nodes if isinstance(node, ContextNode)}
    secured = ContextGraph(
        dependency_edge_types=graph.dependency_edge_types,
        schema_version=graph.schema_version,
    )
    for node in graph.nodes:
        secured.add_node(transformed.get(node.node_id, node))
    for edge in graph.edges:
        secured.add_edge(edge)
    return secured


__all__ = ["apply_security_result"]
