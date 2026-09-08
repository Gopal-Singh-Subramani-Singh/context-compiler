"""Historical-evidence validation and task-diversity checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from contextc.benchmark.source import SourceSpan
from contextc.errors import SourceValidationError

from .loader import list_task_directories, load_case_study_task
from .repository import HistoricalRepository


def _span_key(span: SourceSpan) -> str:
    return f"{span.source_uri}:{span.start_line}-{span.end_line}"


def _relative_path(span: SourceSpan, repository_id: str) -> Path:
    parsed = urlsplit(span.source_uri)
    if parsed.scheme != "repo" or parsed.netloc != repository_id:
        raise SourceValidationError(
            f"ground-truth source must use repo://{repository_id}/: {span.source_uri}"
        )
    return Path(parsed.path.removeprefix("/"))


@dataclass(frozen=True, slots=True)
class TaskValidation:
    task_id: str
    valid: bool
    required_spans: int
    accepted_spans: int
    required_dependencies: int
    diversity_tags: tuple[str, ...]
    bundle_unchanged: bool


def validate_task(
    task_directory: Path, repository: HistoricalRepository | None = None
) -> TaskValidation:
    source = repository or HistoricalRepository()
    task = load_case_study_task(task_directory)
    public, labels, review = task.public, task.labels, task.review
    if public.repository_id != source.repository_id:
        raise SourceValidationError("task repository does not match packaged historical source")
    if source.commit_parent(labels.fix_revision) != public.pre_fix_revision:
        raise SourceValidationError("pre-fix revision is not the single parent of the fix")
    actual_changed = source.changed_files(public.pre_fix_revision, labels.fix_revision)
    if actual_changed != labels.changed_files:
        raise SourceValidationError(
            f"historical changed-file evidence differs: actual={actual_changed}, "
            f"recorded={labels.changed_files}"
        )
    if not labels.evidence_url.endswith(labels.fix_revision):
        raise SourceValidationError("fix evidence URL must identify the exact fix revision")
    public_bytes = b"".join(
        path.read_bytes()
        for path in sorted((task_directory / "public").rglob("*"))
        if path.is_file()
    )
    if labels.evaluator_sentinel.encode() in public_bytes:
        raise SourceValidationError("evaluator sentinel leaked into public task input")

    truth = labels.ground_truth
    useful_spans = truth.useful_spans
    expected_reason_keys = {_span_key(span) for span in useful_spans}
    if set(review.span_reasons) != expected_reason_keys:
        raise SourceValidationError("manual-review reasons must cover every useful span exactly")
    if len(review.dependency_reasons) != len(truth.required_dependencies):
        raise SourceValidationError("manual-review dependency reasons are incomplete")

    bundle_before = source.bundle_identity
    with source.materialize(public.pre_fix_revision) as checkout:
        for span in useful_spans:
            relative = _relative_path(span, public.repository_id)
            path = checkout / relative
            if not path.is_file():
                raise SourceValidationError(f"ground-truth source is absent pre-fix: {relative}")
            line_count = max(1, len(path.read_text(encoding="utf-8").splitlines()))
            if span.end_line > line_count:
                raise SourceValidationError(
                    f"ground-truth span exceeds pre-fix source: {_span_key(span)}"
                )
            if relative.as_posix() not in labels.changed_files:
                raise SourceValidationError(
                    f"ground-truth span is not justified by the fix diff: {relative}"
                )
    return TaskValidation(
        task_id=public.task_id,
        valid=True,
        required_spans=len(truth.required_spans),
        accepted_spans=len(truth.accepted_spans),
        required_dependencies=len(truth.required_dependencies),
        diversity_tags=review.diversity_tags,
        bundle_unchanged=source.bundle_identity == bundle_before,
    )


def validate_suite(
    root: Path | None = None, repository: HistoricalRepository | None = None
) -> tuple[TaskValidation, ...]:
    source = repository or HistoricalRepository()
    validations = tuple(validate_task(path, source) for path in list_task_directories(root))
    tags = [tag for result in validations for tag in result.diversity_tags]
    dependency_tasks = sum(result.required_dependencies > 0 for result in validations)
    if len(validations) < 5:
        raise SourceValidationError("M11 requires at least five historical tasks")
    if dependency_tasks < 2:
        raise SourceValidationError("M11 requires at least two dependency-sensitive tasks")
    for required_tag in ("tight_budget", "large_relevant_function", "distractor_heavy"):
        if required_tag not in tags:
            raise SourceValidationError(f"M11 task diversity is missing {required_tag}")
    return validations
