from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

import contextc.benchmark.runner as public_runner
from contextc.application.compile import compile_repository_to_path
from contextc.benchmark.debug import one_task_debug_report
from contextc.benchmark.evaluator import evaluate_public_compilation
from contextc.benchmark.fingerprint import assert_equal_footing
from contextc.benchmark.labels import load_ground_truth
from contextc.benchmark.public import load_public_task
from contextc.benchmark.runner import compile_public_task
from contextc.benchmark.storage import SQLITE_SCHEMA_VERSION, BenchmarkStore
from contextc.canonical import canonical_json_text, to_canonical_primitive
from contextc.errors import SourceValidationError
from contextc.explanation import explain_node
from contextc.reproduction.transaction import default_manifest_path

SENTINEL = "EVALUATOR_ONLY_SENTINEL_8f48c7"


def task_directory(tmp_path: Path, *, include_labels: bool = True) -> Path:
    root = tmp_path / "task"
    (root / "public").mkdir(parents=True)
    (root / "evaluator").mkdir()
    (root / "repository").mkdir()
    (root / "repository" / "auth.py").write_text(
        "def authorize(amount: int) -> bool:\n    return amount < 100\n",
        encoding="utf-8",
    )
    (root / "repository" / "noise.md").write_text(
        "Unrelated deployment rotation notes.\n", encoding="utf-8"
    )
    public = {
        "task_id": "authorization",
        "repository_id": "fixture",
        "repository": "repository",
        "description": "Explain authorize payment",
        "token_budget": 500,
        "source_content_allowance": 180,
        "source_revision": "fixture-v1",
        "time_anchor": "2026-09-02T00:00:00Z",
        "system_instruction": "Use repository evidence.",
    }
    (root / "public" / "task.yaml").write_text(json.dumps(public), encoding="utf-8")
    if include_labels:
        labels = {
            "required_spans": [
                {"source_uri": "repo://fixture/auth.py", "start_line": 1, "end_line": 2}
            ],
            "accepted_spans": [],
            "required_dependencies": [],
            "debug_expected_node_ids": ["stale-debug-id"],
            "evaluator_sentinel": SENTINEL,
        }
        (root / "evaluator" / "labels.yaml").write_text(json.dumps(labels), encoding="utf-8")
    return root


def test_public_compilation_runs_without_evaluator_files(tmp_path: Path) -> None:
    root = task_directory(tmp_path, include_labels=False)
    task = load_public_task(root)
    compilation = compile_public_task(task, strategy="density_greedy")
    assert compilation.result.rendered.ordered_node_ids
    assert "GroundTruth" not in vars(public_runner)
    assert "load_ground_truth" not in vars(public_runner)


def test_evaluator_sentinel_is_absent_from_every_compiler_visible_surface(
    tmp_path: Path,
) -> None:
    root = task_directory(tmp_path)
    task = load_public_task(root)
    compilation = compile_public_task(task, strategy="top_k")
    labels = load_ground_truth(root, repository_id=task.repository_id)
    run = evaluate_public_compilation(task, compilation, labels)
    result = compilation.result
    artifact = tmp_path / "public-only-context.txt"
    compiled_to_path = compile_repository_to_path(compilation.request, artifact)
    manifest = default_manifest_path(artifact)
    selected_id = compiled_to_path.selection.selected_node_ids[0]
    explanation = explain_node(
        node_id=selected_id,
        graph=compiled_to_path.graph,
        analyses={item.node_id: item for item in compiled_to_path.analyses},
        selection=compiled_to_path.selection,
        tokenizer_id=compiled_to_path.rendered.tokenizer_identity.tokenizer_id,
    )
    compiler_surfaces = (
        task.description,
        canonical_json_text(result.graph.to_dict()),
        canonical_json_text(result.analyses),
        canonical_json_text(result.selection.to_dict()),
        result.rendered.rendered_text,
        canonical_json_text(result.rendered.diagnostics),
        canonical_json_text(compilation.request.optimizer),
        run.top_k_trace.query_text if run.top_k_trace else "",
        artifact.read_text(encoding="utf-8"),
        manifest.read_text(encoding="utf-8"),
        canonical_json_text(explanation),
        result.graph.semantic_identity,
    )
    assert labels.evaluator_sentinel == SENTINEL
    assert all(SENTINEL not in surface for surface in compiler_surfaces)
    assert run.evaluator_label_identity == labels.label_identity
    assert SENTINEL not in run.evaluator_label_identity
    assert run.top_k_trace is not None
    assert run.top_k_trace.status == "fallback"
    assert run.top_k_trace.candidates == ()


def test_equal_footing_ignores_only_strategy_identity_and_rejects_mismatch(
    tmp_path: Path,
) -> None:
    root = task_directory(tmp_path)
    task = load_public_task(root)
    labels = load_ground_truth(root, repository_id=task.repository_id)
    runs = tuple(
        evaluate_public_compilation(task, compile_public_task(task, strategy=strategy), labels)
        for strategy in ("naive", "density_greedy", "brute_force")
    )
    assert_equal_footing(runs)
    assert len({run.input_fingerprint for run in runs}) == 1
    with pytest.raises(SourceValidationError, match="not equal-footing"):
        mismatched = replace(runs[0], input_fingerprint="sha256:bad", run_id="")
        assert_equal_footing((*runs, mismatched))


def test_debug_report_exposes_ids_but_uses_canonical_spans_as_labels(tmp_path: Path) -> None:
    root = task_directory(tmp_path)
    task = load_public_task(root)
    labels = load_ground_truth(root, repository_id=task.repository_id)
    first = compile_public_task(task, strategy="naive")
    second = compile_public_task(task, strategy="density_greedy")
    report = one_task_debug_report(task, labels, (first, second))
    assert report["task_description"] == task.description
    assert report["expected_node_ids_debug_only"] == ("stale-debug-id",)
    assert report["expected_source_uris"] == ["repo://fixture/auth.py"]
    assert set(report["selected_by_strategy"]) == {"naive", "density_greedy"}  # type: ignore[arg-type]
    assert all(
        item["source_uri"].startswith("repo://fixture/")
        for item in report["actual_normalized_locations"]  # type: ignore[union-attr]
    )


def test_sqlite_round_trip_is_transactional_versioned_and_idempotent(tmp_path: Path) -> None:
    root = task_directory(tmp_path)
    task = load_public_task(root)
    labels = load_ground_truth(root, repository_id=task.repository_id)
    run = evaluate_public_compilation(task, compile_public_task(task, strategy="top_k"), labels)
    store = BenchmarkStore(tmp_path / "evidence" / "benchmark.sqlite3")
    assert store.save_run(run) is True
    assert (
        store.save_run(replace(run, metrics=replace(run.metrics, compilation_latency_ms=999)))
        is False
    )

    loaded = store.load_run_evidence(run.run_id)
    assert loaded["semantic"] == to_canonical_primitive(run.semantic_form())
    assert loaded["metrics"]["required_file_recall"] == 1.0  # type: ignore[index]
    assert len(loaded["selected_nodes"]) == len(run.selected_locations)  # type: ignore[arg-type]
    assert loaded["top_k_candidates"] == ()
    assert loaded["top_k_trace"]["status"] == "fallback"  # type: ignore[index]
    assert store.list_runs()[0]["run_id"] == run.run_id
    assert SENTINEL.encode() not in store.path.read_bytes()

    import sqlite3

    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT version FROM benchmark_schema").fetchone() == (
            SQLITE_SCHEMA_VERSION,
        )
