"""Transparent, separately reported M6 raw benchmark metrics."""

from __future__ import annotations

from collections.abc import Iterable

from .models import GroundTruth, RawMetrics, SelectedLocation
from .source import SourceSpan, union_line_units


def _safe_fraction(numerator: float, denominator: float, *, empty: float) -> float:
    if denominator == 0:
        return empty
    value = numerator / denominator
    # Proportional attribution can accumulate one representable float above or below
    # the mathematical [0, 1] boundary across large real files. Correct only tiny
    # representation drift; materially invalid ratios remain visible to RawMetrics.
    if -1e-12 <= value < 0.0:
        return 0.0
    if 1.0 < value <= 1.0 + 1e-12:
        return 1.0
    return value


def _span_is_covered(span: SourceSpan, selected_units: frozenset[tuple[str, int]]) -> bool:
    return any(
        (span.source_uri, line) in selected_units
        for line in range(span.start_line, span.end_line + 1)
    )


def calculate_raw_metrics(
    *,
    labels: GroundTruth,
    selected: Iterable[SelectedLocation],
    final_rendered_tokens: int,
    configured_budget: int,
    compilation_latency_ms: float,
    optimizer_runtime_ms: float,
) -> RawMetrics:
    """Calculate all ten metrics with line-union and proportional token attribution."""

    locations = tuple(sorted(selected, key=lambda item: item.rank))
    required_units = union_line_units(labels.required_spans)
    useful_units = union_line_units(labels.useful_spans)
    selected_units = union_line_units(item.span for item in locations)
    required_files = {span.source_uri for span in labels.required_spans}
    accepted_files = {span.source_uri for span in labels.useful_spans}
    selected_files = {item.span.source_uri for item in locations}

    covered_required_files = required_files & selected_files
    required_file_recall = _safe_fraction(
        len(covered_required_files), len(required_files), empty=1.0
    )
    required_file_precision = _safe_fraction(
        len(accepted_files & selected_files), len(selected_files), empty=1.0
    )
    required_span_recall = _safe_fraction(
        len(required_units & selected_units), len(required_units), empty=1.0
    )

    covered_dependencies = sum(
        _span_is_covered(source, selected_units) and _span_is_covered(target, selected_units)
        for source, target in labels.required_dependencies
    )
    dependency_coverage = _safe_fraction(
        covered_dependencies, len(labels.required_dependencies), empty=1.0
    )

    seen_useful: set[tuple[str, int]] = set()
    useful_tokens = 0.0
    redundant_tokens = 0.0
    unsupported_tokens = 0.0
    total_source_tokens = sum(item.source_tokens for item in locations)
    for item in locations:
        units = tuple(
            (item.span.source_uri, line)
            for line in range(item.span.start_line, item.span.end_line + 1)
        )
        per_line = item.source_tokens / len(units)
        for unit in units:
            if unit not in useful_units:
                unsupported_tokens += per_line
            elif unit in seen_useful:
                redundant_tokens += per_line
            else:
                useful_tokens += per_line
                seen_useful.add(unit)

    return RawMetrics(
        required_file_recall=required_file_recall,
        required_file_precision=required_file_precision,
        required_span_recall=required_span_recall,
        dependency_closure_coverage=dependency_coverage,
        useful_token_ratio=_safe_fraction(useful_tokens, total_source_tokens, empty=1.0),
        redundant_token_ratio=_safe_fraction(redundant_tokens, total_source_tokens, empty=0.0),
        unsupported_context_ratio=_safe_fraction(
            unsupported_tokens, total_source_tokens, empty=0.0
        ),
        budget_utilization=_safe_fraction(final_rendered_tokens, configured_budget, empty=0.0),
        compilation_latency_ms=compilation_latency_ms,
        optimizer_runtime_ms=optimizer_runtime_ms,
    )
