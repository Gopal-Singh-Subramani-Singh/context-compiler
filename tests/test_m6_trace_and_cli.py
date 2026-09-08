from __future__ import annotations

import json
from pathlib import Path

import contextc
from contextc.benchmark import GroundTruth, SourceSpan
from contextc.benchmark.storage import BenchmarkStore
from contextc.benchmark.trace import attach_evaluator_overlap, record_top_k_trace
from contextc.cli.main import main


def controlled_task(name: str) -> Path:
    return Path(contextc.__file__).parent / "resources" / "benchmarks" / "controlled" / name


def test_retrieval_trace_gets_evaluator_overlap_only_afterward() -> None:
    useful = SourceSpan("repo://fixture/auth.py", 2, 3)
    distractor = SourceSpan("repo://fixture/noise.py", 1, 2)
    trace = record_top_k_trace(
        query_text="authorize payment",
        embedding_model_id="local-model",
        embedding_model_version="1.0.0",
        embedding_revision="sha256:revision",
        candidates=(
            ("auth", SourceSpan("repo://fixture/auth.py", 1, 3), 0.9, True),
            ("noise", distractor, 0.2, False),
        ),
        selected_node_ids=("auth",),
        removed_node_ids=(),
    )
    assert [item.evaluator_overlap_lines for item in trace.candidates] == [0, 0]
    annotated = attach_evaluator_overlap(trace, GroundTruth(required_spans=(useful,)))
    assert [item.evaluator_overlap_lines for item in annotated.candidates] == [2, 0]
    assert trace.candidates[0].evaluator_overlap_lines == 0


def test_benchmark_debug_cli_emits_span_alignment(capsys) -> None:  # type: ignore[no-untyped-def]
    exit_code = main(
        [
            "benchmark",
            "debug",
            str(controlled_task("01_direct_file")),
            "--strategy",
            "density_greedy",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["expected_source_uris"] == ["repo://direct-file/auth.py"]
    assert output["expected_node_ids_debug_only"] == ["legacy-auth-node"]


def test_benchmark_run_and_inspect_cli_persist_top_k_trace(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "benchmark.sqlite3"
    exit_code = main(
        [
            "benchmark",
            "run",
            str(controlled_task("01_direct_file")),
            "--database",
            str(database),
            "--strategy",
            "top_k",
        ]
    )
    run_output = json.loads(capsys.readouterr().out)
    run_id = run_output["runs"][0]["run_id"]
    assert exit_code == 0
    assert main(["benchmark", "inspect", str(database), "--run-id", run_id]) == 0
    evidence = json.loads(capsys.readouterr().out)
    assert evidence["top_k_trace"]["status"] == "fallback"
    assert evidence["top_k_candidates"] == []
    assert BenchmarkStore(database).list_runs()[0]["run_id"] == run_id
    assert main(["benchmark", "report", str(database)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["rows"][0]["strategy_requested"] == "top_k"
    assert "required_span_recall" in report["rows"][0]
