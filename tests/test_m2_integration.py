from datetime import UTC, datetime
from pathlib import Path

from contextc.application import graph_repository_index
from contextc.diagnostics import DiagnosticCode
from contextc.explanation import NodeStatus, explain_node
from contextc.hashing import semantic_hash
from contextc.ir import (
    CompilationUnit,
    ContextEdge,
    DeterministicBaselineSelection,
    EdgeType,
    NodeAnalysis,
    NodeKind,
)
from contextc.parsers import RepositoryParser
from contextc.targets import render_generic


def test_repository_to_graph_selection_generic_and_explanation(tmp_path: Path) -> None:
    (tmp_path / "helper.py").write_text(
        "def helper_function(value: int) -> int:\n    return value + 1\n"
    )
    (tmp_path / "app.py").write_text(
        "import helper\n"
        "raise RuntimeError('must never execute')\n\n"
        "def run(value: int) -> int:\n"
        "    return helper_function(value)\n"
    )
    (tmp_path / "unrelated.txt").write_text("conflicting but unrelated context\n")

    index = RepositoryParser(revision="git:integration").parse(tmp_path)
    graph = graph_repository_index(index)
    nodes_by_symbol = {
        node.metadata["symbol"]: node
        for node in graph.nodes
        if isinstance(node.metadata.get("symbol"), str)
    }
    modules_by_uri = {node.source.uri: node for node in graph.nodes if node.kind is NodeKind.MODULE}
    unrelated = next(node for node in graph.nodes if node.kind is NodeKind.DOCUMENT)
    app_module = modules_by_uri["repo:///app.py"]
    helper_module = modules_by_uri["repo:///helper.py"]
    run_function = nodes_by_symbol["run"]
    helper_function = nodes_by_symbol["helper_function"]
    graph.add_edge(
        ContextEdge(
            app_module.node_id,
            unrelated.node_id,
            EdgeType.CONFLICTS,
            evidence={"fixture": "unrelated conflict"},
        )
    )

    assert all(node.source.revision == "git:integration" for node in graph.nodes)
    assert run_function.source.start_line == 4
    assert helper_function.source.start_line == 1
    assert any(
        edge.edge_type is EdgeType.IMPORTS
        and edge.source_node_id == app_module.node_id
        and edge.target_node_id == helper_module.node_id
        for edge in graph.edges
    )
    assert any(
        edge.edge_type is EdgeType.CALLS
        and edge.source_node_id == run_function.node_id
        and edge.target_node_id == helper_function.node_id
        for edge in graph.edges
    )

    seed_ids = {app_module.node_id, run_function.node_id}
    analyses = {
        node.node_id: NodeAnalysis(
            node_id=node.node_id,
            relevance=1.0 if node.node_id in seed_ids else 0.0,
            mandatory=node.node_id == app_module.node_id,
            token_counts={"generic:test": len(node.content)},
            metadata={"fixture": "stored analysis"},
        )
        for node in graph.nodes
    }
    compilation = CompilationUnit(
        task_id="integration",
        task_description="Explain the application and helper call",
        target_id="generic",
        tokenizer_id="generic:test",
        token_budget=10_000,
        policy_id="policy:test",
        source_revision="git:integration",
        time_anchor=datetime(2026, 8, 28, tzinfo=UTC),
        random_seed=0,
        compiler_version="0.2.0",
        pipeline_config_hash=semantic_hash({"fixture": "m2"}),
    )
    selection = DeterministicBaselineSelection().select(graph, analyses, compilation)
    selected_nodes = tuple(graph.get_node(node_id) for node_id in selection.selected_node_ids)
    rendered = render_generic(selected_nodes)

    assert helper_module.node_id in selection.dependency_forced_node_ids
    assert helper_function.node_id in selection.dependency_forced_node_ids
    assert unrelated.node_id in selection.excluded_node_ids
    assert unrelated.node_id not in selection.selected_node_ids
    assert "repo:///app.py" in rendered
    assert "repo:///helper.py" in rendered
    assert "unrelated context" not in rendered

    explanation = explain_node(
        node_id=helper_function.node_id,
        graph=graph,
        analyses=analyses,
        selection=selection,
        tokenizer_id="generic:test",
    )
    assert explanation.status is NodeStatus.INCLUDED
    assert DiagnosticCode.DEPENDENCY_FORCED_INCLUSION in explanation.diagnostic_codes
    assert run_function.node_id in explanation.related_node_ids
