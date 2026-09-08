"""Evaluator-only ground-truth loader, physically separate from public compilation."""

from __future__ import annotations

from pathlib import Path

from contextc.decoding import (
    optional_string,
    require_int,
    require_mapping,
    require_sequence,
    require_string,
)

from ._records import read_json_yaml
from .models import GroundTruth
from .source import SourceSpan, canonical_repository_uri


def _span(value: object, *, repository_id: str) -> SourceSpan:
    item = require_mapping(value, "ground_truth.span")
    uri = require_string(item.get("source_uri"), "ground_truth.span.source_uri")
    if uri.startswith("repo:///"):
        uri = canonical_repository_uri(uri, repository_id=repository_id)
    else:
        uri = canonical_repository_uri(uri)
    return SourceSpan(
        source_uri=uri,
        start_line=require_int(item.get("start_line"), "ground_truth.span.start_line"),
        end_line=require_int(item.get("end_line"), "ground_truth.span.end_line"),
    )


def load_ground_truth(task_directory: Path, *, repository_id: str) -> GroundTruth:
    value = read_json_yaml(task_directory / "evaluator" / "labels.yaml")
    required = tuple(
        _span(item, repository_id=repository_id)
        for item in require_sequence(value.get("required_spans"), "labels.required_spans")
    )
    accepted = tuple(
        _span(item, repository_id=repository_id)
        for item in require_sequence(value.get("accepted_spans", ()), "labels.accepted_spans")
    )
    dependencies = []
    for raw in require_sequence(
        value.get("required_dependencies", ()), "labels.required_dependencies"
    ):
        item = require_mapping(raw, "labels.required_dependency")
        dependencies.append(
            (
                _span(item.get("source"), repository_id=repository_id),
                _span(item.get("target"), repository_id=repository_id),
            )
        )
    debug_ids = tuple(
        require_string(item, "labels.debug_expected_node_id")
        for item in require_sequence(
            value.get("debug_expected_node_ids", ()), "labels.debug_expected_node_ids"
        )
    )
    return GroundTruth(
        required_spans=required,
        accepted_spans=accepted,
        required_dependencies=tuple(dependencies),
        debug_expected_node_ids=debug_ids,
        evaluator_sentinel=optional_string(
            value.get("evaluator_sentinel"), "labels.evaluator_sentinel"
        )
        or "",
    )
