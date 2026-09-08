from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from contextc.benchmark import calculate_raw_metrics
from contextc.benchmark.storage import BenchmarkStore
from contextc.case_study import (
    HistoricalRepository,
    list_task_directories,
    load_case_study_task,
    load_public_case_task,
    run_case_task,
    validate_suite,
    validate_task,
    verify_task_determinism,
)
from contextc.case_study.case_metrics import calculate_case_metrics
from contextc.case_study.extract_labels import extract_label_candidates
from contextc.case_study.reporting import build_report, report_markdown
from contextc.errors import SourceValidationError


def task_directory(name: str) -> Path:
    return next(path for path in list_task_directories() if path.name == name)


def test_real_repository_and_all_eight_historical_tasks_validate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    repository = HistoricalRepository()
    repository.validate_reference()
    validations = validate_suite(repository=repository)
    assert len(validations) == 8
    assert all(item.valid and item.bundle_unchanged for item in validations)
    assert sum(item.required_dependencies > 0 for item in validations) == 2
    tags = {tag for item in validations for tag in item.diversity_tags}
    assert {"tight_budget", "large_relevant_function", "distractor_heavy"} <= tags
    assert repository.source_metadata["license"] == "MIT"


def test_public_loader_succeeds_without_evaluator_and_cannot_see_sentinel(
    tmp_path: Path,
) -> None:
    source = task_directory("01_nonfinite_naturaldelta")
    isolated = tmp_path / "task"
    shutil.copytree(source / "public", isolated / "public")
    public = load_public_case_task(isolated)
    assert public.task_id == "humanize-nonfinite-naturaldelta"
    assert not (isolated / "evaluator").exists()
    sentinel = json.loads((source / "evaluator" / "labels.yaml").read_text())["evaluator_sentinel"]
    assert sentinel not in repr(public)


def test_materialization_is_exact_reordered_and_does_not_mutate_bundle() -> None:
    repository = HistoricalRepository()
    task = load_case_study_task(task_directory("06_empty_natural_list"))
    before = repository.bundle_identity
    with repository.materialize(task.public.pre_fix_revision) as checkout:
        head = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=checkout,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        canonical_content = (checkout / "src/humanize/lists.py").read_bytes()
    with repository.materialize(
        task.public.pre_fix_revision, reverse_creation_order=True
    ) as reordered:
        assert not (reordered / ".git").exists()
        assert (reordered / "src/humanize/lists.py").read_bytes() == canonical_content
    assert head == task.public.pre_fix_revision
    assert repository.bundle_identity == before


def test_label_extraction_is_review_only_and_uses_real_fix_diff() -> None:
    evidence = extract_label_candidates(task_directory("06_empty_natural_list"))
    assert evidence["approval_required"] is True
    assert evidence["writes_ground_truth"] is False
    assert evidence["changed_files"] == (
        "src/humanize/lists.py",
        "tests/test_lists.py",
    )
    assert "natural_list" in str(evidence["patch"])


def test_m11_reuses_m6_metric_function_unchanged() -> None:
    assert calculate_case_metrics is calculate_raw_metrics


def test_validation_rejects_missing_manual_evidence(tmp_path: Path) -> None:
    source = task_directory("06_empty_natural_list")
    copied = tmp_path / "task"
    shutil.copytree(source, copied)
    (copied / "evaluator" / "review.yaml").unlink()
    with pytest.raises(SourceValidationError, match="invalid benchmark record"):
        validate_task(copied)


def test_tight_budget_and_dependency_sensitive_behavior(tmp_path: Path) -> None:
    store = BenchmarkStore(tmp_path / "case.sqlite3")
    tight = run_case_task(
        task_directory("03_naturalsize_unit_rollover"),
        strategies=("relevance_greedy", "density_greedy"),
        store=store,
    )
    relevant, density = tight.runs
    assert relevant.metrics.required_span_recall == 1.0
    assert density.metrics.required_span_recall == 0.0
    assert all(run.metrics.budget_utilization <= 1.0 for run in tight.runs)

    dependency = run_case_task(
        task_directory("07_timezone_aware_naturaldate"),
        strategies=("relevance_greedy",),
        store=store,
    )
    assert dependency.runs[0].metrics.dependency_closure_coverage == 1.0
    assert dependency.evaluator_sentinel_absent
    assert dependency.reference_bundle_unchanged

    report = build_report(store.path)
    rendered = report_markdown(report)
    assert len(report["raw_rows"]) == 3
    assert "## Raw results" in rendered
    assert "statistically significant" in rendered


def test_repeated_and_reordered_execution_is_semantically_identical() -> None:
    report = verify_task_determinism(
        task_directory("06_empty_natural_list"),
        strategies=("relevance_greedy", "density_greedy"),
    )
    assert report.repeated_semantics_identical
    assert report.reversed_materialization_identical
    assert len(report.run_ids) == 2
