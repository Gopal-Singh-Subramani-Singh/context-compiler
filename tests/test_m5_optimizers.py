from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from contextc.hashing import semantic_hash
from contextc.ir import (
    CompilationUnit,
    ContextEdge,
    ContextGraph,
    ContextNode,
    EdgeType,
    NodeAnalysis,
    NodeKind,
    SelectionStatus,
    SourceReference,
)
from contextc.optimization.cascade import DeterministicOptimizerCascade, choose_optimizer
from contextc.optimization.models import (
    OPTIMIZER_IDS,
    ObjectiveWeights,
    OptimizerConfiguration,
    OptimizerLimits,
)
from contextc.optimization.problem import SelectionProblem
from contextc.optimization.strategies import (
    BruteForceSelection,
    DensityGreedySelection,
    DynamicProgrammingSelection,
    GraphClosureGreedySelection,
    ILPSelection,
    NaiveSelection,
    RelevanceGreedySelection,
    TopKSelection,
    strategy_for,
)

TOKENIZER = "generic:m5-test"


def node(node_id: str, *, uri: str | None = None, line: int = 1) -> ContextNode:
    return ContextNode.create(
        node_id=node_id,
        kind=NodeKind.FILE,
        content=f"content {node_id}",
        source=SourceReference(
            uri=uri or f"repo:///{node_id}.py",
            start_line=line,
            end_line=line,
        ),
    )


def graph_for(
    node_ids: tuple[str, ...],
    dependencies: tuple[tuple[str, str], ...] = (),
    *,
    reverse: bool = False,
) -> ContextGraph:
    graph = ContextGraph()
    ordered = tuple(reversed(node_ids)) if reverse else node_ids
    for node_id in ordered:
        graph.add_node(node(node_id))
    edges = tuple(reversed(dependencies)) if reverse else dependencies
    for source, target in edges:
        graph.add_edge(ContextEdge(source, target, EdgeType.REQUIRES))
    return graph


def analyses_for(
    values: dict[str, tuple[float, int]],
    *,
    mandatory: tuple[str, ...] = (),
    semantic: bool = True,
) -> dict[str, NodeAnalysis]:
    return {
        node_id: NodeAnalysis(
            node_id=node_id,
            relevance=value,
            trust_score=value / 2,
            freshness=value / 3,
            redundancy_score=value / 10,
            security_risk=value / 20,
            token_counts={TOKENIZER: cost},
            mandatory=node_id in mandatory,
            metadata={"semantic_score": value} if semantic else {},
        )
        for node_id, (value, cost) in values.items()
    }


def compilation(
    *,
    strategy: str,
    allowance: int,
    mandatory: tuple[str, ...] = (),
    blocked: tuple[str, ...] = (),
    eligible: tuple[str, ...] | None = None,
    limits: OptimizerLimits | None = None,
    weights: ObjectiveWeights | None = None,
) -> CompilationUnit:
    optimizer = OptimizerConfiguration(
        requested_strategy=strategy,
        source_content_allowance=allowance,
        mandatory_node_ids=mandatory,
        blocked_node_ids=blocked,
        policy_eligible_node_ids=eligible,
        limits=limits or OptimizerLimits(),
        objective_weights=weights
        or ObjectiveWeights(
            relevance=1,
            trust=0,
            freshness=0,
            dependency_coverage=0,
            redundancy_penalty=0,
            security_risk_penalty=0,
        ),
    )
    return CompilationUnit(
        task_id="task-m5",
        task_description="optimizer correctness",
        target_id="generic",
        tokenizer_id=TOKENIZER,
        token_budget=max(1, allowance),
        policy_id="policy:m5",
        time_anchor=datetime(2026, 8, 31, tzinfo=UTC),
        random_seed=0,
        compiler_version="0.5.0",
        pipeline_config_hash=semantic_hash({"m": 5, "optimizer": optimizer}),
        optimizer=optimizer,
    )


@pytest.mark.parametrize(
    ("values", "allowance"),
    [
        ({"a": (0.9, 4), "b": (0.6, 3), "c": (0.4, 2)}, 5),
        ({"a": (0.7, 3), "b": (0.7, 3), "c": (0.2, 1), "d": (0.1, 1)}, 6),
        ({"a": (1.0, 5), "b": (0.8, 4), "c": (0.5, 3)}, 7),
        ({"a": (0.0, 1), "b": (0.5, 2), "c": (0.5, 2)}, 3),
    ],
)
def test_exact_strategies_agree_on_supported_dependency_free_fixtures(
    values: dict[str, tuple[float, int]], allowance: int
) -> None:
    graph = graph_for(tuple(values))
    analyses = analyses_for(values)
    results = [
        strategy.select(
            graph, analyses, compilation(strategy=strategy.strategy_id, allowance=allowance)
        )
        for strategy in (BruteForceSelection(), DynamicProgrammingSelection(), ILPSelection())
    ]
    assert {result.optimizer_status for result in results} == {SelectionStatus.OPTIMAL}
    assert len({result.objective_value for result in results}) == 1
    assert len({result.selected_node_ids for result in results}) == 1


@pytest.mark.parametrize(
    ("strategy", "values"),
    (
        (NaiveSelection(), {"a": (0.4, 10), "b": (0.6, 5), "c": (0.6, 5)}),
        (RelevanceGreedySelection(), {"a": (1.0, 10), "b": (0.6, 5), "c": (0.6, 5)}),
        (DensityGreedySelection(), {"a": (1.0, 6), "b": (0.75, 5), "c": (0.75, 5)}),
    ),
)
def test_three_greedy_counterexamples_are_strictly_suboptimal(
    strategy: object, values: dict[str, tuple[float, int]]
) -> None:
    graph = graph_for(tuple(values))
    analyses = analyses_for(values)
    heuristic = strategy.select(  # type: ignore[attr-defined]
        graph,
        analyses,
        compilation(strategy=strategy.strategy_id, allowance=10),  # type: ignore[attr-defined]
    )
    optimum = BruteForceSelection().select(
        graph, analyses, compilation(strategy="brute_force", allowance=10)
    )
    assert heuristic.optimizer_status is SelectionStatus.HEURISTIC
    assert heuristic.objective_value is not None
    assert optimum.objective_value is not None
    assert heuristic.objective_value < optimum.objective_value


@pytest.mark.parametrize(
    "dependencies",
    [
        (("a", "b"), ("b", "c")),
        (("a", "c"), ("c", "b")),
    ],
)
def test_dependency_chain_forcing_is_transitive_and_flat_selection_is_invalid(
    dependencies: tuple[tuple[str, str], ...],
) -> None:
    graph = graph_for(("a", "b", "c", "z"), dependencies)
    analyses = analyses_for({"a": (1.0, 2), "b": (0.0, 2), "c": (0.0, 2), "z": (0.2, 2)})
    problem = SelectionProblem(
        graph, analyses, compilation(strategy="graph_closure_greedy", allowance=6)
    )
    assert not problem.is_feasible(("a",))
    result = GraphClosureGreedySelection().select(
        graph, analyses, compilation(strategy="graph_closure_greedy", allowance=6)
    )
    assert set(result.selected_node_ids) == {"a", "b", "c"}
    assert result.dependency_forced_node_ids == ("b", "c")


def test_shared_dependency_is_not_double_charged() -> None:
    graph = graph_for(("a", "b", "shared"), (("a", "shared"), ("b", "shared")))
    analyses = analyses_for({"a": (1.0, 2), "b": (0.9, 2), "shared": (0.0, 3)})
    result = GraphClosureGreedySelection().select(
        graph,
        analyses,
        compilation(strategy="graph_closure_greedy", allowance=7),
    )
    assert set(result.selected_node_ids) == {"a", "b", "shared"}
    assert result.used_tokens == 7


def test_brute_force_and_ilp_agree_with_dependencies_and_coverage_reward() -> None:
    graph = graph_for(("a", "b", "c"), (("a", "c"), ("b", "c")))
    analyses = analyses_for({"a": (0.8, 2), "b": (0.7, 2), "c": (0.1, 2)})
    weights = ObjectiveWeights(
        relevance=1,
        trust=0,
        freshness=0,
        dependency_coverage=0.4,
        redundancy_penalty=0,
        security_risk_penalty=0,
    )
    brute = BruteForceSelection().select(
        graph,
        analyses,
        compilation(strategy="brute_force", allowance=4, weights=weights),
    )
    ilp = ILPSelection().select(
        graph,
        analyses,
        compilation(strategy="ilp", allowance=4, weights=weights),
    )
    assert brute.optimizer_status is ilp.optimizer_status is SelectionStatus.OPTIMAL
    assert brute.objective_value == ilp.objective_value
    assert brute.selected_node_ids == ilp.selected_node_ids
    assert brute.dependency_forced_node_ids == ilp.dependency_forced_node_ids == ("c",)


def test_mandatory_overflow_and_blocked_mandatory_are_infeasible() -> None:
    graph = graph_for(("a", "b"), (("a", "b"),))
    analyses = analyses_for({"a": (1.0, 4), "b": (0.0, 4)}, mandatory=("a",))
    overflow = BruteForceSelection().select(
        graph, analyses, compilation(strategy="brute_force", allowance=7)
    )
    blocked = DensityGreedySelection().select(
        graph,
        analyses,
        compilation(strategy="density_greedy", allowance=8, blocked=("b",)),
    )
    for result in (overflow, blocked):
        assert result.optimizer_status is SelectionStatus.INFEASIBLE
        assert result.diagnostics[0].code.value == "CTX530"
        assert result.mandatory_node_ids == ("a",)


def test_non_dependency_edges_do_not_force_selection() -> None:
    graph = graph_for(("a", "b"))
    graph.add_edge(ContextEdge("a", "b", EdgeType.SUPPORTS))
    analyses = analyses_for({"a": (1.0, 2), "b": (0.0, 10)})
    result = GraphClosureGreedySelection().select(
        graph, analyses, compilation(strategy="graph_closure_greedy", allowance=2)
    )
    assert result.selected_node_ids == ("a",)
    assert result.dependency_forced_node_ids == ()


def test_policy_eligibility_is_shared_and_benchmark_metadata_is_not_reward() -> None:
    graph = graph_for(("a", "b"))
    analyses = analyses_for({"a": (0.8, 2), "b": (0.9, 2)})
    analyses["a"] = replace(analyses["a"], metadata={"benchmark_ground_truth_reward": 999})
    result = BruteForceSelection().select(
        graph,
        analyses,
        compilation(strategy="brute_force", allowance=2, eligible=("a",)),
    )
    assert result.selected_node_ids == ("a",)
    assert result.objective_value == pytest.approx(0.8)


def test_top_k_never_relabels_lexical_relevance_as_semantic() -> None:
    graph = graph_for(("a", "b"))
    analyses = analyses_for({"a": (1.0, 2), "b": (0.5, 2)}, semantic=False)
    result = TopKSelection().select(graph, analyses, compilation(strategy="top_k", allowance=2))
    assert result.optimizer_status is SelectionStatus.FALLBACK
    assert result.requested_strategy_id == "top_k"
    assert result.strategy_id == "density_greedy"
    assert result.fallback_reason
    assert result.diagnostics[-1].code.value == "CTX520"


def test_dp_unsafe_bounds_fall_back_without_allocating() -> None:
    graph = graph_for(("a", "b"))
    analyses = analyses_for({"a": (1.0, 2), "b": (0.5, 2)})
    limits = replace(OptimizerLimits(), max_dp_states=2)
    result = DynamicProgrammingSelection().select(
        graph,
        analyses,
        compilation(strategy="dynamic_programming", allowance=4, limits=limits),
    )
    assert result.optimizer_status is SelectionStatus.FALLBACK
    assert "states=" in (result.fallback_reason or "")


def test_ilp_timeout_with_feasible_incumbent_is_never_optimal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pulp = pytest.importorskip("pulp")
    graph = graph_for(("a", "b"))
    analyses = analyses_for({"a": (1.0, 2), "b": (0.5, 2)})

    def timed_out(model: object, solver: object) -> int:
        del solver
        for variable in model.variables():  # type: ignore[attr-defined]
            variable.varValue = 0
        return pulp.LpStatusNotSolved

    monkeypatch.setattr(pulp.LpProblem, "solve", timed_out)
    result = ILPSelection().select(graph, analyses, compilation(strategy="ilp", allowance=4))
    assert result.optimizer_status is SelectionStatus.FEASIBLE_TIMEOUT
    assert result.optimizer_status is not SelectionStatus.OPTIMAL
    assert result.solver_timeout_ms == 2000
    assert result.fallback_reason


def test_ilp_without_incumbent_uses_explicit_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    pulp = pytest.importorskip("pulp")
    graph = graph_for(("a", "b"))
    analyses = analyses_for({"a": (1.0, 2), "b": (0.5, 2)})

    def no_incumbent(model: object, solver: object) -> int:
        del model, solver
        return pulp.LpStatusNotSolved

    monkeypatch.setattr(pulp.LpProblem, "solve", no_incumbent)
    result = ILPSelection().select(graph, analyses, compilation(strategy="ilp", allowance=4))
    assert result.optimizer_status is SelectionStatus.FALLBACK
    assert result.strategy_id == "density_greedy"
    assert "no feasible incumbent" in (result.fallback_reason or "")


@pytest.mark.parametrize(
    "strategy_id",
    (
        "naive",
        "recency",
        "top_k",
        "relevance_greedy",
        "density_greedy",
        "brute_force",
        "dynamic_programming",
        "ilp",
        "graph_closure_greedy",
    ),
)
def test_every_strategy_is_deterministic_under_reversed_insertion(strategy_id: str) -> None:
    values = {"a": (0.9, 3), "b": (0.8, 2), "c": (0.4, 2), "d": (0.2, 1)}
    analyses = analyses_for(values)
    config = compilation(strategy=strategy_id, allowance=5)
    first = strategy_for(strategy_id).select(graph_for(tuple(values)), analyses, config)  # type: ignore[attr-defined]
    repeated = strategy_for(strategy_id).select(graph_for(tuple(values)), analyses, config)  # type: ignore[attr-defined]
    reversed_result = strategy_for(strategy_id).select(  # type: ignore[attr-defined]
        graph_for(tuple(values), reverse=True), analyses, config
    )
    assert (
        first.selected_node_ids == repeated.selected_node_ids == reversed_result.selected_node_ids
    )
    assert first.objective_value == repeated.objective_value == reversed_result.objective_value


def test_cascade_decision_shape_is_centralized_and_deterministic() -> None:
    values = {"a": (1.0, 1), "b": (0.5, 1)}
    graph = graph_for(tuple(values))
    analyses = analyses_for(values)
    config = compilation(strategy="auto", allowance=2)
    problem = SelectionProblem(graph, analyses, config)
    decision = choose_optimizer(problem)
    assert decision.selected_strategy_id == "brute_force"
    result = DeterministicOptimizerCascade().select(graph, analyses, config)
    assert result.requested_strategy_id == "auto"
    assert result.strategy_id == "brute_force"
    assert result.optimizer_status is SelectionStatus.OPTIMAL


def test_cascade_exercises_dp_ilp_dependency_and_density_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {"a": (1.0, 1), "b": (0.5, 1), "c": (0.2, 1)}
    analyses = analyses_for(values)
    tight = OptimizerLimits(
        max_bruteforce_nodes=1,
        max_dp_nodes=3,
        max_dp_budget=10,
        max_dp_states=100,
        max_dp_memory_bytes=10_000,
        ilp_max_nodes=3,
    )
    dependency_free = SelectionProblem(
        graph_for(tuple(values)),
        analyses,
        compilation(strategy="auto", allowance=3, limits=tight),
    )
    assert choose_optimizer(dependency_free).selected_strategy_id == "dynamic_programming"

    no_dp = replace(tight, max_dp_nodes=1)
    monkeypatch.setattr(
        "contextc.optimization.cascade.importlib.util.find_spec", lambda _name: object()
    )
    ilp_problem = SelectionProblem(
        graph_for(tuple(values)),
        analyses,
        compilation(strategy="auto", allowance=3, limits=no_dp),
    )
    assert choose_optimizer(ilp_problem).selected_strategy_id == "ilp"

    monkeypatch.setattr("contextc.optimization.cascade.importlib.util.find_spec", lambda name: None)
    dependency_problem = SelectionProblem(
        graph_for(tuple(values), (("a", "b"),)),
        analyses,
        compilation(strategy="auto", allowance=3, limits=no_dp),
    )
    assert choose_optimizer(dependency_problem).selected_strategy_id == "graph_closure_greedy"
    assert choose_optimizer(ilp_problem).selected_strategy_id == "density_greedy"


def test_public_optimizer_api_lazily_exports_every_strategy() -> None:
    import contextc.optimization as optimization

    for strategy_id in OPTIMIZER_IDS:
        strategy = optimization.strategy_for(strategy_id)
        assert strategy.strategy_id == strategy_id
    assert optimization.SelectionProblem is SelectionProblem
    assert optimization.choose_optimizer is choose_optimizer
    with pytest.raises(AttributeError):
        _missing = optimization.not_an_optimizer_export  # type: ignore[attr-defined]


def test_objective_configuration_is_versioned_canonical_and_rejects_nonfinite() -> None:
    weights = ObjectiveWeights(relevance=2.0, trust=0.5)
    assert ObjectiveWeights.from_dict(weights.to_dict()) == weights
    assert (
        compilation(strategy="brute_force", allowance=4, weights=weights).to_dict()["optimizer"][
            "objective_weights"
        ]
        == weights.to_dict()
    )  # type: ignore[index]
    with pytest.raises(Exception, match="finite"):
        ObjectiveWeights(relevance=float("nan"))
    with pytest.raises(Exception, match="finite"):
        ObjectiveWeights(security_risk_penalty=float("inf"))


def test_equal_utility_records_source_aware_tie_resolution() -> None:
    graph = graph_for(("a", "b"))
    analyses = analyses_for({"a": (0.5, 2), "b": (0.5, 2)})
    result = BruteForceSelection().select(
        graph, analyses, compilation(strategy="brute_force", allowance=2)
    )
    assert result.selected_node_ids == ("a",)
    assert any(
        "tie:utility=" in item and "stable_order=a,b" in item for item in result.tie_break_trace
    )
    assert len(result.tie_break_trace) <= 64
