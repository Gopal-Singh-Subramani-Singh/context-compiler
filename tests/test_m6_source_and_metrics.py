from __future__ import annotations

from dataclasses import replace

import pytest

from contextc.benchmark import (
    GroundTruth,
    SelectedLocation,
    SourceSpan,
    calculate_raw_metrics,
    canonical_repository_uri,
    union_line_units,
)
from contextc.errors import SourceValidationError


def location(uri: str, start: int, end: int, tokens: int, rank: int) -> SelectedLocation:
    return SelectedLocation(f"node-{rank}", SourceSpan(uri, start, end), tokens, rank)


def metrics(labels: GroundTruth, selected: tuple[SelectedLocation, ...], final: int = 60):
    return calculate_raw_metrics(
        labels=labels,
        selected=selected,
        final_rendered_tokens=final,
        configured_budget=100,
        compilation_latency_ms=12.5,
        optimizer_runtime_ms=2.5,
    )


def test_canonical_repository_uri_normalizes_equivalent_spellings() -> None:
    assert canonical_repository_uri("repo://fixture/src/./auth.py") == (
        "repo://fixture/src/auth.py"
    )
    assert canonical_repository_uri("repo:///src//auth.py", repository_id="fixture") == (
        "repo://fixture/src/auth.py"
    )
    for invalid in (
        "repo://fixture/src/../secret",
        "repo://fixture/src/%2e%2e/secret",
        "file:///src/auth.py",
        "repo://fixture",
        "repo://fixture/src\\auth.py",
        "repo://fixture:80/src/auth.py",
        "repo://fixture/src/auth file.py",
    ):
        with pytest.raises(SourceValidationError):
            canonical_repository_uri(invalid)


def test_spans_are_inclusive_and_union_overlap_once() -> None:
    first = SourceSpan("repo://fixture/a.py", 1, 3)
    second = SourceSpan("repo://fixture/a.py", 3, 5)
    assert first.line_count == 3
    assert first.intersection_lines(second) == 1
    assert len(union_line_units((first, second))) == 5
    with pytest.raises(SourceValidationError):
        SourceSpan("repo://fixture/a.py", 0, 2)


def test_all_ten_metrics_have_hand_calculated_partial_duplicate_distractor_values() -> None:
    required = SourceSpan("repo://fixture/a.py", 1, 4)
    accepted = SourceSpan("repo://fixture/b.py", 1, 2)
    labels = GroundTruth(
        required_spans=(required,),
        accepted_spans=(accepted,),
        required_dependencies=((required, accepted),),
    )
    selected = (
        location("repo://fixture/a.py", 1, 2, 20, 1),
        location("repo://fixture/a.py", 2, 3, 20, 2),
        location("repo://fixture/b.py", 1, 1, 10, 3),
        location("repo://fixture/distractor.py", 1, 1, 10, 4),
    )
    result = metrics(labels, selected)
    assert result.required_file_recall == 1.0
    assert result.required_file_precision == pytest.approx(2 / 3)
    assert result.required_span_recall == 0.75
    assert result.dependency_closure_coverage == 1.0
    assert result.useful_token_ratio == pytest.approx(2 / 3)
    assert result.redundant_token_ratio == pytest.approx(1 / 6)
    assert result.unsupported_context_ratio == pytest.approx(1 / 6)
    assert result.budget_utilization == 0.6
    assert result.compilation_latency_ms == 12.5
    assert result.optimizer_runtime_ms == 2.5


def test_perfect_zero_empty_and_infeasible_metric_policies_are_explicit() -> None:
    span = SourceSpan("repo://fixture/a.py", 1, 2)
    labels = GroundTruth(required_spans=(span,))
    perfect = metrics(labels, (location(span.source_uri, 1, 2, 10, 1),), final=100)
    assert perfect.required_file_recall == perfect.required_file_precision == 1.0
    assert perfect.required_span_recall == perfect.useful_token_ratio == 1.0
    assert perfect.budget_utilization == 1.0

    zero = metrics(labels, ())
    assert zero.required_file_recall == zero.required_span_recall == 0.0
    assert zero.required_file_precision == 1.0
    assert zero.useful_token_ratio == 1.0

    empty = metrics(GroundTruth(required_spans=()), ())
    assert empty.required_file_recall == empty.required_file_precision == 1.0
    assert empty.required_span_recall == empty.dependency_closure_coverage == 1.0

    infeasible = replace(zero, compilation_latency_ms=0.0, optimizer_runtime_ms=0.0)
    assert infeasible.required_span_recall == 0.0


def test_dependency_metric_requires_both_relation_endpoints() -> None:
    source = SourceSpan("repo://fixture/a.py", 1, 1)
    target = SourceSpan("repo://fixture/b.py", 1, 1)
    labels = GroundTruth(required_spans=(source,), required_dependencies=((source, target),))
    partial = metrics(labels, (location(source.source_uri, 1, 1, 5, 1),))
    assert partial.dependency_closure_coverage == 0.0


def test_large_proportional_attribution_clamps_float_boundary_drift() -> None:
    label = SourceSpan("repo://fixture/target.py", 1, 1)
    unsupported = SourceSpan("repo://fixture/noise.py", 1, 152)
    result = metrics(
        GroundTruth(required_spans=(label,)),
        (SelectedLocation("noise", unsupported, 1078, 1),),
    )
    assert result.unsupported_context_ratio == 1.0
    assert result.useful_token_ratio == 0.0
