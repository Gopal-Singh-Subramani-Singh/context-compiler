"""Immutable, versioned contracts for historical repository case studies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from contextc.benchmark.models import BenchmarkRun, GroundTruth
from contextc.canonical import freeze_value
from contextc.errors import SourceValidationError
from contextc.schema import (
    CASE_STUDY_LABELS_SCHEMA,
    CASE_STUDY_PUBLIC_TASK_SCHEMA,
    CASE_STUDY_REVIEW_SCHEMA,
    SchemaVersion,
)


def _nonempty(value: str, field_name: str) -> str:
    if not value or value.strip() != value:
        raise SourceValidationError(f"{field_name} must be non-empty and trimmed")
    return value


@dataclass(frozen=True, slots=True)
class CaseStudyPublicTask:
    """Compiler-visible historical bug description and bounded configuration."""

    task_id: str
    repository_id: str
    description: str
    pre_fix_revision: str
    token_budget: int
    source_content_allowance: int
    time_anchor: datetime
    system_instruction: str = "Use only supplied pre-fix repository evidence."
    schema_version: SchemaVersion = CASE_STUDY_PUBLIC_TASK_SCHEMA

    def __post_init__(self) -> None:
        for value, name in (
            (self.task_id, "task_id"),
            (self.repository_id, "repository_id"),
            (self.description, "description"),
            (self.pre_fix_revision, "pre_fix_revision"),
            (self.system_instruction, "system_instruction"),
        ):
            _nonempty(value, name)
        if len(self.pre_fix_revision) != 40:
            raise SourceValidationError("pre_fix_revision must be a full Git object ID")
        if self.token_budget < 1 or self.source_content_allowance < 1:
            raise SourceValidationError("case-study budgets must be positive")
        if self.source_content_allowance > self.token_budget:
            raise SourceValidationError("source allowance cannot exceed final token budget")
        if self.time_anchor.tzinfo is None or self.time_anchor.utcoffset() is None:
            raise SourceValidationError("case-study time anchor must be timezone-aware")


@dataclass(frozen=True, slots=True)
class HistoricalLabels:
    """Evaluator-only ground truth derived from an identified historical fix."""

    fix_revision: str
    changed_files: tuple[str, ...]
    ground_truth: GroundTruth
    evidence_url: str
    evaluator_sentinel: str
    schema_version: SchemaVersion = CASE_STUDY_LABELS_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "changed_files", tuple(sorted(set(self.changed_files))))
        _nonempty(self.fix_revision, "fix_revision")
        _nonempty(self.evidence_url, "evidence_url")
        _nonempty(self.evaluator_sentinel, "evaluator_sentinel")
        if len(self.fix_revision) != 40:
            raise SourceValidationError("fix_revision must be a full Git object ID")
        if not self.changed_files or any(
            not item or item.startswith("/") for item in self.changed_files
        ):
            raise SourceValidationError("changed_files must be non-empty relative paths")
        if self.ground_truth.evaluator_sentinel != self.evaluator_sentinel:
            raise SourceValidationError("ground-truth sentinel does not match historical labels")


@dataclass(frozen=True, slots=True)
class ManualReview:
    """Evaluator approval and human rationale; extraction helpers cannot create it."""

    status: str
    reviewer: str
    reviewed_at: str
    evidence_basis: str
    span_reasons: Mapping[str, str]
    dependency_reasons: tuple[str, ...] = ()
    diversity_tags: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    schema_version: SchemaVersion = CASE_STUDY_REVIEW_SCHEMA

    def __post_init__(self) -> None:
        if self.status != "approved":
            raise SourceValidationError("case-study ground truth requires approved manual review")
        for value, name in (
            (self.reviewer, "reviewer"),
            (self.reviewed_at, "reviewed_at"),
            (self.evidence_basis, "evidence_basis"),
        ):
            _nonempty(value, name)
        frozen = freeze_value(self.span_reasons)
        if not isinstance(frozen, Mapping) or not frozen:
            raise SourceValidationError("manual review requires span reasons")
        if any(not key or not value for key, value in frozen.items()):
            raise SourceValidationError("manual-review span reasons must be non-empty")
        object.__setattr__(self, "span_reasons", frozen)
        object.__setattr__(self, "dependency_reasons", tuple(self.dependency_reasons))
        object.__setattr__(self, "diversity_tags", tuple(sorted(set(self.diversity_tags))))
        object.__setattr__(self, "limitations", tuple(self.limitations))


@dataclass(frozen=True, slots=True)
class CaseStudyTask:
    public: CaseStudyPublicTask
    labels: HistoricalLabels
    review: ManualReview


@dataclass(frozen=True, slots=True)
class CaseStudyExecution:
    task: CaseStudyTask
    runs: tuple[BenchmarkRun, ...]
    reference_bundle_unchanged: bool
    evaluator_sentinel_absent: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "runs", tuple(self.runs))
        if not self.runs:
            raise SourceValidationError("case-study execution requires at least one run")


@dataclass(frozen=True, slots=True)
class DeterminismReport:
    task_id: str
    strategies: tuple[str, ...]
    repeated_semantics_identical: bool
    reversed_materialization_identical: bool
    run_ids: tuple[str, ...] = field(default_factory=tuple)
