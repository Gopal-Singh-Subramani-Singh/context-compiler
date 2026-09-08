"""Deterministic bounded TAINTS/ENABLES traversal."""

from __future__ import annotations

from collections import deque

from contextc.ir import ContextEdge, ContextGraph, EdgeType
from contextc.security.models import TaintLimits, TaintPath

_FLOW = frozenset({EdgeType.TAINTS, EdgeType.ENABLES})


def find_taint_paths(
    graph: ContextGraph,
    *,
    source_node_ids: tuple[str, ...],
    sink_node_ids: tuple[str, ...],
    rule_id: str,
    limits: TaintLimits | None = None,
) -> tuple[TaintPath, ...]:
    limits = TaintLimits() if limits is None else limits
    sinks = frozenset(sink_node_ids)
    outgoing: dict[str, list[ContextEdge]] = {}
    for edge in graph.edges:
        if edge.edge_type in _FLOW:
            outgoing.setdefault(edge.source_node_id, []).append(edge)
    for edges in outgoing.values():
        edges.sort(
            key=lambda edge: (
                edge.target_node_id,
                edge.edge_type.value,
                edge.edge_id,
            )
        )

    results: list[TaintPath] = []
    for source in sorted(source_node_ids):
        queue: deque[tuple[str, tuple[str, ...], tuple[str, ...]]] = deque(
            [(source, (source,), ())]
        )
        while queue and len(results) < limits.max_reported_paths:
            current, nodes, edge_ids = queue.popleft()
            if current in sinks and current != source:
                results.append(TaintPath(rule_id, nodes, edge_ids, source, current))
                continue
            if len(edge_ids) >= limits.max_path_length:
                continue
            for edge in outgoing.get(current, ()):
                if edge.target_node_id in nodes:
                    continue
                queue.append(
                    (
                        edge.target_node_id,
                        (*nodes, edge.target_node_id),
                        (*edge_ids, edge.edge_id),
                    )
                )
    return tuple(
        sorted(
            results,
            key=lambda path: (
                path.source_node_id,
                path.sink_node_id,
                path.node_ids,
                path.edge_ids,
            ),
        )
    )
