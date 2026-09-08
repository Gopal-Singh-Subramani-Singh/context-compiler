"""Nine deterministic M5 selection strategies over the shared problem model."""

from __future__ import annotations

import importlib.util
import itertools
import time
from collections.abc import Callable, Mapping

from contextc.diagnostics import Diagnostic, DiagnosticCode, get_definition
from contextc.ir.analysis import NodeAnalysis
from contextc.ir.compilation import CompilationUnit, SelectionResult, SelectionStatus
from contextc.ir.graph import ContextGraph
from contextc.ir.selection import SelectionStrategy
from contextc.optimization.problem import SelectionProblem


def _requested(problem: SelectionProblem, strategy_id: str) -> str:
    requested = problem.compilation.optimizer.requested_strategy
    return strategy_id if requested == "auto" else requested


def _fallback_diagnostic(reason: str, requested: str, used: str) -> Diagnostic:
    definition = get_definition(DiagnosticCode.OPTIMIZER_FALLBACK)
    return Diagnostic(
        code=definition.code,
        severity=definition.default_severity,
        message=definition.title,
        evidence={"reason": reason, "requested": requested, "used": used},
        owning_pass="optimizer",
    )


def _greedy_by_order(
    problem: SelectionProblem,
    candidates: tuple[str, ...],
    *,
    strategy_id: str,
    requested: str,
    status: SelectionStatus = SelectionStatus.HEURISTIC,
    fallback_reason: str | None = None,
    diagnostics: tuple[Diagnostic, ...] = (),
) -> SelectionResult:
    if problem.mandatory_infeasible_reason:
        return problem.infeasible_result(requested=requested, strategy_id=strategy_id)
    selected = set(problem.mandatory_closure)
    seeds = set(problem.mandatory)
    trace: list[str] = []
    for candidate in candidates:
        if candidate in selected or candidate not in problem.allowed:
            continue
        cluster = problem.closure((candidate,)) - selected
        proposed = selected | cluster
        if problem.cost(proposed) <= problem.available_tokens and proposed <= problem.allowed:
            selected = proposed
            seeds.add(candidate)
            trace.append(f"accept:{candidate}:cost={problem.cost(cluster)}")
        else:
            trace.append(f"reject:{candidate}:closure_or_allowance")
    return problem.result(
        selected=selected,
        selected_seeds=seeds,
        requested=requested,
        strategy_id=strategy_id,
        status=status,
        fallback_reason=fallback_reason,
        diagnostics=diagnostics,
        trace=trace,
    )


def _density_result(
    problem: SelectionProblem,
    *,
    requested: str,
    strategy_id: str = "density_greedy",
    status: SelectionStatus = SelectionStatus.HEURISTIC,
    fallback_reason: str | None = None,
    diagnostics: tuple[Diagnostic, ...] = (),
) -> SelectionResult:
    if problem.mandatory_infeasible_reason:
        return problem.infeasible_result(requested=requested, strategy_id=strategy_id)
    selected = set(problem.mandatory_closure)
    seeds = set(problem.mandatory)
    remaining = set(problem.optional_node_ids)
    trace: list[str] = []
    while remaining:
        ranked: list[tuple[tuple[object, ...], str, frozenset[str], float, int]] = []
        for candidate in sorted(remaining):
            cluster = problem.closure((candidate,)) - selected
            proposed = selected | cluster
            if not cluster or not proposed <= problem.allowed:
                continue
            marginal_cost = problem.cost(cluster)
            marginal_value = problem.objective(proposed) - problem.objective(selected)
            density = marginal_value / max(1, marginal_cost)
            key = (-density, *problem.stable_key(candidate, marginal_value))
            ranked.append((key, candidate, cluster, marginal_value, marginal_cost))
        if not ranked:
            break
        _key, candidate, cluster, marginal_value, marginal_cost = min(ranked)
        remaining.remove(candidate)
        if marginal_value <= 0:
            trace.append(f"reject:{candidate}:non_positive_marginal")
            continue
        proposed = selected | cluster
        if problem.cost(proposed) <= problem.available_tokens:
            selected = proposed
            seeds.add(candidate)
            remaining.difference_update(cluster)
            trace.append(f"accept:{candidate}:marginal={marginal_value:.12g}:cost={marginal_cost}")
        else:
            trace.append(f"reject:{candidate}:allowance")
    return problem.result(
        selected=selected,
        selected_seeds=seeds,
        requested=requested,
        strategy_id=strategy_id,
        status=status,
        fallback_reason=fallback_reason,
        diagnostics=diagnostics,
        trace=trace,
    )


def _fallback(problem: SelectionProblem, requested: str, reason: str) -> SelectionResult:
    diagnostic = _fallback_diagnostic(reason, requested, "density_greedy")
    return _density_result(
        problem,
        requested=requested,
        status=SelectionStatus.FALLBACK,
        fallback_reason=reason,
        diagnostics=(diagnostic,),
    )


class NaiveSelection:
    strategy_id = "naive"
    strategy_version = "1.0.0"

    def select(
        self,
        graph: ContextGraph,
        analyses: Mapping[str, NodeAnalysis],
        compilation: CompilationUnit,
    ) -> SelectionResult:
        problem = SelectionProblem(graph, analyses, compilation)
        candidates = tuple(
            sorted(
                problem.optional_node_ids,
                key=lambda item: (
                    graph.get_node(item).source.uri,
                    graph.get_node(item).source.start_line or 0,
                    graph.get_node(item).source.end_line or 0,
                    item,
                ),
            )
        )
        return _greedy_by_order(
            problem,
            candidates,
            strategy_id=self.strategy_id,
            requested=_requested(problem, self.strategy_id),
        )


class RecencySelection:
    strategy_id = "recency"
    strategy_version = "1.0.0"

    def select(
        self,
        graph: ContextGraph,
        analyses: Mapping[str, NodeAnalysis],
        compilation: CompilationUnit,
    ) -> SelectionResult:
        problem = SelectionProblem(graph, analyses, compilation)
        candidates = tuple(
            sorted(
                problem.optional_node_ids,
                key=lambda item: problem.stable_key(item, analyses[item].freshness),
            )
        )
        return _greedy_by_order(
            problem,
            candidates,
            strategy_id=self.strategy_id,
            requested=_requested(problem, self.strategy_id),
        )


class TopKSelection:
    strategy_id = "top_k"
    strategy_version = "1.0.0"

    def select(
        self,
        graph: ContextGraph,
        analyses: Mapping[str, NodeAnalysis],
        compilation: CompilationUnit,
    ) -> SelectionResult:
        problem = SelectionProblem(graph, analyses, compilation)
        semantic: dict[str, float] = {}
        for node_id in problem.optional_node_ids:
            value = analyses[node_id].metadata.get("semantic_score")
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return _fallback(
                    problem,
                    _requested(problem, self.strategy_id),
                    "semantic embeddings/scores are unavailable; no lexical score was "
                    "relabeled semantic",
                )
            semantic[node_id] = float(value)
        candidates = tuple(
            sorted(
                problem.optional_node_ids,
                key=lambda item: problem.stable_key(item, semantic[item]),
            )
        )
        return _greedy_by_order(
            problem,
            candidates,
            strategy_id=self.strategy_id,
            requested=_requested(problem, self.strategy_id),
        )


class RelevanceGreedySelection:
    strategy_id = "relevance_greedy"
    strategy_version = "1.0.0"

    def select(
        self,
        graph: ContextGraph,
        analyses: Mapping[str, NodeAnalysis],
        compilation: CompilationUnit,
    ) -> SelectionResult:
        problem = SelectionProblem(graph, analyses, compilation)
        candidates = tuple(
            sorted(
                problem.optional_node_ids,
                key=lambda item: problem.stable_key(item, analyses[item].relevance),
            )
        )
        return _greedy_by_order(
            problem,
            candidates,
            strategy_id=self.strategy_id,
            requested=_requested(problem, self.strategy_id),
        )


class DensityGreedySelection:
    strategy_id = "density_greedy"
    strategy_version = "1.0.0"

    def select(
        self,
        graph: ContextGraph,
        analyses: Mapping[str, NodeAnalysis],
        compilation: CompilationUnit,
    ) -> SelectionResult:
        problem = SelectionProblem(graph, analyses, compilation)
        return _density_result(
            problem,
            requested=_requested(problem, self.strategy_id),
            strategy_id=self.strategy_id,
        )


class GraphClosureGreedySelection:
    strategy_id = "graph_closure_greedy"
    strategy_version = "1.0.0"

    def select(
        self,
        graph: ContextGraph,
        analyses: Mapping[str, NodeAnalysis],
        compilation: CompilationUnit,
    ) -> SelectionResult:
        problem = SelectionProblem(graph, analyses, compilation)
        return _density_result(
            problem,
            requested=_requested(problem, self.strategy_id),
            strategy_id=self.strategy_id,
        )


class BruteForceSelection:
    strategy_id = "brute_force"
    strategy_version = "1.0.0"

    def select(
        self,
        graph: ContextGraph,
        analyses: Mapping[str, NodeAnalysis],
        compilation: CompilationUnit,
    ) -> SelectionResult:
        started = time.perf_counter()
        problem = SelectionProblem(graph, analyses, compilation)
        requested = _requested(problem, self.strategy_id)
        if problem.mandatory_infeasible_reason:
            return problem.infeasible_result(requested=requested, strategy_id=self.strategy_id)
        optional = problem.optional_node_ids
        if len(optional) > compilation.optimizer.limits.max_bruteforce_nodes:
            return _fallback(
                problem,
                requested,
                f"brute-force optional node limit exceeded: {len(optional)} > "
                f"{compilation.optimizer.limits.max_bruteforce_nodes}",
            )
        best: frozenset[str] | None = None
        best_seeds: frozenset[str] = frozenset()
        examined = 0
        for size in range(len(optional) + 1):
            for combination in itertools.combinations(optional, size):
                examined += 1
                seeds = frozenset(problem.mandatory | frozenset(combination))
                selected = problem.closure(seeds)
                if problem.is_feasible(selected) and problem.better(selected, best):
                    best = selected
                    best_seeds = seeds
        if best is None:
            return problem.infeasible_result(requested=requested, strategy_id=self.strategy_id)
        return problem.result(
            selected=best,
            selected_seeds=best_seeds,
            requested=requested,
            strategy_id=self.strategy_id,
            status=SelectionStatus.OPTIMAL,
            runtime_ms=(time.perf_counter() - started) * 1000,
            trace=(f"enumerated_valid_decisions:{examined}",),
        )


class DynamicProgrammingSelection:
    strategy_id = "dynamic_programming"
    strategy_version = "1.0.0"

    def select(
        self,
        graph: ContextGraph,
        analyses: Mapping[str, NodeAnalysis],
        compilation: CompilationUnit,
    ) -> SelectionResult:
        started = time.perf_counter()
        problem = SelectionProblem(graph, analyses, compilation)
        requested = _requested(problem, self.strategy_id)
        limits = compilation.optimizer.limits
        if problem.mandatory_infeasible_reason:
            return problem.infeasible_result(requested=requested, strategy_id=self.strategy_id)
        optional = problem.optional_node_ids
        remaining_budget = problem.available_tokens - problem.cost(problem.mandatory_closure)
        estimated_states = (len(optional) + 1) * (remaining_budget + 1)
        estimated_memory = estimated_states * 64
        unsafe = (
            not problem.dependency_free
            or len(optional) > limits.max_dp_nodes
            or problem.available_tokens > limits.max_dp_budget
            or estimated_states > limits.max_dp_states
            or estimated_memory > limits.max_dp_memory_bytes
        )
        if unsafe:
            return _fallback(
                problem,
                requested,
                "dynamic programming unsupported/unsafe: requires dependency-free bounded "
                f"instance; nodes={len(optional)}, budget={problem.available_tokens}, "
                f"states={estimated_states}, memory={estimated_memory}",
            )
        states: dict[int, frozenset[str]] = {0: frozenset()}
        for node_id in sorted(optional, key=problem.stable_key):
            cost = problem.costs[node_id]
            updated = dict(states)
            for used, selected_optional in sorted(states.items(), reverse=True):
                new_cost = used + cost
                if new_cost > remaining_budget:
                    continue
                candidate = selected_optional | {node_id}
                current = updated.get(new_cost)
                candidate_full = problem.mandatory_closure | candidate
                current_full = None if current is None else problem.mandatory_closure | current
                if problem.better(candidate_full, current_full):
                    updated[new_cost] = candidate
            states = updated
        best_optional: frozenset[str] | None = None
        best_full: frozenset[str] | None = None
        for selected_optional in states.values():
            full = problem.mandatory_closure | selected_optional
            if problem.better(full, best_full):
                best_optional = selected_optional
                best_full = full
        if best_optional is None or best_full is None:
            return problem.infeasible_result(requested=requested, strategy_id=self.strategy_id)
        return problem.result(
            selected=best_full,
            selected_seeds=problem.mandatory | best_optional,
            requested=requested,
            strategy_id=self.strategy_id,
            status=SelectionStatus.OPTIMAL,
            runtime_ms=(time.perf_counter() - started) * 1000,
            trace=(f"dp_final_states:{len(states)}", f"dp_estimated_states:{estimated_states}"),
        )


class ILPSelection:
    strategy_id = "ilp"
    strategy_version = "1.0.0"

    def select(
        self,
        graph: ContextGraph,
        analyses: Mapping[str, NodeAnalysis],
        compilation: CompilationUnit,
    ) -> SelectionResult:
        started = time.perf_counter()
        problem = SelectionProblem(graph, analyses, compilation)
        requested = _requested(problem, self.strategy_id)
        limits = compilation.optimizer.limits
        if problem.mandatory_infeasible_reason:
            return problem.infeasible_result(requested=requested, strategy_id=self.strategy_id)
        if (
            len(graph.node_ids) > limits.ilp_max_nodes
            or len(problem.dependency_pairs) > limits.ilp_max_dependency_edges
        ):
            return _fallback(problem, requested, "ILP configured size limit exceeded")
        if importlib.util.find_spec("pulp") is None:
            return _fallback(problem, requested, "PuLP ILP solver is unavailable")
        try:
            pulp = importlib.import_module("pulp")

            model = pulp.LpProblem("contextc_m5_selection", pulp.LpMaximize)
            variables = {
                node_id: pulp.LpVariable(f"select_{index:06d}", cat="Binary")
                for index, node_id in enumerate(graph.node_ids)
            }
            coverage_by_source: dict[str, int] = {}
            for source, _target in problem.dependency_pairs:
                coverage_by_source[source] = coverage_by_source.get(source, 0) + 1
            weight = compilation.optimizer.objective_weights.dependency_coverage
            model += pulp.lpSum(
                (problem.base_value(node_id) + coverage_by_source.get(node_id, 0) * weight)
                * variables[node_id]
                for node_id in graph.node_ids
            )
            model += (
                pulp.lpSum(
                    problem.costs[node_id] * variables[node_id] for node_id in graph.node_ids
                )
                <= problem.available_tokens,
                "source_content_allowance",
            )
            for index, node_id in enumerate(sorted(problem.mandatory)):
                model += variables[node_id] == 1, f"mandatory_{index:06d}"
            for index, node_id in enumerate(sorted(problem.blocked)):
                model += variables[node_id] == 0, f"blocked_{index:06d}"
            for index, (source, target) in enumerate(problem.dependency_pairs):
                model += variables[source] <= variables[target], f"dependency_{index:06d}"
            solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=limits.ilp_timeout_ms / 1000)
            status_code = model.solve(solver)
            runtime_ms = (time.perf_counter() - started) * 1000
            has_incumbent = all(variable.value() is not None for variable in variables.values())
            selected = frozenset(
                node_id
                for node_id, variable in variables.items()
                if variable.value() is not None and variable.value() >= 0.5
            )
            if status_code == pulp.LpStatusOptimal and problem.is_feasible(selected):
                return problem.result(
                    selected=selected,
                    requested=requested,
                    strategy_id=self.strategy_id,
                    status=SelectionStatus.OPTIMAL,
                    runtime_ms=runtime_ms,
                    timeout_ms=limits.ilp_timeout_ms,
                    trace=("solver_status:optimal",),
                )
            if has_incumbent and problem.is_feasible(selected):
                reason = f"ILP stopped without optimality proof: {pulp.LpStatus[status_code]}"
                return problem.result(
                    selected=selected,
                    requested=requested,
                    strategy_id=self.strategy_id,
                    status=SelectionStatus.FEASIBLE_TIMEOUT,
                    runtime_ms=runtime_ms,
                    timeout_ms=limits.ilp_timeout_ms,
                    fallback_reason=reason,
                    diagnostics=(_fallback_diagnostic(reason, requested, self.strategy_id),),
                    trace=(f"solver_status:{pulp.LpStatus[status_code]}",),
                )
            return _fallback(
                problem,
                requested,
                f"ILP returned no feasible incumbent: {pulp.LpStatus[status_code]}",
            )
        except Exception as error:
            return _fallback(
                problem, requested, f"ILP solver error: {type(error).__name__}: {error}"
            )


StrategyFactory = Callable[[], SelectionStrategy]

STRATEGY_TYPES: dict[str, StrategyFactory] = {
    "naive": NaiveSelection,
    "recency": RecencySelection,
    "top_k": TopKSelection,
    "relevance_greedy": RelevanceGreedySelection,
    "density_greedy": DensityGreedySelection,
    "brute_force": BruteForceSelection,
    "dynamic_programming": DynamicProgrammingSelection,
    "ilp": ILPSelection,
    "graph_closure_greedy": GraphClosureGreedySelection,
}


def strategy_for(strategy_id: str) -> SelectionStrategy:
    """Return a fresh strategy instance from the authoritative registry."""

    try:
        return STRATEGY_TYPES[strategy_id]()
    except KeyError as error:
        raise ValueError(f"unknown optimizer strategy: {strategy_id}") from error
