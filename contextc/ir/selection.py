"""Typed selection protocol and the retained M2 compatibility baseline."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from contextc.errors import DependencyCycleError, GraphInvariantError
from contextc.ir.analysis import NodeAnalysis
from contextc.ir.compilation import CompilationUnit, SelectionResult, SelectionStatus
from contextc.ir.graph import ContextGraph


class SelectionStrategy(Protocol):
    """Stable strategy boundary implemented fully by later optimizer milestones."""

    def select(
        self,
        graph: ContextGraph,
        analyses: Mapping[str, NodeAnalysis],
        compilation: CompilationUnit,
    ) -> SelectionResult:
        """Select an ordered, dependency-complete set with stored evidence."""


class DeterministicBaselineSelection:
    """Select positive-relevance/mandatory seeds plus configured dependencies.

    This baseline does not claim budget optimization. If no analysis supplies a
    seed, it deterministically retains all nodes to avoid an implicit empty build.
    """

    strategy_id = "m2_deterministic_baseline"
    strategy_version = "1.0.0"

    def select(
        self,
        graph: ContextGraph,
        analyses: Mapping[str, NodeAnalysis],
        compilation: CompilationUnit,
    ) -> SelectionResult:
        unknown = sorted(set(analyses) - set(graph.node_ids))
        if unknown:
            raise GraphInvariantError(f"analyses reference unknown graph nodes: {unknown}")
        mandatory = tuple(
            sorted(node_id for node_id, analysis in analyses.items() if analysis.mandatory)
        )
        relevant = tuple(
            sorted(node_id for node_id, analysis in analyses.items() if analysis.relevance > 0.0)
        )
        seeds = tuple(sorted(set(mandatory) | set(relevant)))
        if not seeds:
            seeds = graph.node_ids
        closure = graph.dependency_closure(seeds)
        selected_set = set(closure.node_ids)
        try:
            ordered_selected = graph.topological_dependency_order(selected_set)
        except DependencyCycleError:
            ordered_selected = tuple(sorted(selected_set))
        excluded = tuple(sorted(set(graph.node_ids) - selected_set))
        reasons = {node_id: "no_positive_relevance_or_requirement" for node_id in excluded}
        objective = sum(
            analyses[node_id].relevance for node_id in ordered_selected if node_id in analyses
        )
        used_tokens = sum(
            analyses[node_id].token_counts.get(compilation.tokenizer_id, 0)
            for node_id in ordered_selected
            if node_id in analyses
        )
        trace = tuple(
            [
                *(f"seed:{node_id}" for node_id in seeds),
                *(f"dependency:{node_id}" for node_id in closure.dependency_forced_node_ids),
            ]
        )
        return SelectionResult(
            selected_node_ids=ordered_selected,
            excluded_node_ids=excluded,
            dependency_forced_node_ids=closure.dependency_forced_node_ids,
            mandatory_node_ids=mandatory,
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            requested_strategy_id=self.strategy_id,
            optimizer_status=SelectionStatus.HEURISTIC,
            objective_value=objective,
            used_tokens=used_tokens,
            available_tokens=compilation.token_budget,
            solver_runtime_ms=0,
            tie_break_trace=trace,
            diagnostics=closure.diagnostics,
            excluded_reasons=reasons,
        )
