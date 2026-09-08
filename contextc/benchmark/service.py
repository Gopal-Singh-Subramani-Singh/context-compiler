"""Application services for benchmark runs, reports, and controlled suites."""

from __future__ import annotations

from pathlib import Path

from contextc.errors import ContextCompilerError

from .debug import one_task_debug_report
from .evaluator import evaluate_public_compilation
from .fingerprint import assert_equal_footing
from .labels import load_ground_truth
from .models import BenchmarkRun
from .public import load_public_task
from .runner import compile_public_task
from .storage import BenchmarkStore


def run_task(
    task_directory: Path,
    *,
    strategies: tuple[str, ...],
    store: BenchmarkStore | None = None,
) -> tuple[BenchmarkRun, ...]:
    """Compile all public inputs before evaluator labels are loaded."""

    if not strategies:
        raise ValueError("benchmark run requires at least one strategy")
    task = load_public_task(task_directory)
    compilations = tuple(compile_public_task(task, strategy=strategy) for strategy in strategies)
    labels = load_ground_truth(task_directory, repository_id=task.repository_id)
    runs = tuple(
        evaluate_public_compilation(task, compilation, labels) for compilation in compilations
    )
    assert_equal_footing(runs)
    if store is not None:
        for run in runs:
            store.save_run(run)
    return runs


def debug_task(task_directory: Path, *, strategies: tuple[str, ...]) -> dict[str, object]:
    task = load_public_task(task_directory)
    compilations = tuple(compile_public_task(task, strategy=strategy) for strategy in strategies)
    labels = load_ground_truth(task_directory, repository_id=task.repository_id)
    return one_task_debug_report(task, labels, compilations)


def run_suite(
    suite_directory: Path,
    *,
    strategies: tuple[str, ...],
    store: BenchmarkStore,
) -> tuple[dict[str, object], ...]:
    """Run sorted physical task directories and retain explicit expected failures."""

    reports: list[dict[str, object]] = []
    for task_directory in sorted(path for path in suite_directory.iterdir() if path.is_dir()):
        try:
            runs = run_task(task_directory, strategies=strategies, store=store)
        except (ContextCompilerError, ValueError) as error:
            reports.append(
                {
                    "task": task_directory.name,
                    "status": "infeasible" if "CTX530" in str(error) else "failed",
                    "detail": str(error),
                    "run_ids": (),
                }
            )
        else:
            reports.append(
                {
                    "task": task_directory.name,
                    "status": "completed",
                    "detail": "",
                    "run_ids": tuple(run.run_id for run in runs),
                }
            )
    return tuple(reports)
