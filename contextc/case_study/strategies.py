"""Bounded strategy set for scalable, equal-footing historical comparisons."""

from __future__ import annotations

from contextc.errors import SourceValidationError

CASE_STUDY_STRATEGIES = (
    "naive",
    "top_k",
    "relevance_greedy",
    "density_greedy",
    "graph_closure_greedy",
)


def normalized_strategies(values: tuple[str, ...]) -> tuple[str, ...]:
    strategies = values if values else CASE_STUDY_STRATEGIES
    if len(strategies) != len(set(strategies)) or any(not item for item in strategies):
        raise SourceValidationError("case-study strategies must be unique and non-empty")
    unknown = sorted(set(strategies) - set(CASE_STUDY_STRATEGIES))
    if unknown:
        raise SourceValidationError(f"unsupported case-study strategies: {unknown}")
    return strategies
