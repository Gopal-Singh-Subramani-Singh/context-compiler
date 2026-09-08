from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from contextc.application.compile import (
    CompileRepositoryRequest,
    compile_repository_to_path,
)
from contextc.cli.main import main
from contextc.errors import (
    ArtifactTransactionError,
    ManifestSourceMismatchError,
    RebuildCompatibilityError,
    ReproductionMismatchError,
    SchemaVersionError,
)
from contextc.hashing import digest_bytes
from contextc.reproduction import (
    BuildManifest,
    check_rebuild_compatibility,
    read_build_manifest,
    rebuild_build,
    stored_build_evidence,
    verify_build,
)
from contextc.reproduction.transaction import (
    canonical_manifest_bytes,
    default_manifest_path,
    pretty_manifest_bytes,
)
from contextc.targets import TargetId

FIXTURE = Path(__file__).parent / "fixtures" / "m4_reproduction_repo"


def _copy_fixture(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    for source in sorted(FIXTURE.iterdir()):
        (repository / source.name).write_bytes(source.read_bytes())
    return repository


def _request(
    repository: Path, *, task: str = "explain stable reference"
) -> CompileRepositoryRequest:
    return CompileRepositoryRequest(
        repository=repository,
        task=task,
        target_id=TargetId.GENERIC,
        token_budget=500,
        time_anchor=datetime(2026, 8, 29, tzinfo=UTC),
        source_revision="fixture-v1",
        policy_id="policy:m4-test",
        policy_version="1.0.0",
        random_seed=7,
        system_instruction="Use deterministic evidence.",
        developer_instruction="Explain stored dependency behavior.",
        policy_instruction="Do not use external evidence.",
        tool_schema_text='{"name":"none"}',
    )


def _build(tmp_path: Path) -> tuple[Path, Path, Path, BuildManifest]:
    repository = _copy_fixture(tmp_path)
    output = tmp_path / "build" / "context.txt"
    compile_repository_to_path(_request(repository), output)
    manifest_path = default_manifest_path(output)
    return repository, output, manifest_path, read_build_manifest(manifest_path)


def _write_manifest(path: Path, manifest: BuildManifest) -> None:
    path.write_bytes(pretty_manifest_bytes(manifest))


def test_manifest_is_strict_canonical_portable_and_path_independent(tmp_path: Path) -> None:
    _repository, output, manifest_path, manifest = _build(tmp_path)
    assert not Path(manifest.artifact_path).is_absolute()
    assert not Path(manifest.source_path).is_absolute()
    assert str(tmp_path) not in canonical_manifest_bytes(manifest).decode()
    assert manifest.expected_build_id == manifest.build_id
    assert BuildManifest.from_dict(manifest.to_dict()) == manifest
    assert canonical_manifest_bytes(BuildManifest.from_dict(manifest.to_dict())) == (
        canonical_manifest_bytes(manifest)
    )

    rebuilt = rebuild_build(manifest_path, output_path=tmp_path / "fresh" / "context.txt")
    rebuilt_manifest = read_build_manifest(rebuilt.manifest_path)
    assert rebuilt.build_id == manifest.build_id
    assert rebuilt_manifest.semantic_form() == manifest.semantic_form()
    assert rebuilt.artifact_path.read_bytes() == output.read_bytes()


def test_verify_recounts_and_checks_available_source_without_mutation(tmp_path: Path) -> None:
    _repository, output, manifest_path, manifest = _build(tmp_path)
    artifact_before = output.read_bytes()
    manifest_before = manifest_path.read_bytes()
    result = verify_build(manifest_path)
    assert result.status == "verified"
    assert result.source_checked
    assert result.final_token_count == manifest.final_emitted_token_count
    assert result.artifact_identity == digest_bytes(output.read_bytes())
    assert output.read_bytes() == artifact_before
    assert manifest_path.read_bytes() == manifest_before


def test_altered_artifact_byte_fails_and_verify_is_read_only(tmp_path: Path) -> None:
    _repository, output, manifest_path, _manifest = _build(tmp_path)
    output.write_bytes(output.read_bytes() + b"tamper")
    artifact_before = output.read_bytes()
    manifest_before = manifest_path.read_bytes()
    with pytest.raises(ReproductionMismatchError, match=r"CTX610.*artifact identity"):
        verify_build(manifest_path)
    assert output.read_bytes() == artifact_before
    assert manifest_path.read_bytes() == manifest_before


def test_altered_manifest_artifact_identity_fails(tmp_path: Path) -> None:
    _repository, _output, manifest_path, manifest = _build(tmp_path)
    altered = replace(
        manifest,
        artifact_content_identity=f"sha256:{'f' * 64}",
    ).with_computed_build_id()
    _write_manifest(manifest_path, altered)
    with pytest.raises(ReproductionMismatchError, match="artifact identity differs"):
        verify_build(manifest_path)


def test_tampered_build_id_and_missing_artifact_fail(tmp_path: Path) -> None:
    _repository, output, manifest_path, manifest = _build(tmp_path)
    tampered = replace(manifest, build_id=f"sha256:{'e' * 64}")
    _write_manifest(manifest_path, tampered)
    with pytest.raises(ReproductionMismatchError, match="build_id"):
        verify_build(manifest_path)

    _write_manifest(manifest_path, manifest)
    output.unlink()
    with pytest.raises(ReproductionMismatchError, match="artifact does not exist"):
        verify_build(manifest_path)


def test_altered_source_content_and_revision_fail_with_ctx600(tmp_path: Path) -> None:
    repository, _output, manifest_path, _manifest = _build(tmp_path)
    (repository / "helper.py").write_text("def stable_value() -> int:\n    return 99\n")
    with pytest.raises(ManifestSourceMismatchError, match=r"CTX600.*source graph"):
        verify_build(manifest_path)

    (repository / "helper.py").write_bytes((FIXTURE / "helper.py").read_bytes())
    with pytest.raises(ManifestSourceMismatchError, match="source revision differs"):
        verify_build(
            manifest_path,
            source_root=repository,
            source_revision="fixture-v2",
        )


def test_changed_task_policy_and_token_metadata_are_detected(tmp_path: Path) -> None:
    _repository, _output, manifest_path, manifest = _build(tmp_path)
    changed_task = replace(
        manifest,
        task_description="a different task",
    ).with_computed_build_id()
    _write_manifest(manifest_path, changed_task)
    with pytest.raises(ReproductionMismatchError, match="task identity"):
        verify_build(manifest_path)

    changed_inputs = dict(manifest.build_inputs)
    changed_inputs["policy_instruction"] = "changed policy"
    changed_policy = replace(manifest, build_inputs=changed_inputs).with_computed_build_id()
    _write_manifest(manifest_path, changed_policy)
    with pytest.raises(ReproductionMismatchError, match="policy identity"):
        verify_build(manifest_path)

    changed_tokens = replace(
        manifest,
        pre_render_selected_tokens=manifest.pre_render_selected_tokens - 1,
        final_emitted_token_count=manifest.final_emitted_token_count - 1,
    ).with_computed_build_id()
    _write_manifest(manifest_path, changed_tokens)
    with pytest.raises(ReproductionMismatchError, match="final token recount differs"):
        verify_build(manifest_path)


def test_changed_tokenizer_and_unpinned_model_rebuild_are_incompatible(tmp_path: Path) -> None:
    _repository, _output, manifest_path, manifest = _build(tmp_path)
    changed = replace(manifest, tokenizer_id="generic:other").with_computed_build_id()
    _write_manifest(manifest_path, changed)
    with pytest.raises(RebuildCompatibilityError, match=r"CTX720.*tokenizer ID differs"):
        verify_build(manifest_path)

    changed_target = replace(manifest, target_id="unsupported").with_computed_build_id()
    _write_manifest(manifest_path, changed_target)
    with pytest.raises(RebuildCompatibilityError, match="unsupported target"):
        verify_build(manifest_path)

    unpinned = replace(
        manifest,
        target_id="qwen",
        tokenizer_id="example/qwen",
        tokenizer_revision=None,
    ).with_computed_build_id()
    with pytest.raises(RebuildCompatibilityError, match="tokenizer revision is not pinned"):
        check_rebuild_compatibility(unpinned)


def test_unsupported_manifest_major_is_ctx720_and_cli_has_no_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _repository, _output, manifest_path, _manifest = _build(tmp_path)
    raw = json.loads(manifest_path.read_text())
    raw["schema_version"]["major"] = 99
    manifest_path.write_text(json.dumps(raw))
    with pytest.raises(SchemaVersionError, match=r"CTX720.*unsupported BuildManifest"):
        read_build_manifest(manifest_path)
    assert main(["reproduce", str(manifest_path), "--verify"]) == 2
    captured = capsys.readouterr()
    assert "CTX720" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize(
    "fault_at",
    (
        "render",
        "artifact_staging",
        "manifest_serialization",
        "manifest_staging",
        "commit_boundary",
    ),
)
def test_fault_injection_preserves_previous_valid_pair_and_cleans_temps(
    tmp_path: Path, fault_at: str
) -> None:
    repository, output, manifest_path, _manifest = _build(tmp_path)
    artifact_before = output.read_bytes()
    manifest_before = manifest_path.read_bytes()
    with pytest.raises(ArtifactTransactionError, match=fault_at):
        compile_repository_to_path(
            _request(repository, task="a replacement build"),
            output,
            fault_at=fault_at,
        )
    assert output.read_bytes() == artifact_before
    assert manifest_path.read_bytes() == manifest_before
    assert not tuple(output.parent.glob(".*.tmp"))
    assert verify_build(manifest_path).status == "verified"


@pytest.mark.parametrize(
    "fault_at",
    (
        "render",
        "artifact_staging",
        "manifest_serialization",
        "manifest_staging",
        "commit_boundary",
    ),
)
def test_failed_initial_transaction_leaves_no_valid_looking_pair(
    tmp_path: Path, fault_at: str
) -> None:
    repository = _copy_fixture(tmp_path)
    output = tmp_path / "new" / "context.txt"
    manifest_path = default_manifest_path(output)
    with pytest.raises(ArtifactTransactionError):
        compile_repository_to_path(_request(repository), output, fault_at=fault_at)
    assert not output.exists()
    assert not manifest_path.exists()
    assert not tuple(output.parent.glob(".*.tmp"))


def test_rebuild_fails_before_output_when_source_is_missing(tmp_path: Path) -> None:
    repository, _output, manifest_path, _manifest = _build(tmp_path)
    for path in repository.iterdir():
        path.unlink()
    repository.rmdir()
    destination = tmp_path / "fresh" / "context.txt"
    with pytest.raises(RebuildCompatibilityError, match="source repository is unavailable"):
        rebuild_build(manifest_path, output_path=destination)
    assert not destination.exists()
    assert not default_manifest_path(destination).exists()


def test_inspect_and_explain_use_stored_evidence_without_selection_rerun(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _repository, _output, manifest_path, manifest = _build(tmp_path)

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("optimizer/selection must not rerun")

    monkeypatch.setattr(
        "contextc.ir.selection.DeterministicBaselineSelection.select",
        forbidden,
    )
    evidence = stored_build_evidence(manifest_path)
    assert evidence["artifact_content_identity"] == manifest.artifact_content_identity
    assert evidence["verification_status"] == "verified"
    assert main(["inspect", str(manifest_path)]) == 0
    assert "optimizer_status: optimal" in capsys.readouterr().out
    assert main(["explain", str(manifest_path), "--json"]) == 0
    explained = capsys.readouterr().out
    assert '"source_graph_identity"' in explained
    assert '"verification_status": "verified"' in explained


def test_cli_compile_verify_rebuild_and_semantic_comparison(tmp_path: Path) -> None:
    repository = _copy_fixture(tmp_path)
    output = tmp_path / "cli" / "context.txt"
    compile_args = [
        "compile",
        str(repository),
        "--task",
        "explain stable reference",
        "--target",
        "generic",
        "--token-budget",
        "500",
        "--time-anchor",
        "2026-08-29T00:00:00Z",
        "--source-revision",
        "fixture-v1",
        "--output",
        str(output),
    ]
    assert main(compile_args) == 0
    manifest_path = default_manifest_path(output)
    assert main(["reproduce", str(manifest_path), "--verify"]) == 0
    rebuilt = tmp_path / "cli-fresh" / "context.txt"
    assert (
        main(
            [
                "reproduce",
                str(manifest_path),
                "--rebuild",
                "--output",
                str(rebuilt),
            ]
        )
        == 0
    )
    original_manifest = read_build_manifest(manifest_path)
    rebuilt_manifest = read_build_manifest(default_manifest_path(rebuilt))
    assert rebuilt.read_bytes() == output.read_bytes()
    assert rebuilt_manifest.semantic_form() == original_manifest.semantic_form()
