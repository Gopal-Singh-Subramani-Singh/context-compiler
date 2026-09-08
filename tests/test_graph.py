from collections.abc import Iterable

import pytest

from contextc.diagnostics import DiagnosticCode
from contextc.errors import DependencyCycleError, GraphInvariantError, SourceValidationError
from contextc.ir import ContextEdge, ContextGraph, ContextNode, EdgeType, NodeKind, SourceReference


def node(node_id: str, content: str | None = None) -> ContextNode:
    return ContextNode.create(
        node_id=node_id,
        kind=NodeKind.FILE,
        content=node_id if content is None else content,
        source=SourceReference(uri=f"repo:///{node_id}.txt"),
    )


def graph_with_order(
    node_order: Iterable[str], edge_order: Iterable[tuple[str, str, EdgeType]]
) -> ContextGraph:
    graph = ContextGraph()
    for node_id in node_order:
        graph.add_node(node(node_id))
    for source_id, target_id, kind in edge_order:
        graph.add_edge(ContextEdge(source_id, target_id, kind, evidence={"fact": kind.value}))
    return graph


def test_graph_serialization_and_identity_ignore_insertion_order() -> None:
    edge_order = [
        ("a", "b", EdgeType.REQUIRES),
        ("b", "c", EdgeType.CALLS),
        ("a", "c", EdgeType.SUPPORTS),
    ]
    left = graph_with_order(["c", "a", "b"], edge_order)
    right = graph_with_order(["a", "b", "c"], reversed(edge_order))
    assert left.node_ids == ("a", "b", "c")
    assert left.to_dict() == right.to_dict()
    assert left.semantic_identity == right.semantic_identity
    assert ContextGraph.from_dict(left.to_dict()).to_dict() == left.to_dict()


def test_one_semantic_graph_mutation_changes_identity() -> None:
    graph = graph_with_order(["a", "b"], [("a", "b", EdgeType.REQUIRES)])
    before = graph.semantic_identity
    graph.add_edge(ContextEdge("a", "b", EdgeType.SUPPORTS))
    assert graph.semantic_identity != before


def test_edge_validation_duplicate_and_parallel_edge_policy() -> None:
    graph = graph_with_order(["a", "b"], [])
    first = ContextEdge("a", "b", EdgeType.SUPPORTS, evidence={"source": "one"})
    second = ContextEdge("a", "b", EdgeType.SUPPORTS, evidence={"source": "two"})
    graph.add_edge(first)
    graph.add_edge(first)
    graph.add_edge(second)
    assert len(graph.edges) == 2
    assert graph.get_edge(first.edge_id) == first
    assert graph.remove_edge(second.edge_id) == second
    with pytest.raises(SourceValidationError):
        ContextEdge("a", "a", EdgeType.REQUIRES)
    with pytest.raises(SourceValidationError):
        ContextEdge("a", "b", EdgeType.CALLS, confidence=1.1)
    with pytest.raises(SourceValidationError):
        ContextEdge("a", "b", EdgeType.CALLS, edge_id="edge-false")
    with pytest.raises(GraphInvariantError):
        graph.add_edge(ContextEdge("a", "missing", EdgeType.CALLS))


def test_unknown_edge_kind_and_missing_graph_endpoints_are_rejected() -> None:
    edge = ContextEdge("a", "b", EdgeType.IMPORTS)
    value = edge.to_dict()
    value["edge_type"] = "future_unknown_edge"
    with pytest.raises(SourceValidationError):
        ContextEdge.from_dict(value)
    graph_value = graph_with_order(["a", "b"], [("a", "b", EdgeType.IMPORTS)]).to_dict()
    nodes = graph_value["nodes"]
    assert isinstance(nodes, list)
    graph_value["nodes"] = nodes[:1]
    with pytest.raises(GraphInvariantError):
        ContextGraph.from_dict(graph_value)


def test_dependency_closure_uses_only_configured_relationships() -> None:
    graph = graph_with_order(
        ["a", "b", "c", "d"],
        [
            ("a", "b", EdgeType.REQUIRES),
            ("b", "c", EdgeType.IMPORTS),
            ("a", "d", EdgeType.CONFLICTS),
        ],
    )
    closure = graph.dependency_closure(["a", "missing"])
    assert closure.node_ids == ("a", "b", "c")
    assert closure.dependency_forced_node_ids == ("b", "c")
    assert closure.missing_node_ids == ("missing",)
    assert {item.code for item in closure.diagnostics} == {
        DiagnosticCode.MISSING_DEPENDENCY,
        DiagnosticCode.DEPENDENCY_FORCED_INCLUSION,
    }
    assert "d" not in closure.node_ids


def test_cycles_are_deterministic_and_block_only_acyclic_api() -> None:
    edges = [
        ("a", "b", EdgeType.REQUIRES),
        ("b", "a", EdgeType.IMPORTS),
        ("c", "d", EdgeType.CALLS),
        ("d", "c", EdgeType.REQUIRES),
    ]
    left = graph_with_order(["d", "c", "b", "a"], edges)
    right = graph_with_order(["a", "b", "c", "d"], reversed(edges))
    expected = (("a", "b"), ("c", "d"))
    assert left.dependency_cycles() == expected
    assert right.dependency_cycles() == expected
    closure = left.dependency_closure(["a"])
    assert closure.node_ids == ("a", "b")
    assert DiagnosticCode.DEPENDENCY_CYCLE in {item.code for item in closure.diagnostics}
    with pytest.raises(DependencyCycleError) as captured:
        left.topological_dependency_order()
    assert captured.value.diagnostic_code == "CTX320"
    assert captured.value.cycles == expected
    assert left.outgoing_edges("a", kinds=[EdgeType.REQUIRES])


def test_topological_order_subgraph_filters_and_cascading_node_removal() -> None:
    graph = graph_with_order(
        ["a", "b", "c"],
        [
            ("a", "b", EdgeType.REQUIRES),
            ("b", "c", EdgeType.CALLS),
            ("c", "a", EdgeType.CONFLICTS),
        ],
    )
    assert graph.topological_dependency_order() == ("c", "b", "a")
    assert len(graph.incoming_edges("b", kinds=[EdgeType.REQUIRES])) == 1
    assert len(graph.outgoing_edges("c", kinds=[EdgeType.CONFLICTS])) == 1
    subset = graph.subgraph(["a", "b"])
    assert subset.node_ids == ("a", "b")
    assert len(subset.edges) == 1
    assert graph.remove_node("b").node_id == "b"
    assert graph.node_ids == ("a", "c")
    assert all("b" not in {edge.source_node_id, edge.target_node_id} for edge in graph.edges)
    with pytest.raises(GraphInvariantError):
        graph.get_node("b")
    with pytest.raises(GraphInvariantError):
        graph.subgraph(["missing"])
