"""Strict public and evaluator loaders for packaged historical tasks."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from contextc.benchmark._records import read_json_yaml
from contextc.benchmark.labels import load_ground_truth
from contextc.decoding import (
    require_int,
    require_mapping,
    require_sequence,
    require_string,
    require_string_tuple,
)
from contextc.errors import SourceValidationError
from contextc.schema import (
    CASE_STUDY_LABELS_SCHEMA,
    CASE_STUDY_PUBLIC_TASK_SCHEMA,
    CASE_STUDY_REVIEW_SCHEMA,
    SchemaVersion,
    require_schema_version,
)

from .repository import packaged_case_study_root
from .schemas import CaseStudyPublicTask, CaseStudyTask, HistoricalLabels, ManualReview


def packaged_tasks_root() -> Path:
    return packaged_case_study_root() / "tasks"


def list_task_directories(root: Path | None = None) -> tuple[Path, ...]:
    tasks_root = packaged_tasks_root() if root is None else root
    if not tasks_root.is_dir():
        raise SourceValidationError(f"case-study task directory does not exist: {tasks_root}")
    return tuple(
        sorted(
            (path for path in tasks_root.iterdir() if path.is_dir()),
            key=lambda path: path.name,
        )
    )


def resolve_task_directory(value: str | Path, root: Path | None = None) -> Path:
    candidate = Path(value)
    if candidate.is_dir():
        return candidate
    for task_directory in list_task_directories(root):
        public = load_public_case_task(task_directory)
        if value in {task_directory.name, public.task_id}:
            return task_directory
    raise SourceValidationError(f"unknown case-study task: {value}")


def _version(value: object, *, expected: SchemaVersion, artifact: str) -> None:
    require_schema_version(value, expected=expected, artifact=artifact)


def load_public_case_task(task_directory: Path) -> CaseStudyPublicTask:
    """Load compiler-visible data only; evaluator paths are never opened."""

    value = read_json_yaml(task_directory / "public" / "task.yaml")
    _version(
        value.get("schema_version"),
        expected=CASE_STUDY_PUBLIC_TASK_SCHEMA,
        artifact="CaseStudyPublicTask",
    )
    raw_anchor = require_string(value.get("time_anchor"), "task.time_anchor")
    try:
        anchor = datetime.fromisoformat(raw_anchor.replace("Z", "+00:00"))
    except ValueError as error:
        raise SourceValidationError("task.time_anchor must be ISO-8601") from error
    return CaseStudyPublicTask(
        task_id=require_string(value.get("task_id"), "task.task_id"),
        repository_id=require_string(value.get("repository_id"), "task.repository_id"),
        description=require_string(value.get("description"), "task.description"),
        pre_fix_revision=require_string(value.get("pre_fix_revision"), "task.pre_fix_revision"),
        token_budget=require_int(value.get("token_budget"), "task.token_budget"),
        source_content_allowance=require_int(
            value.get("source_content_allowance"), "task.source_content_allowance"
        ),
        time_anchor=anchor,
        system_instruction=require_string(
            value.get("system_instruction"), "task.system_instruction"
        ),
    )


def load_historical_labels(task_directory: Path, *, repository_id: str) -> HistoricalLabels:
    value = read_json_yaml(task_directory / "evaluator" / "labels.yaml")
    _version(
        value.get("schema_version"),
        expected=CASE_STUDY_LABELS_SCHEMA,
        artifact="HistoricalLabels",
    )
    ground_truth = load_ground_truth(task_directory, repository_id=repository_id)
    return HistoricalLabels(
        fix_revision=require_string(value.get("fix_revision"), "labels.fix_revision"),
        changed_files=require_string_tuple(value.get("changed_files"), "labels.changed_files"),
        ground_truth=ground_truth,
        evidence_url=require_string(value.get("evidence_url"), "labels.evidence_url"),
        evaluator_sentinel=require_string(
            value.get("evaluator_sentinel"), "labels.evaluator_sentinel"
        ),
    )


def load_manual_review(task_directory: Path) -> ManualReview:
    value = read_json_yaml(task_directory / "evaluator" / "review.yaml")
    _version(
        value.get("schema_version"),
        expected=CASE_STUDY_REVIEW_SCHEMA,
        artifact="ManualReview",
    )
    reasons = require_mapping(value.get("span_reasons"), "review.span_reasons")
    if not all(isinstance(item, str) for item in reasons.values()):
        raise SourceValidationError("review.span_reasons values must be strings")
    return ManualReview(
        status=require_string(value.get("status"), "review.status"),
        reviewer=require_string(value.get("reviewer"), "review.reviewer"),
        reviewed_at=require_string(value.get("reviewed_at"), "review.reviewed_at"),
        evidence_basis=require_string(value.get("evidence_basis"), "review.evidence_basis"),
        span_reasons={key: item for key, item in reasons.items() if isinstance(item, str)},
        dependency_reasons=tuple(
            require_string(item, "review.dependency_reason")
            for item in require_sequence(
                value.get("dependency_reasons", ()), "review.dependency_reasons"
            )
        ),
        diversity_tags=require_string_tuple(
            value.get("diversity_tags", ()), "review.diversity_tags"
        ),
        limitations=require_string_tuple(value.get("limitations", ()), "review.limitations"),
    )


def load_case_study_task(task_directory: Path) -> CaseStudyTask:
    public = load_public_case_task(task_directory)
    labels = load_historical_labels(task_directory, repository_id=public.repository_id)
    review = load_manual_review(task_directory)
    return CaseStudyTask(public=public, labels=labels, review=review)
