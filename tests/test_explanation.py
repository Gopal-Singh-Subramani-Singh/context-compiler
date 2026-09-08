from collections.abc import Mapping

from contextc.diagnostics import DiagnosticCode
from contextc.explanation import NodeStatus, explain_node, format_node_explanation
from contextc.ir import (
    ContextEdge,
    ContextGraph,
    ContextNode,
    EdgeType,
    NodeAnalysis,
    NodeKind,
    SelectionResult,
    SourceReference,
)


def make_node(node_id: str) -> ContextNode:
    return ContextNode.create(
        node_id=node_id,
        kind=NodeKind.FILE,
        content=node_id,
        source=SourceReference(uri=f"repo:///{node_id}"),
    )


def test_explanation_consumes_stored_analysis_selection_graph_and_diagnostics() -> None:
    graph = ContextGraph()
    graph.add_node(make_node("app"))
    graph.add_node(make_node("dependency"))
    graph.add_edge(ContextEdge("app", "dependency", EdgeType.REQUIRES))
    closure = graph.dependency_closure(["app"])
    selection = SelectionResult(
        selected_node_ids=("dependency", "app"),
        dependency_forced_node_ids=("dependency",),
        mandatory_node_ids=("app",),
        diagnostics=closure.diagnostics,
    )
    stored = NodeAnalysis(
        node_id="dependency",
        relevance=0.25,
        token_counts={"generic:test": 9},
        metadata={"evidence": "stored-only"},
    )
    explanation = explain_node(
        node_id="dependency",
        graph=graph,
        analyses={"dependency": stored},
        selection=selection,
        tokenizer_id="generic:test",
    )
    assert explanation.status is NodeStatus.INCLUDED
    assert explanation.target_token_count == 9
    assert explanation.related_node_ids == ("app",)
    assert explanation.diagnostic_codes == (DiagnosticCode.DEPENDENCY_FORCED_INCLUSION,)
    assert explanation.evidence["dependency_forced"] is True
    analysis_evidence = explanation.evidence["analysis"]
    assert isinstance(analysis_evidence, Mapping)
    assert analysis_evidence["relevance"] == 0.25
    terminal = format_node_explanation(explanation)
    assert "CTX310" in terminal
    assert "target tokens: 9" in terminal


def test_explanation_reports_excluded_and_unknown_from_stored_outcome() -> None:
    graph = ContextGraph()
    graph.add_node(make_node("excluded"))
    selection = SelectionResult(
        selected_node_ids=(),
        excluded_node_ids=("excluded",),
        excluded_reasons={"excluded": "stored reason"},
    )
    excluded = explain_node(node_id="excluded", graph=graph, analyses={}, selection=selection)
    unknown = explain_node(node_id="not-present", graph=graph, analyses={}, selection=selection)
    assert excluded.status is NodeStatus.EXCLUDED
    assert excluded.evidence["excluded_reason"] == "stored reason"
    assert unknown.status is NodeStatus.UNKNOWN
    assert unknown.related_node_ids == ()
