"""Deterministic M2 graph construction for statically indexed Python sources."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import PurePosixPath

from contextc.ir.edges import ContextEdge, EdgeType
from contextc.ir.graph import ContextGraph
from contextc.ir.nodes import ContextNode, NodeKind
from contextc.parsers.base import IndexResult


def _module_name(node: ContextNode) -> str:
    relative = node.source.uri.removeprefix("repo:///")
    path = PurePosixPath(relative)
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _add_edge(
    graph: ContextGraph,
    source_id: str,
    target_id: str,
    kind: EdgeType,
    evidence: dict[str, object],
) -> None:
    if source_id == target_id:
        return
    graph.add_edge(
        ContextEdge(
            source_node_id=source_id,
            target_node_id=target_id,
            edge_type=kind,
            evidence=evidence,
        )
    )


def graph_repository_index(index: IndexResult) -> ContextGraph:
    """Build stable local import/call/definition edges without executing code."""

    graph = ContextGraph()
    for node in index.nodes:
        graph.add_node(node)
    modules = {
        _module_name(node): node
        for node in index.nodes
        if node.kind is NodeKind.MODULE and node.metadata.get("parse_status") == "parsed"
    }
    symbols: dict[str, list[ContextNode]] = defaultdict(list)
    for node in index.nodes:
        symbol = node.metadata.get("symbol")
        if isinstance(symbol, str):
            symbols[symbol].append(node)
    for values in symbols.values():
        values.sort(key=lambda node: node.node_id)

    for module_name, module in sorted(modules.items()):
        try:
            tree = ast.parse(module.content, filename=module.source.uri)
        except SyntaxError:
            continue
        imported_names: set[str] = set()
        for statement in ast.walk(tree):
            if isinstance(statement, ast.Import):
                imported_names.update(alias.name for alias in statement.names)
            elif isinstance(statement, ast.ImportFrom) and statement.module:
                imported_names.add(statement.module)
        for imported_name in sorted(imported_names):
            target = modules.get(imported_name)
            if target is not None:
                _add_edge(
                    graph,
                    module.node_id,
                    target.node_id,
                    EdgeType.IMPORTS,
                    {"imported_module": imported_name, "source_module": module_name},
                )

    for node in index.nodes:
        if node.kind not in {NodeKind.FUNCTION, NodeKind.CLASS}:
            continue
        owner = next(
            (module for module in modules.values() if module.source.uri == node.source.uri),
            None,
        )
        if owner is not None:
            _add_edge(
                graph,
                owner.node_id,
                node.node_id,
                EdgeType.DEFINES,
                {"symbol": node.metadata.get("symbol", "")},
            )
        if node.kind is not NodeKind.FUNCTION:
            continue
        try:
            tree = ast.parse(node.content, filename=node.source.uri)
        except SyntaxError:
            continue
        called_names = sorted(
            {
                call.func.id
                for call in ast.walk(tree)
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            }
        )
        for called_name in called_names:
            for target in symbols.get(called_name, []):
                _add_edge(
                    graph,
                    node.node_id,
                    target.node_id,
                    EdgeType.CALLS,
                    {"called_symbol": called_name},
                )
    return graph
