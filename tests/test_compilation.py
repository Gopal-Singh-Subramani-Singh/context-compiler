from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from contextc.errors import SourceValidationError
from contextc.hashing import semantic_hash
from contextc.ir import (
    CompilationUnit,
    CompiledContext,
    ContextEdge,
    ContextGraph,
    ContextNode,
    DeterministicBaselineSelection,
    EdgeType,
    NodeAnalysis,
    NodeKind,
    SelectionResult,
    SelectionStatus,
    SelectionStrategy,
    SourceReference,
)


def compilation(**overrides: object) -> CompilationUnit:
    values: dict[str, object] = {
        "task_id": "task-1",
        "task_description": "Explain the application",
        "target_id": "generic",
        "tokenizer_id": "generic:test",
        "token_budget": 100,
        "policy_id": "policy:default",
        "time_anchor": datetime(2026, 8, 28, 12, tzinfo=UTC),
        "random_seed": 7,
        "compiler_version": "0.2.0",
        "pipeline_config_hash": semantic_hash({"pipeline": "m2"}),
        "source_revision": "git:abc",
    }
    values.update(overrides)
    return CompilationUnit(**values)  # type: ignore[arg-type]


def make_node(node_id: str) -> ContextNode:
    return ContextNode.create(
        node_id=node_id,
        kind=NodeKind.FILE,
        content=node_id,
        source=SourceReference(uri=f"repo:///{node_id}"),
    )


def test_compilation_unit_is_deterministic_timezone_aware_and_round_trips() -> None:
    offset = timezone(timedelta(hours=5, minutes=30))
    left = compilation(time_anchor=datetime(2026, 8, 28, 17, 30, tzinfo=offset))
    right = compilation(time_anchor=datetime(2026, 8, 28, 12, tzinfo=UTC))
    assert left == right
    assert left.time_anchor.tzinfo is UTC
    assert left.to_dict() == right.to_dict()
    assert CompilationUnit.from_dict(left.to_dict()) == left


@pytest.mark.parametrize(
    "overrides",
    [
        {"task_id": ""},
        {"token_budget": 0},
        {"time_anchor": datetime(2026, 1, 1)},
        {"compiler_version": "v2"},
        {"pipeline_config_hash": "not-a-hash"},
    ],
)
def test_compilation_unit_validation(overrides: dict[str, object]) -> None:
    with pytest.raises(SourceValidationError):
        compilation(**overrides)


def test_selection_result_stores_complete_immutable_evidence_and_round_trips() -> None:
    selection = SelectionResult(
        selected_node_ids=("a", "b"),
        excluded_node_ids=("c",),
        dependency_forced_node_ids=("b",),
        mandatory_node_ids=("a",),
        objective_value=1.5,
        used_tokens=8,
        available_tokens=100,
        solver_runtime_ms=0,
        solver_timeout_ms=100,
        tie_break_trace=("seed:a", "dependency:b"),
        excluded_reasons={"c": "unrelated"},
    )
    assert SelectionResult.from_dict(selection.to_dict()) == selection
    with pytest.raises(TypeError):
        selection.runtime_evidence["changed"] = True  # type: ignore[index]
    with pytest.raises(SourceValidationError):
        replace(selection, excluded_node_ids=("a",))
    with pytest.raises(SourceValidationError):
        replace(selection, dependency_forced_node_ids=("missing",))
    with pytest.raises(SourceValidationError):
        replace(selection, strategy_version="one")


def test_baseline_selection_is_dependency_complete_and_does_not_follow_conflicts() -> None:
    graph = ContextGraph()
    for node_id in ("app", "dependency", "conflict", "unrelated"):
        graph.add_node(make_node(node_id))
    graph.add_edge(ContextEdge("app", "dependency", EdgeType.REQUIRES))
    graph.add_edge(ContextEdge("app", "conflict", EdgeType.CONFLICTS))
    analyses = {
        "app": NodeAnalysis(
            node_id="app",
            relevance=1.0,
            mandatory=True,
            token_counts={"generic:test": 5},
        ),
        "dependency": NodeAnalysis(node_id="dependency", token_counts={"generic:test": 3}),
        "conflict": NodeAnalysis(node_id="conflict"),
        "unrelated": NodeAnalysis(node_id="unrelated"),
    }
    strategy: SelectionStrategy = DeterministicBaselineSelection()
    first = strategy.select(graph, analyses, compilation())
    second = strategy.select(graph, analyses, compilation())
    assert first == second
    assert first.selected_node_ids == ("dependency", "app")
    assert first.dependency_forced_node_ids == ("dependency",)
    assert first.excluded_node_ids == ("conflict", "unrelated")
    assert first.mandatory_node_ids == ("app",)
    assert first.optimizer_status is SelectionStatus.HEURISTIC
    assert first.objective_value == 1.0
    assert first.used_tokens == 8
    assert first.available_tokens == 100


def test_baseline_without_seed_retains_all_nodes_and_rejects_unknown_analysis() -> None:
    graph = ContextGraph()
    graph.add_node(make_node("a"))
    graph.add_node(make_node("b"))
    strategy = DeterministicBaselineSelection()
    result = strategy.select(
        graph,
        {"a": NodeAnalysis(node_id="a"), "b": NodeAnalysis(node_id="b")},
        compilation(),
    )
    assert result.selected_node_ids == ("a", "b")
    with pytest.raises(Exception, match="unknown graph nodes"):
        strategy.select(
            graph,
            {"missing": NodeAnalysis(node_id="missing")},
            compilation(),
        )


def test_compiled_context_is_versioned_and_round_trips() -> None:
    selection = SelectionResult(("a",))
    rendered = "<<<CONTEXT>>>\na\n<<<END_CONTEXT>>>\n"
    compiled = CompiledContext(
        rendered_text=rendered,
        selection=selection,
        semantic_hash=semantic_hash({"rendered_text": rendered, "selection": selection.to_dict()}),
    )
    assert CompiledContext.from_dict(compiled.to_dict()) == compiled
    with pytest.raises(SourceValidationError):
        replace(compiled, semantic_hash="invalid")
