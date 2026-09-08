from __future__ import annotations

import json
from pathlib import Path

import contextc
from contextc.benchmark.service import debug_task, run_suite, run_task
from contextc.benchmark.storage import BenchmarkStore


def controlled_suite() -> Path:
    return Path(contextc.__file__).parent / "resources" / "benchmarks" / "controlled"


def test_controlled_suite_has_eight_physical_public_evaluator_boundaries() -> None:
    tasks = sorted(path for path in controlled_suite().iterdir() if path.is_dir())
    assert len(tasks) == 8
    for task in tasks:
        assert (task / "public" / "task.yaml").is_file()
        assert (task / "evaluator" / "labels.yaml").is_file()
        assert (task / "repository").is_dir()


def test_controlled_suite_produces_sensible_raw_runs_and_explicit_infeasibility(
    tmp_path: Path,
) -> None:
    store = BenchmarkStore(tmp_path / "controlled.sqlite3")
    reports = run_suite(
        controlled_suite(),
        strategies=("naive", "density_greedy", "brute_force"),
        store=store,
    )
    assert len(reports) == 8
    assert [item["status"] for item in reports].count("completed") == 7
    infeasible = next(item for item in reports if item["task"] == "08_infeasible_mandatory")
    assert infeasible["status"] == "infeasible"
    assert "CTX530" in str(infeasible["detail"])
    stored = store.list_runs()
    assert len(stored) == 21
    for row in stored:
        evidence = store.load_run_evidence(str(row["run_id"]))
        metrics = evidence["metrics"]
        for name in (
            "required_file_recall",
            "required_file_precision",
            "required_span_recall",
            "dependency_closure_coverage",
            "useful_token_ratio",
            "redundant_token_ratio",
            "unsupported_context_ratio",
            "budget_utilization",
        ):
            assert 0.0 <= metrics[name] <= 1.0  # type: ignore[index]


def test_one_task_debug_report_diagnoses_stale_id_but_span_match() -> None:
    task = controlled_suite() / "01_direct_file"
    report = debug_task(task, strategies=("density_greedy",))
    assert report["expected_node_ids_debug_only"] == ("legacy-auth-node",)
    assert "legacy-auth-node" not in report["actual_ir_ids"]
    assert report["expected_source_uris"] == ["repo://direct-file/auth.py"]
    actual_uris = {
        item["source_uri"]
        for item in report["actual_normalized_locations"]  # type: ignore[union-attr]
    }
    assert "repo://direct-file/auth.py" in actual_uris


def test_raw_cross_strategy_task_table_keeps_each_result(tmp_path: Path) -> None:
    task = controlled_suite() / "03_distractor_heavy"
    runs = run_task(
        task,
        strategies=("naive", "recency", "density_greedy", "brute_force", "top_k"),
        store=BenchmarkStore(tmp_path / "table.sqlite3"),
    )
    assert len(runs) == 5
    assert len({run.input_fingerprint for run in runs}) == 1
    assert {run.metadata["requested_strategy"] for run in runs} == {
        "naive",
        "recency",
        "density_greedy",
        "brute_force",
        "top_k",
    }
    assert all(run.metrics.required_file_recall >= 0.0 for run in runs)


def test_manually_reviewed_direct_task_matches_predeclared_metrics() -> None:
    task = controlled_suite() / "01_direct_file"
    expected = json.loads(
        (task / "evaluator" / "expected_metrics.json").read_text(encoding="utf-8")
    )
    run = run_task(task, strategies=(str(expected.pop("strategy")),))[0]
    actual = {name: getattr(run.metrics, name) for name in expected}
    assert actual == expected
