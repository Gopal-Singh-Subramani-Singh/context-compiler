"""Sealed public compilation followed by evaluator-only historical scoring."""

from __future__ import annotations

from pathlib import Path

from contextc.benchmark.evaluator import evaluate_public_compilation
from contextc.benchmark.fingerprint import assert_equal_footing
from contextc.benchmark.public import PublicBenchmarkTask
from contextc.benchmark.runner import PublicCompilation, compile_public_tasks
from contextc.benchmark.storage import BenchmarkStore
from contextc.errors import SourceValidationError

from .loader import (
    list_task_directories,
    load_historical_labels,
    load_manual_review,
    load_public_case_task,
)
from .repository import HistoricalRepository
from .schemas import CaseStudyExecution, CaseStudyTask, DeterminismReport
from .strategies import normalized_strategies


def _benchmark_task(public: object, repository: Path) -> PublicBenchmarkTask:
    from .schemas import CaseStudyPublicTask

    if not isinstance(public, CaseStudyPublicTask):
        raise TypeError("public case-study task has an unexpected type")
    return PublicBenchmarkTask(
        task_id=public.task_id,
        repository_id=public.repository_id,
        repository=repository,
        description=public.description,
        token_budget=public.token_budget,
        time_anchor=public.time_anchor,
        source_revision=public.pre_fix_revision,
        source_content_allowance=public.source_content_allowance,
        system_instruction=public.system_instruction,
    )


def run_case_task(
    task_directory: Path,
    *,
    strategies: tuple[str, ...] = (),
    store: BenchmarkStore | None = None,
    repository: HistoricalRepository | None = None,
    reverse_creation_order: bool = False,
) -> CaseStudyExecution:
    """Compile every strategy before opening any evaluator-side task file."""

    selected_strategies = normalized_strategies(strategies)
    source = repository or HistoricalRepository()
    public = load_public_case_task(task_directory)
    bundle_before = source.bundle_identity
    with source.materialize(
        public.pre_fix_revision,
        reverse_creation_order=reverse_creation_order,
    ) as checkout:
        benchmark_task = _benchmark_task(public, checkout)
        compilations: tuple[PublicCompilation, ...] = compile_public_tasks(
            benchmark_task,
            strategies=selected_strategies,
        )

        # Evaluator files are first opened only after every compilation is sealed.
        labels = load_historical_labels(task_directory, repository_id=public.repository_id)
        review = load_manual_review(task_directory)
        runs = tuple(
            evaluate_public_compilation(benchmark_task, compilation, labels.ground_truth)
            for compilation in compilations
        )
        visible_surface = "\n".join(
            (
                repr(public),
                *(repr(compilation.request) for compilation in compilations),
                *(repr(compilation.result) for compilation in compilations),
                *(compilation.result.rendered.rendered_text for compilation in compilations),
            )
        )

    assert_equal_footing(runs)
    sentinel_absent = labels.evaluator_sentinel not in visible_surface
    if not sentinel_absent:
        raise SourceValidationError("evaluator sentinel entered compiler-visible evidence")
    if store is not None:
        for run in runs:
            store.save_run(run)
    return CaseStudyExecution(
        task=CaseStudyTask(public=public, labels=labels, review=review),
        runs=runs,
        reference_bundle_unchanged=source.bundle_identity == bundle_before,
        evaluator_sentinel_absent=sentinel_absent,
    )


def run_case_suite(
    *,
    strategies: tuple[str, ...] = (),
    store: BenchmarkStore | None = None,
    tasks_root: Path | None = None,
    repository: HistoricalRepository | None = None,
) -> tuple[CaseStudyExecution, ...]:
    source = repository or HistoricalRepository()
    return tuple(
        run_case_task(
            task_directory,
            strategies=strategies,
            store=store,
            repository=source,
        )
        for task_directory in list_task_directories(tasks_root)
    )


def _semantics(execution: CaseStudyExecution) -> tuple[dict[str, object], ...]:
    return tuple(run.semantic_form() for run in execution.runs)


def verify_task_determinism(
    task_directory: Path,
    *,
    strategies: tuple[str, ...] = (),
    repository: HistoricalRepository | None = None,
) -> DeterminismReport:
    source = repository or HistoricalRepository()
    first = run_case_task(task_directory, strategies=strategies, repository=source)
    repeated = run_case_task(task_directory, strategies=strategies, repository=source)
    reversed_order = run_case_task(
        task_directory,
        strategies=strategies,
        repository=source,
        reverse_creation_order=True,
    )
    selected = normalized_strategies(strategies)
    return DeterminismReport(
        task_id=first.task.public.task_id,
        strategies=selected,
        repeated_semantics_identical=_semantics(first) == _semantics(repeated),
        reversed_materialization_identical=_semantics(first) == _semantics(reversed_order),
        run_ids=tuple(run.run_id for run in first.runs),
    )
