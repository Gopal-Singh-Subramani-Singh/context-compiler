"""Raw historical result reports with bounded, non-universal conclusions."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from contextc.benchmark.storage import BenchmarkStore
from contextc.errors import SourceValidationError
from contextc.schema import CASE_STUDY_REPORT_SCHEMA

from .baselines import strategy_means
from .loader import list_task_directories, load_case_study_task
from .repository import HistoricalRepository


def build_report(database: Path, *, tasks_root: Path | None = None) -> dict[str, object]:
    rows = BenchmarkStore(database).raw_metric_rows()
    if not rows:
        raise SourceValidationError("case-study report database contains no runs")
    tasks = tuple(load_case_study_task(path) for path in list_task_directories(tasks_root))
    source = HistoricalRepository().source_metadata
    return {
        "schema_version": CASE_STUDY_REPORT_SCHEMA,
        "repository": source,
        "task_count": len(tasks),
        "tasks": tuple(
            {
                "task_id": task.public.task_id,
                "description": task.public.description,
                "pre_fix_revision": task.public.pre_fix_revision,
                "fix_revision": task.labels.fix_revision,
                "manual_review_status": task.review.status,
                "diversity_tags": task.review.diversity_tags,
            }
            for task in tasks
        ),
        "raw_rows": rows,
        "descriptive_strategy_means": strategy_means(rows),
        "limitations": (
            "Eight tasks from one small Python repository are not statistically significant.",
            "Lexical analysis and this bounded task set do not establish universal "
            "strategy superiority.",
            "Latency is machine-dependent operational evidence.",
        ),
    }


def report_markdown(report: Mapping[str, object]) -> str:
    repository = report.get("repository")
    source = repository if isinstance(repository, Mapping) else {}
    lines = [
        "# Context Compiler M11 Case-Study Report",
        "",
        f"Repository: {source.get('upstream', 'unknown')}",
        f"License: {source.get('license', 'unknown')}",
        f"Historical tasks: {report.get('task_count', 0)}",
        "",
        "## Raw results",
        "",
        "| Task | Requested | Used | Status | File recall | File precision | Span recall | "
        "Dependency coverage | Useful ratio | Unsupported ratio | Budget | Compile ms | "
        "Optimizer ms |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    raw_rows = report.get("raw_rows")
    if isinstance(raw_rows, (tuple, list)):
        for raw in raw_rows:
            if not isinstance(raw, Mapping):
                continue
            lines.append(
                "| {task_id} | {strategy_requested} | {strategy_used} | {optimizer_status} | "
                "{required_file_recall:.3f} | {required_file_precision:.3f} | "
                "{required_span_recall:.3f} | {dependency_closure_coverage:.3f} | "
                "{useful_token_ratio:.3f} | {unsupported_context_ratio:.3f} | "
                "{budget_utilization:.3f} | {compilation_latency_ms:.3f} | "
                "{optimizer_runtime_ms:.3f} |".format(**raw)
            )
    lines.extend(
        (
            "",
            "## Limits",
            "",
            "This is a bounded historical case study, not a statistically significant "
            "claim or a universal ranking of retrieval strategies.",
            "",
        )
    )
    return "\n".join(lines)
