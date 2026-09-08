from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from contextc.application.compile import (
    CompileRepositoryRequest,
    compile_repository_target,
    compile_repository_to_path,
    pipeline_configuration_identity,
)
from contextc.cli.main import main
from contextc.explanation import explain_node
from contextc.optimization.models import ObjectiveWeights, OptimizerConfiguration
from contextc.reproduction import read_build_manifest, rebuild_build, stored_build_evidence
from contextc.reproduction.transaction import default_manifest_path
from contextc.targets import TargetId
from contextc.tokenizers import GenericTokenizer


def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    (root / "main.py").write_text(
        "from helper import stable_value\n\n"
        "def explain_optimizer() -> int:\n"
        "    return stable_value()\n"
    )
    (root / "helper.py").write_text("def stable_value() -> int:\n    return 7\n")
    (root / "notes.md").write_text("# Optimizer\nDeterministic selection evidence.\n")
    return root


def request(root: Path, *, strategy: str = "density_greedy") -> CompileRepositoryRequest:
    return CompileRepositoryRequest(
        repository=root,
        task="explain deterministic optimizer selection",
        target_id=TargetId.GENERIC,
        token_budget=600,
        time_anchor=datetime(2026, 8, 31, tzinfo=UTC),
        source_revision="m5-fixture-v1",
        optimizer=OptimizerConfiguration(requested_strategy=strategy),
        system_instruction="Use only stored evidence.",
    )


def test_manifest_records_complete_optimizer_evidence_and_rebuilds(tmp_path: Path) -> None:
    root = repository(tmp_path)
    output = tmp_path / "build" / "context.txt"
    result = compile_repository_to_path(request(root), output)
    manifest_path = default_manifest_path(output)
    manifest = read_build_manifest(manifest_path)

    assert manifest.optimizer_requested == "density_greedy"
    assert manifest.optimizer_used == "density_greedy"
    assert manifest.optimizer_status == "heuristic"
    assert manifest.optimizer_objective == result.selection.objective_value
    assert manifest.optimizer_runtime_ms >= 0
    assert manifest.optimizer_timeout_ms is None
    assert manifest.optimizer_timed_out is False
    assert manifest.optimizer_selected_node_ids == result.selection.selected_node_ids
    assert manifest.tie_break_trace == result.selection.tie_break_trace
    stored_optimizer = manifest.build_inputs["optimizer_configuration"]
    assert OptimizerConfiguration.from_dict(stored_optimizer) == request(root).optimizer  # type: ignore[arg-type]

    rebuilt = rebuild_build(
        manifest_path,
        output_path=tmp_path / "rebuilt" / "context.txt",
    )
    rebuilt_manifest = read_build_manifest(rebuilt.manifest_path)
    assert rebuilt.artifact_path.read_bytes() == output.read_bytes()
    assert rebuilt.build_id == manifest.build_id
    assert rebuilt_manifest.semantic_form() == manifest.semantic_form()


def test_stored_and_node_explanations_answer_m5_optimizer_questions(tmp_path: Path) -> None:
    root = repository(tmp_path)
    output = tmp_path / "build" / "context.txt"
    result = compile_repository_to_path(request(root, strategy="brute_force"), output)
    manifest_path = default_manifest_path(output)
    stored = stored_build_evidence(manifest_path)
    assert stored["optimizer_requested"] == "brute_force"
    assert stored["optimizer_used"] == "brute_force"
    assert stored["optimizer_status"] == "optimal"
    assert stored["optimizer_objective"] == result.selection.objective_value
    assert stored["optimizer_selected_node_ids"] == result.selection.selected_node_ids
    assert stored["optimality_proven"] is True
    assert stored["strategy_heuristic"] is False
    assert stored["exact_solver_timed_out"] is False
    assert stored["fallback_used"] is False

    selected = result.selection.selected_node_ids[0]
    explanation = explain_node(
        node_id=selected,
        graph=result.graph,
        analyses={analysis.node_id: analysis for analysis in result.analyses},
        selection=result.selection,
        tokenizer_id=result.rendered.tokenizer_identity.tokenizer_id,
    )
    assert explanation.evidence["optimality_proven"] is True
    assert explanation.evidence["heuristic"] is False
    assert explanation.evidence["timed_out"] is False
    assert explanation.evidence["optimizer_requested"] == "brute_force"


def test_optimizer_configuration_enters_pipeline_identity(tmp_path: Path) -> None:
    root = repository(tmp_path)
    first = request(root)
    second = CompileRepositoryRequest(
        repository=root,
        task=first.task,
        target_id=first.target_id,
        token_budget=first.token_budget,
        time_anchor=first.time_anchor,
        optimizer=OptimizerConfiguration(
            requested_strategy="density_greedy",
            objective_weights=ObjectiveWeights(relevance=2.0),
        ),
    )
    identity = GenericTokenizer().identity
    assert pipeline_configuration_identity(first, identity) != pipeline_configuration_identity(
        second, identity
    )


def test_cli_selects_requested_strategy_and_prints_honest_status(
    tmp_path: Path, capsys: object
) -> None:
    root = repository(tmp_path)
    output = tmp_path / "cli" / "context.txt"
    exit_code = main(
        [
            "compile",
            str(root),
            "--task",
            "explain optimizer",
            "--target",
            "generic",
            "--token-budget",
            "600",
            "--optimizer",
            "naive",
            "--time-anchor",
            "2026-08-31T00:00:00Z",
            "--output",
            str(output),
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "optimizer: naive -> naive (heuristic)" in captured.out
    assert read_build_manifest(default_manifest_path(output)).optimizer_requested == "naive"


def test_compilation_reserves_exact_target_overhead_before_selection(tmp_path: Path) -> None:
    result = compile_repository_target(request(repository(tmp_path)))
    evidence = result.rendered.budget_evidence
    assert result.selection.available_tokens == evidence.source_allowance_tokens
    assert result.selection.used_tokens <= result.selection.available_tokens
    assert result.rendered.exact_token_count <= evidence.configured_budget
