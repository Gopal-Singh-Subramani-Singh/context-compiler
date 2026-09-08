"""Immutable, versioned M6 benchmark evidence models."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

from contextc.canonical import freeze_value, to_canonical_primitive
from contextc.errors import SourceValidationError
from contextc.hashing import semantic_hash
from contextc.schema import (
    BENCHMARK_METRICS_SCHEMA,
    BENCHMARK_RUN_SCHEMA,
    GROUND_TRUTH_SCHEMA,
    TOP_K_TRACE_SCHEMA,
    SchemaVersion,
)

from .source import SourceSpan


@dataclass(frozen=True, slots=True)
class GroundTruth:
    required_spans: tuple[SourceSpan, ...]
    accepted_spans: tuple[SourceSpan, ...] = ()
    required_dependencies: tuple[tuple[SourceSpan, SourceSpan], ...] = ()
    debug_expected_node_ids: tuple[str, ...] = ()
    evaluator_sentinel: str = ""
    schema_version: SchemaVersion = GROUND_TRUTH_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_spans", tuple(sorted(set(self.required_spans))))
        object.__setattr__(self, "accepted_spans", tuple(sorted(set(self.accepted_spans))))
        object.__setattr__(
            self,
            "required_dependencies",
            tuple(sorted(set(self.required_dependencies))),
        )
        object.__setattr__(self, "debug_expected_node_ids", tuple(self.debug_expected_node_ids))
        if any(not item for item in self.debug_expected_node_ids):
            raise SourceValidationError("debug node IDs must not be empty")

    @property
    def useful_spans(self) -> tuple[SourceSpan, ...]:
        return tuple(sorted(set(self.required_spans) | set(self.accepted_spans)))

    @property
    def label_identity(self) -> str:
        return semantic_hash(
            {
                "required_spans": self.required_spans,
                "accepted_spans": self.accepted_spans,
                "required_dependencies": self.required_dependencies,
                "schema_version": self.schema_version,
            }
        )


@dataclass(frozen=True, slots=True)
class SelectedLocation:
    node_id: str
    span: SourceSpan
    source_tokens: int
    rank: int

    def __post_init__(self) -> None:
        if not self.node_id or self.source_tokens < 0 or self.rank < 1:
            raise SourceValidationError("selected location identity/count/rank is invalid")


@dataclass(frozen=True, slots=True)
class RawMetrics:
    required_file_recall: float
    required_file_precision: float
    required_span_recall: float
    dependency_closure_coverage: float
    useful_token_ratio: float
    redundant_token_ratio: float
    unsupported_context_ratio: float
    budget_utilization: float
    compilation_latency_ms: float
    optimizer_runtime_ms: float
    schema_version: SchemaVersion = BENCHMARK_METRICS_SCHEMA

    def __post_init__(self) -> None:
        ratios = (
            self.required_file_recall,
            self.required_file_precision,
            self.required_span_recall,
            self.dependency_closure_coverage,
            self.useful_token_ratio,
            self.redundant_token_ratio,
            self.unsupported_context_ratio,
            self.budget_utilization,
        )
        values = (*ratios, self.compilation_latency_ms, self.optimizer_runtime_ms)
        if any(not math.isfinite(value) for value in values):
            raise SourceValidationError("benchmark metrics must be finite")
        if any(not 0.0 <= value <= 1.0 for value in ratios):
            raise SourceValidationError("benchmark ratios must be within [0, 1]")
        if min(self.compilation_latency_ms, self.optimizer_runtime_ms) < 0:
            raise SourceValidationError("benchmark runtimes must not be negative")

    def semantic_form(self) -> dict[str, object]:
        value = to_canonical_primitive(self)
        if not isinstance(value, dict):
            raise AssertionError("benchmark metrics did not canonicalize")
        value.pop("compilation_latency_ms")
        value.pop("optimizer_runtime_ms")
        return value


@dataclass(frozen=True, slots=True)
class TopKCandidate:
    node_id: str
    span: SourceSpan
    similarity: float
    rank: int
    selected: bool
    evaluator_overlap_lines: int = 0

    def __post_init__(self) -> None:
        if not self.node_id or not math.isfinite(self.similarity) or self.rank < 1:
            raise SourceValidationError("Top-K candidate evidence is invalid")
        if self.evaluator_overlap_lines < 0:
            raise SourceValidationError("Top-K overlap must not be negative")


@dataclass(frozen=True, slots=True)
class TopKTrace:
    query_text: str
    status: str
    embedding_model_id: str | None = None
    embedding_model_version: str | None = None
    embedding_revision: str | None = None
    candidates: tuple[TopKCandidate, ...] = ()
    selected_node_ids: tuple[str, ...] = ()
    removed_node_ids: tuple[str, ...] = ()
    schema_version: SchemaVersion = TOP_K_TRACE_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "selected_node_ids", tuple(self.selected_node_ids))
        object.__setattr__(self, "removed_node_ids", tuple(self.removed_node_ids))
        if not self.query_text or self.status not in {"retrieved", "fallback", "unsupported"}:
            raise SourceValidationError("Top-K trace query/status is invalid")
        if self.status == "retrieved" and not self.embedding_model_id:
            raise SourceValidationError("retrieved Top-K trace requires a model identity")
        if self.status != "retrieved" and self.candidates:
            raise SourceValidationError("fallback Top-K trace cannot fabricate candidates")


@dataclass(frozen=True, slots=True)
class BenchmarkRun:
    task_id: str
    strategy_id: str
    strategy_version: str
    input_fingerprint: str
    evaluator_label_identity: str
    source_revision: str | None
    graph_identity: str
    task_identity: str
    analysis_identity: str
    target_id: str
    tokenizer_identity: str
    configured_budget: int
    fixed_overhead_tokens: int
    source_allowance_tokens: int
    optimizer_status: str
    selected_locations: tuple[SelectedLocation, ...]
    rendered_token_count: int
    metrics: RawMetrics
    top_k_trace: TopKTrace | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    run_id: str = ""
    schema_version: SchemaVersion = BENCHMARK_RUN_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "selected_locations", tuple(self.selected_locations))
        frozen = freeze_value(self.metadata)
        if not isinstance(frozen, Mapping):
            raise SourceValidationError("benchmark metadata must be a mapping")
        object.__setattr__(self, "metadata", frozen)
        if not all((self.task_id, self.strategy_id, self.strategy_version, self.input_fingerprint)):
            raise SourceValidationError("benchmark run identities must not be empty")
        counts = (
            self.configured_budget,
            self.fixed_overhead_tokens,
            self.source_allowance_tokens,
            self.rendered_token_count,
        )
        if any(value < 0 for value in counts):
            raise SourceValidationError("benchmark run counts must not be negative")
        expected = semantic_hash(self.semantic_form())
        if self.run_id and self.run_id != expected:
            raise SourceValidationError("benchmark run_id disagrees with semantic evidence")
        object.__setattr__(self, "run_id", expected)

    def semantic_form(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "input_fingerprint": self.input_fingerprint,
            "evaluator_label_identity": self.evaluator_label_identity,
            "source_revision": self.source_revision,
            "graph_identity": self.graph_identity,
            "task_identity": self.task_identity,
            "analysis_identity": self.analysis_identity,
            "target_id": self.target_id,
            "tokenizer_identity": self.tokenizer_identity,
            "configured_budget": self.configured_budget,
            "fixed_overhead_tokens": self.fixed_overhead_tokens,
            "source_allowance_tokens": self.source_allowance_tokens,
            "optimizer_status": self.optimizer_status,
            "selected_locations": self.selected_locations,
            "rendered_token_count": self.rendered_token_count,
            "metrics": self.metrics.semantic_form(),
            "top_k_trace": self.top_k_trace,
            "metadata": self.metadata,
            "schema_version": self.schema_version,
        }
