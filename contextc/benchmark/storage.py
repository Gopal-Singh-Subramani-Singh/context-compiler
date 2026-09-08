"""Versioned, transactional SQLite persistence for M6 benchmark evidence."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from contextc.canonical import canonical_json_text, to_canonical_primitive
from contextc.errors import SourceValidationError

from .models import BenchmarkRun

SQLITE_SCHEMA_VERSION = 1

_METRIC_NAMES = (
    "required_file_recall",
    "required_file_precision",
    "required_span_recall",
    "dependency_closure_coverage",
    "useful_token_ratio",
    "redundant_token_ratio",
    "unsupported_context_ratio",
    "budget_utilization",
    "compilation_latency_ms",
    "optimizer_runtime_ms",
)


class BenchmarkStore:
    """Store immutable semantic runs; duplicate run IDs are idempotent first-write-wins."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS benchmark_schema (
                    version INTEGER PRIMARY KEY
                );
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    run_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    input_fingerprint TEXT NOT NULL,
                    evaluator_label_identity TEXT NOT NULL,
                    source_revision TEXT,
                    graph_identity TEXT NOT NULL,
                    task_identity TEXT NOT NULL,
                    analysis_identity TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    tokenizer_identity TEXT NOT NULL,
                    configured_budget INTEGER NOT NULL,
                    fixed_overhead_tokens INTEGER NOT NULL,
                    source_allowance_tokens INTEGER NOT NULL,
                    optimizer_status TEXT NOT NULL,
                    rendered_token_count INTEGER NOT NULL,
                    compilation_latency_ms REAL NOT NULL,
                    optimizer_runtime_ms REAL NOT NULL,
                    semantic_json TEXT NOT NULL,
                    top_k_trace_json TEXT
                );
                CREATE TABLE IF NOT EXISTS benchmark_metrics (
                    run_id TEXT NOT NULL REFERENCES benchmark_runs(run_id) ON DELETE CASCADE,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    PRIMARY KEY (run_id, metric_name)
                );
                CREATE TABLE IF NOT EXISTS benchmark_selected_nodes (
                    run_id TEXT NOT NULL REFERENCES benchmark_runs(run_id) ON DELETE CASCADE,
                    rank INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    source_tokens INTEGER NOT NULL,
                    PRIMARY KEY (run_id, rank)
                );
                CREATE TABLE IF NOT EXISTS top_k_candidates (
                    run_id TEXT NOT NULL REFERENCES benchmark_runs(run_id) ON DELETE CASCADE,
                    rank INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    similarity REAL NOT NULL,
                    selected INTEGER NOT NULL,
                    evaluator_overlap_lines INTEGER NOT NULL,
                    PRIMARY KEY (run_id, rank)
                );
                """
            )
            rows = connection.execute("SELECT version FROM benchmark_schema").fetchall()
            versions = {int(row[0]) for row in rows}
            if versions and versions != {SQLITE_SCHEMA_VERSION}:
                raise SourceValidationError(
                    f"unsupported benchmark SQLite schema versions: {sorted(versions)}"
                )
            connection.execute(
                "INSERT OR IGNORE INTO benchmark_schema(version) VALUES (?)",
                (SQLITE_SCHEMA_VERSION,),
            )

    def save_run(self, run: BenchmarkRun) -> bool:
        """Commit one run and normalized evidence atomically; return false for duplicates."""

        self.initialize()
        semantic_json = canonical_json_text(run.semantic_form())
        trace_json = None if run.top_k_trace is None else canonical_json_text(run.top_k_trace)
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT semantic_json FROM benchmark_runs WHERE run_id = ?", (run.run_id,)
            ).fetchone()
            if existing is not None:
                if existing[0] != semantic_json:
                    raise SourceValidationError("duplicate benchmark run ID has different evidence")
                return False
            connection.execute(
                """
                INSERT INTO benchmark_runs VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    run.run_id,
                    run.task_id,
                    run.strategy_id,
                    run.strategy_version,
                    run.input_fingerprint,
                    run.evaluator_label_identity,
                    run.source_revision,
                    run.graph_identity,
                    run.task_identity,
                    run.analysis_identity,
                    run.target_id,
                    run.tokenizer_identity,
                    run.configured_budget,
                    run.fixed_overhead_tokens,
                    run.source_allowance_tokens,
                    run.optimizer_status,
                    run.rendered_token_count,
                    run.metrics.compilation_latency_ms,
                    run.metrics.optimizer_runtime_ms,
                    semantic_json,
                    trace_json,
                ),
            )
            metric_values = to_canonical_primitive(run.metrics)
            if not isinstance(metric_values, dict):
                raise AssertionError("metrics did not canonicalize")
            connection.executemany(
                "INSERT INTO benchmark_metrics VALUES (?, ?, ?)",
                ((run.run_id, name, float(metric_values[name])) for name in _METRIC_NAMES),
            )
            connection.executemany(
                "INSERT INTO benchmark_selected_nodes VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    (
                        run.run_id,
                        item.rank,
                        item.node_id,
                        item.span.source_uri,
                        item.span.start_line,
                        item.span.end_line,
                        item.source_tokens,
                    )
                    for item in run.selected_locations
                ),
            )
            if run.top_k_trace is not None:
                connection.executemany(
                    "INSERT INTO top_k_candidates VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        (
                            run.run_id,
                            item.rank,
                            item.node_id,
                            item.span.source_uri,
                            item.span.start_line,
                            item.span.end_line,
                            item.similarity,
                            int(item.selected),
                            item.evaluator_overlap_lines,
                        )
                        for item in run.top_k_trace.candidates
                    ),
                )
        return True

    def load_run_evidence(self, run_id: str) -> dict[str, object]:
        """Reload inspectable run, metric, selected-node, and Top-K rows."""

        self.initialize()
        with self._connect() as connection:
            run = connection.execute(
                "SELECT * FROM benchmark_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if run is None:
                raise SourceValidationError(f"unknown benchmark run: {run_id}")
            metrics = connection.execute(
                "SELECT metric_name, metric_value FROM benchmark_metrics "
                "WHERE run_id = ? ORDER BY metric_name",
                (run_id,),
            ).fetchall()
            selected = connection.execute(
                "SELECT * FROM benchmark_selected_nodes WHERE run_id = ? ORDER BY rank",
                (run_id,),
            ).fetchall()
            candidates = connection.execute(
                "SELECT * FROM top_k_candidates WHERE run_id = ? ORDER BY rank",
                (run_id,),
            ).fetchall()
        return {
            "run": dict(run),
            "semantic": json.loads(run["semantic_json"]),
            "metrics": {row["metric_name"]: row["metric_value"] for row in metrics},
            "selected_nodes": tuple(dict(row) for row in selected),
            "top_k_candidates": tuple(dict(row) for row in candidates),
            "top_k_trace": (
                None if run["top_k_trace_json"] is None else json.loads(run["top_k_trace_json"])
            ),
        }

    def list_runs(self) -> tuple[dict[str, object], ...]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT run_id, task_id, strategy_id, optimizer_status "
                "FROM benchmark_runs ORDER BY task_id, strategy_id, run_id"
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def raw_metric_rows(self) -> tuple[dict[str, object], ...]:
        """Return one non-aggregated row per stored task/strategy run."""

        rows = []
        for summary in self.list_runs():
            evidence = self.load_run_evidence(str(summary["run_id"]))
            semantic = evidence["semantic"]
            if not isinstance(semantic, dict):
                raise AssertionError("stored semantic benchmark evidence is not an object")
            metadata = semantic.get("metadata")
            if not isinstance(metadata, dict):
                raise AssertionError("stored benchmark metadata is not an object")
            metrics = evidence["metrics"]
            if not isinstance(metrics, dict):
                raise AssertionError("stored benchmark metrics are not an object")
            rows.append(
                {
                    "run_id": summary["run_id"],
                    "task_id": summary["task_id"],
                    "strategy_requested": metadata.get("requested_strategy"),
                    "strategy_used": summary["strategy_id"],
                    "optimizer_status": summary["optimizer_status"],
                    **metrics,
                }
            )
        return tuple(rows)
