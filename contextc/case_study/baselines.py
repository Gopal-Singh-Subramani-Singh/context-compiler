"""Transparent descriptive comparisons over raw M6 case-study rows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def strategy_means(rows: Iterable[Mapping[str, object]]) -> tuple[dict[str, object], ...]:
    """Return descriptive means while leaving the complete raw table authoritative."""

    metric_names = (
        "required_file_recall",
        "required_file_precision",
        "required_span_recall",
        "dependency_closure_coverage",
        "useful_token_ratio",
        "redundant_token_ratio",
        "unsupported_context_ratio",
        "budget_utilization",
        "compilation_latency_ms",
        "optimizer_runtime_ms",
    )
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for row in rows:
        strategy = row.get("strategy_requested")
        if isinstance(strategy, str):
            grouped.setdefault(strategy, []).append(row)
    results = []
    for strategy, group in sorted(grouped.items()):
        means: dict[str, object] = {"strategy": strategy, "tasks": len(group)}
        for name in metric_names:
            values = [value for row in group if isinstance((value := row.get(name)), (int, float))]
            means[name] = sum(float(value) for value in values) / len(values) if values else None
        results.append(means)
    return tuple(results)
