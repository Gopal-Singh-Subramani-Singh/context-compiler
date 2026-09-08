"""The single M5 objective and constraint model used by every strategy."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from contextc.diagnostics import Diagnostic, DiagnosticCode, get_definition
from contextc.errors import GraphInvariantError, SourceValidationError
from contextc.ir.analysis import NodeAnalysis
from contextc.ir.compilation import CompilationUnit, SelectionResult, SelectionStatus
from contextc.ir.graph import ContextGraph


@dataclass(frozen=True, slots=True)
class ConstraintViolation:
    code: str
    detail: str


class SelectionProblem:
    """Validated common selection problem with deterministic helper operations."""

    def __init__(
        self,
        graph: ContextGraph,
        analyses: Mapping[str, NodeAnalysis],
        compilation: CompilationUnit,
    ) -> None:
        self.graph = graph
        self.analyses = dict(analyses)
        self.compilation = compilation
        node_ids = set(graph.node_ids)
        unknown = sorted(set(analyses) - node_ids)
        missing = sorted(node_ids - set(analyses))
        if unknown or missing:
            raise GraphInvariantError(
                f"analysis/graph node mismatch; unknown={unknown}, missing={missing}"
            )
        config = compilation.optimizer
        referenced = (
            set(config.mandatory_node_ids)
            | set(config.blocked_node_ids)
            | set(config.policy_eligible_node_ids or ())
        )
        invalid = sorted(referenced - node_ids)
        if invalid:
            raise GraphInvariantError(
                f"optimizer configuration references unknown nodes: {invalid}"
            )
        self.available_tokens = (
            compilation.token_budget
            if config.source_content_allowance is None
            else config.source_content_allowance
        )
        self.costs: dict[str, int] = {}
        for node_id in graph.node_ids:
            counts = self.analyses[node_id].token_counts
            if compilation.tokenizer_id not in counts:
                raise SourceValidationError(
                    f"analysis for {node_id} lacks target token cost {compilation.tokenizer_id!r}"
                )
            self.costs[node_id] = counts[compilation.tokenizer_id]
        analysis_mandatory = {
            node_id for node_id, analysis in self.analyses.items() if analysis.mandatory
        }
        self.mandatory = frozenset(analysis_mandatory | set(config.mandatory_node_ids))
        allowed = node_ids - set(config.blocked_node_ids)
        if config.policy_eligible_node_ids is not None:
            allowed &= set(config.policy_eligible_node_ids)
        self.allowed = frozenset(allowed)
        self.blocked = frozenset(node_ids - allowed)
        self.dependency_pairs = tuple(
            sorted(
                {
                    (edge.source_node_id, edge.target_node_id)
                    for edge in graph.edges
                    if edge.edge_type in graph.dependency_edge_types
                }
            )
        )
        closure = graph.dependency_closure(self.mandatory)
        self.mandatory_closure = frozenset(closure.node_ids)
        self.mandatory_diagnostics = closure.diagnostics
        self.mandatory_infeasible_reason = self._mandatory_infeasible_reason()

    def _mandatory_infeasible_reason(self) -> str | None:
        disallowed = sorted(self.mandatory_closure - self.allowed)
        if disallowed:
            return (
                "mandatory dependency closure contains blocked/policy-ineligible nodes: "
                f"{disallowed}"
            )
        cost = self.cost(self.mandatory_closure)
        if cost > self.available_tokens:
            return (
                "mandatory dependency closure exceeds source-content allowance: "
                f"required={cost}, available={self.available_tokens}"
            )
        return None

    @property
    def optional_node_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.allowed - self.mandatory_closure))

    @property
    def dependency_free(self) -> bool:
        return not self.dependency_pairs

    def cost(self, node_ids: Iterable[str]) -> int:
        return sum(self.costs[node_id] for node_id in set(node_ids))

    def base_value(self, node_id: str) -> float:
        analysis = self.analyses[node_id]
        weights = self.compilation.optimizer.objective_weights
        return math.fsum(
            (
                analysis.relevance * weights.relevance,
                analysis.trust_score * weights.trust,
                analysis.freshness * weights.freshness,
                -analysis.redundancy_score * weights.redundancy_penalty,
                -analysis.security_risk * weights.security_risk_penalty,
            )
        )

    def objective(self, node_ids: Iterable[str]) -> float:
        selected = frozenset(node_ids)
        base = math.fsum(self.base_value(node_id) for node_id in sorted(selected))
        covered = sum(
            1
            for source, target in self.dependency_pairs
            if source in selected and target in selected
        )
        return math.fsum(
            (
                base,
                covered * self.compilation.optimizer.objective_weights.dependency_coverage,
            )
        )

    def closure(self, seed_node_ids: Iterable[str]) -> frozenset[str]:
        return frozenset(self.graph.dependency_closure(seed_node_ids).node_ids)

    def violations(self, node_ids: Iterable[str]) -> tuple[ConstraintViolation, ...]:
        ordered = tuple(node_ids)
        selected = frozenset(ordered)
        violations: list[ConstraintViolation] = []
        if len(ordered) != len(selected):
            violations.append(ConstraintViolation("duplicate", "selection contains duplicate IDs"))
        unknown = sorted(selected - set(self.graph.node_ids))
        if unknown:
            violations.append(ConstraintViolation("unknown", f"unknown selected nodes: {unknown}"))
        blocked = sorted(selected - self.allowed)
        if blocked:
            violations.append(
                ConstraintViolation(
                    "blocked", f"blocked/policy-ineligible selected nodes: {blocked}"
                )
            )
        missing_mandatory = sorted(self.mandatory - selected)
        if missing_mandatory:
            violations.append(
                ConstraintViolation("mandatory", f"mandatory nodes omitted: {missing_mandatory}")
            )
        if not unknown:
            missing_dependencies = sorted(self.closure(selected) - selected)
            if missing_dependencies:
                violations.append(
                    ConstraintViolation(
                        "dependency", f"dependency closure omitted: {missing_dependencies}"
                    )
                )
            used = self.cost(selected)
            if used > self.available_tokens:
                violations.append(
                    ConstraintViolation(
                        "allowance",
                        f"selection costs {used}, allowance is {self.available_tokens}",
                    )
                )
        return tuple(violations)

    def is_feasible(self, node_ids: Iterable[str]) -> bool:
        return not self.violations(node_ids)

    def stable_key(self, node_id: str, primary: float | None = None) -> tuple[object, ...]:
        node = self.graph.get_node(node_id)
        analysis = self.analyses[node_id]
        utility = self.base_value(node_id) if primary is None else primary
        return (
            -utility,
            -analysis.relevance,
            self.costs[node_id],
            node.source.uri,
            node.source.start_line or 0,
            node.source.end_line or 0,
            node_id,
        )

    def ordered(self, node_ids: Iterable[str]) -> tuple[str, ...]:
        selected = set(node_ids)
        if not selected:
            return ()
        dependencies = {
            node_id: {
                target
                for source, target in self.dependency_pairs
                if source == node_id and target in selected
            }
            for node_id in selected
        }
        remaining = set(selected)
        ordered: list[str] = []
        while remaining:
            ready = [node_id for node_id in remaining if not (dependencies[node_id] & remaining)]
            if not ready:
                return tuple(sorted(selected, key=self.stable_key))
            current = min(ready, key=self.stable_key)
            ordered.append(current)
            remaining.remove(current)
        return tuple(ordered)

    def better(self, left: frozenset[str], right: frozenset[str] | None) -> bool:
        if right is None:
            return True
        left_value = self.objective(left)
        right_value = self.objective(right)
        if not math.isclose(left_value, right_value, rel_tol=0.0, abs_tol=1e-12):
            return left_value > right_value
        left_cost = self.cost(left)
        right_cost = self.cost(right)
        if left_cost != right_cost:
            return left_cost < right_cost
        return tuple(self.stable_key(item) for item in self.ordered(left)) < tuple(
            self.stable_key(item) for item in self.ordered(right)
        )

    def tie_break_evidence(self) -> tuple[str, ...]:
        """Record bounded source-aware ordering for genuine equal-utility candidates."""

        groups: dict[tuple[float, float], list[str]] = {}
        for node_id in self.graph.node_ids:
            key = (self.base_value(node_id), self.analyses[node_id].relevance)
            groups.setdefault(key, []).append(node_id)
        evidence = []
        for (utility, relevance), node_ids in sorted(groups.items(), reverse=True):
            if len(node_ids) < 2:
                continue
            ordered = sorted(node_ids, key=self.stable_key)
            evidence.append(
                f"tie:utility={utility:.12g}:relevance={relevance:.12g}:"
                f"stable_order={','.join(ordered)}"
            )
        return tuple(evidence[:8])

    def canonical_seeds(self, node_ids: Iterable[str]) -> frozenset[str]:
        """Derive a deterministic minimal closure generator for solver-selected sets.

        Exact solvers return binary selected variables rather than seed decisions. Removing
        dependency nodes that are regenerated by the remaining selected dependents makes their
        forced-inclusion evidence consistent with closure-based strategies.
        """

        selected = frozenset(node_ids)
        seeds = set(selected)
        for candidate in self.ordered(selected):
            if candidate in self.mandatory:
                continue
            without_candidate = seeds - {candidate}
            if self.closure(without_candidate) == selected:
                seeds.remove(candidate)
        return frozenset(seeds)

    def _diagnostic(self, code: DiagnosticCode, evidence: Mapping[str, object]) -> Diagnostic:
        definition = get_definition(code)
        return Diagnostic(
            code=code,
            severity=definition.default_severity,
            message=definition.title,
            node_ids=tuple(sorted(self.mandatory_closure)),
            evidence=evidence,
            owning_pass="optimizer",
        )

    def infeasible_result(self, *, requested: str, strategy_id: str) -> SelectionResult:
        reason = self.mandatory_infeasible_reason or "selection constraints are infeasible"
        diagnostic = self._diagnostic(
            DiagnosticCode.OPTIMIZER_INFEASIBLE,
            {"reason": reason, "available_tokens": self.available_tokens},
        )
        return SelectionResult(
            selected_node_ids=(),
            excluded_node_ids=self.graph.node_ids,
            mandatory_node_ids=tuple(sorted(self.mandatory)),
            requested_strategy_id=requested,
            strategy_id=strategy_id,
            strategy_version="1.0.0",
            optimizer_status=SelectionStatus.INFEASIBLE,
            objective_value=None,
            used_tokens=0,
            available_tokens=self.available_tokens,
            diagnostics=(diagnostic,),
            excluded_reasons={node_id: "infeasible_constraints" for node_id in self.graph.node_ids},
            fallback_reason=reason,
        )

    def result(
        self,
        *,
        selected: Iterable[str],
        requested: str,
        strategy_id: str,
        status: SelectionStatus,
        selected_seeds: Iterable[str] | None = None,
        runtime_ms: float = 0.0,
        timeout_ms: int | None = None,
        fallback_reason: str | None = None,
        diagnostics: tuple[Diagnostic, ...] = (),
        trace: Iterable[str] = (),
    ) -> SelectionResult:
        selected_set = frozenset(selected)
        violations = self.violations(selected_set)
        if violations:
            raise GraphInvariantError(
                "optimizer produced invalid selection: "
                + "; ".join(item.detail for item in violations)
            )
        seeds = (
            self.canonical_seeds(selected_set)
            if selected_seeds is None
            else frozenset(selected_seeds)
        )
        forced = selected_set - seeds
        ordered = self.ordered(selected_set)
        excluded = tuple(node_id for node_id in self.graph.node_ids if node_id not in selected_set)
        return SelectionResult(
            selected_node_ids=ordered,
            excluded_node_ids=excluded,
            dependency_forced_node_ids=tuple(sorted(forced)),
            mandatory_node_ids=tuple(sorted(self.mandatory)),
            requested_strategy_id=requested,
            strategy_id=strategy_id,
            strategy_version="1.0.0",
            optimizer_status=status,
            objective_value=self.objective(selected_set),
            used_tokens=self.cost(selected_set),
            available_tokens=self.available_tokens,
            solver_runtime_ms=runtime_ms,
            solver_timeout_ms=timeout_ms,
            fallback_reason=fallback_reason,
            tie_break_trace=(tuple(trace) + self.tie_break_evidence())[:64],
            diagnostics=self.mandatory_diagnostics + diagnostics,
            excluded_reasons={node_id: "not_selected_under_objective" for node_id in excluded},
        )
