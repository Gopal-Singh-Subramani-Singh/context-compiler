"""One deterministic optimizer decision cascade; CLI code never chooses algorithms."""

from __future__ import annotations

import importlib.util
from collections.abc import Mapping
from dataclasses import dataclass, replace

from contextc.ir.analysis import NodeAnalysis
from contextc.ir.compilation import CompilationUnit, SelectionResult
from contextc.ir.graph import ContextGraph
from contextc.optimization.problem import SelectionProblem
from contextc.optimization.strategies import strategy_for


@dataclass(frozen=True, slots=True)
class OptimizerDecision:
    requested_strategy_id: str
    selected_strategy_id: str
    reason: str


def choose_optimizer(problem: SelectionProblem) -> OptimizerDecision:
    """Choose one strategy from explicit limits and the common problem shape."""

    requested = problem.compilation.optimizer.requested_strategy
    if requested != "auto":
        return OptimizerDecision(requested, requested, "explicitly requested")
    limits = problem.compilation.optimizer.limits
    if problem.mandatory_infeasible_reason:
        return OptimizerDecision("auto", "brute_force", "mandatory closure is infeasible")
    optional_count = len(problem.optional_node_ids)
    if optional_count <= limits.max_bruteforce_nodes:
        return OptimizerDecision("auto", "brute_force", "small optional problem")
    estimated_states = (optional_count + 1) * (problem.available_tokens + 1)
    if (
        problem.dependency_free
        and optional_count <= limits.max_dp_nodes
        and problem.available_tokens <= limits.max_dp_budget
        and estimated_states <= limits.max_dp_states
        and estimated_states * 64 <= limits.max_dp_memory_bytes
    ):
        return OptimizerDecision("auto", "dynamic_programming", "safe dependency-free DP")
    if (
        importlib.util.find_spec("pulp") is not None
        and len(problem.graph.node_ids) <= limits.ilp_max_nodes
        and len(problem.dependency_pairs) <= limits.ilp_max_dependency_edges
    ):
        return OptimizerDecision("auto", "ilp", "ILP available within configured limits")
    if problem.dependency_pairs:
        return OptimizerDecision("auto", "graph_closure_greedy", "dependency graph heuristic")
    return OptimizerDecision("auto", "density_greedy", "bounded density heuristic")


class DeterministicOptimizerCascade:
    strategy_id = "auto"
    strategy_version = "1.0.0"

    def select(
        self,
        graph: ContextGraph,
        analyses: Mapping[str, NodeAnalysis],
        compilation: CompilationUnit,
    ) -> SelectionResult:
        problem = SelectionProblem(graph, analyses, compilation)
        decision = choose_optimizer(problem)
        strategy = strategy_for(decision.selected_strategy_id)
        result = strategy.select(graph, analyses, compilation)
        if decision.requested_strategy_id == "auto":
            return replace(result, requested_strategy_id="auto")
        return result
