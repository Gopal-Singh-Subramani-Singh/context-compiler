"""M4 manifest creation, read-only verification, and deterministic rebuild."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from contextc.canonical import to_canonical_primitive
from contextc.errors import (
    ContextCompilerError,
    ManifestSourceMismatchError,
    RebuildCompatibilityError,
    ReproductionMismatchError,
    SourceValidationError,
)
from contextc.hashing import digest_bytes, semantic_hash
from contextc.reproduction.manifest import BuildManifest
from contextc.reproduction.transaction import default_manifest_path, write_artifact_transaction
from contextc.targets import TargetId
from contextc.tokenizers import (
    GenericTokenizer,
    LlamaTokenizerAdapter,
    QwenTokenizerAdapter,
    StructuredJsonTokenizer,
)
from contextc.tokenizers.types import TargetTokenizer, TokenizerIdentity
from contextc.version import __version__

if TYPE_CHECKING:
    from contextc.application.compile import CompileRepositoryRequest, TargetCompilation

_ZERO_HASH = f"sha256:{'0' * 64}"
COMPILER_BUILD_IDENTITY = semantic_hash(
    {
        "compiler_version": __version__,
        "analysis_pass": "m3_bounded_lexical_baseline:1.0.0",
        "graph_pass": "m2_static_python_graph:1.0.0",
        "lowering_pass": "m3_exact_target_lowering:1.0.0",
        "manifest_protocol": "m4_transactional_reproduction:1.0.0",
        "selection_pass": "m5_optimizer_correctness:1.0.0",
        "security_pass": "m9_structural_security:1.0.0",
        "cross_domain_pass": "m15_source_neutral_generalization:1.0.0",
    }
)


@dataclass(frozen=True, slots=True)
class VerificationResult:
    manifest_path: Path
    artifact_path: Path
    artifact_identity: str
    final_token_count: int
    source_checked: bool
    status: str = "verified"


@dataclass(frozen=True, slots=True)
class RebuildResult:
    artifact_path: Path
    manifest_path: Path
    build_id: str
    artifact_identity: str
    final_token_count: int


def _runtime_number(value: object, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise SourceValidationError(f"selection runtime {name} must be numeric")
    return float(value)


def _runtime_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise SourceValidationError(f"selection runtime {name} must be boolean")
    return value


def _security_evidence(result: TargetCompilation) -> Mapping[str, object]:
    """Return secret-safe semantic M9 evidence for the build manifest."""

    security = result.security
    source_nodes = {node.node_id: node for node in result.source_graph.nodes}
    decisions = tuple(
        {
            "action": decision.action.value,
            "diagnostic_code": decision.diagnostic_code,
            "node_id": decision.node_id,
            "rule_id": decision.rule_id,
            "taint_path": (
                None
                if decision.taint_path is None
                else {
                    "edge_ids": decision.taint_path.edge_ids,
                    "node_ids": decision.taint_path.node_ids,
                    "rule_id": decision.taint_path.rule_id,
                    "sink_node_id": decision.taint_path.sink_node_id,
                    "source_node_id": decision.taint_path.source_node_id,
                }
            ),
        }
        for decision in security.decisions
    )
    taint_paths = tuple(
        {
            "edge_ids": path.edge_ids,
            "node_ids": path.node_ids,
            "rule_id": path.rule_id,
            "sink_node_id": path.sink_node_id,
            "source_node_id": path.source_node_id,
        }
        for path in security.taint_paths
    )
    node_facts = {
        node_id: {
            "instruction_authority": node.instruction_authority.value,
            "sensitivity": node.sensitivity.value,
            "source_uri": node.source.uri,
            "trust_domain": node.trust_domain.value,
        }
        for node_id, node in sorted(source_nodes.items())
    }
    token_deltas = {
        node_id: {
            "after": counts[1],
            "before": counts[0],
            "changed": counts[0] != counts[1],
            "selected_after_security": node_id in result.selection.selected_node_ids,
        }
        for node_id, counts in sorted(result.security_token_deltas.items())
    }
    return {
        "analysis_version": security.analysis_version,
        "blocked_node_ids": security.blocked_node_ids,
        "decisions": decisions,
        "diagnostic_codes": tuple(
            sorted({diagnostic.code.value for diagnostic in security.diagnostics})
        ),
        "excluded_node_ids": security.excluded_node_ids,
        "node_facts": node_facts,
        "policy_id": security.policy_id,
        "policy_identity": security.policy_identity,
        "policy_version": security.policy_version,
        "rule_ids_triggered": tuple(sorted({decision.rule_id for decision in security.decisions})),
        "taint_paths": taint_paths,
        "token_deltas": token_deltas,
        "transformations": security.transformations,
    }


def create_build_manifest(
    *,
    request: CompileRepositoryRequest,
    result: TargetCompilation,
    artifact_path: Path,
    manifest_path: Path,
) -> BuildManifest:
    """Build complete semantic evidence only after final rendering succeeds."""

    from contextc.application.compile import effective_security_policy, policy_identity

    artifact = artifact_path.resolve()
    manifest_file = manifest_path.resolve()
    if artifact.parent != manifest_file.parent:
        raise SourceValidationError("artifact and manifest must share a directory")
    relative_source = Path(os.path.relpath(request.repository.resolve(), manifest_file.parent))
    identity = result.rendered.tokenizer_identity
    diagnostics = (
        result.index.diagnostics
        + result.supersession.diagnostics
        + result.conflicts.diagnostics
        + result.security.diagnostics
        + result.rendered.diagnostics
    )
    task_identity = semantic_hash({"task": request.task})
    manifest = BuildManifest(
        compiler_version=__version__,
        compiler_build_identity=COMPILER_BUILD_IDENTITY,
        build_id=_ZERO_HASH,
        task_id=task_identity,
        task_identity=task_identity,
        task_description=request.task,
        source_path=relative_source.as_posix(),
        source_revision=request.source_revision,
        source_graph_identity=result.source_graph.semantic_identity,
        node_content_hashes={
            node.node_id: node.normalized_content_hash for node in result.source_graph.nodes
        },
        analysis_identity=semantic_hash([analysis.to_dict() for analysis in result.analyses]),
        policy_id=request.policy_id,
        policy_version=request.policy_version,
        policy_identity=policy_identity(request),
        target_id=result.rendered.target_id.value,
        tokenizer_id=identity.tokenizer_id,
        tokenizer_version=identity.tokenizer_version,
        tokenizer_revision=identity.tokenizer_revision,
        tokenizer_configuration_identity=identity.configuration_identity,
        configured_token_budget=result.rendered.budget_evidence.configured_budget,
        source_allowance_tokens=result.rendered.budget_evidence.source_allowance_tokens,
        pre_render_selected_tokens=result.rendered.budget_evidence.pre_trim_selected_tokens,
        final_emitted_token_count=result.rendered.exact_token_count,
        trim_evidence=result.rendered.trim_evidence,
        optimizer_requested=result.selection.requested_strategy_id,
        optimizer_used=result.selection.strategy_id,
        optimizer_version=result.selection.strategy_version,
        optimizer_status=result.selection.optimizer_status.value,
        optimizer_objective=result.selection.objective_value,
        optimizer_runtime_ms=result.selection.solver_runtime_ms,
        optimizer_timed_out=(result.selection.optimizer_status.value == "feasible_timeout"),
        optimizer_timeout_ms=result.selection.solver_timeout_ms,
        optimizer_fallback_reason=result.selection.fallback_reason,
        pipeline_configuration_identity=_pipeline_identity(request, identity),
        random_seed=request.random_seed,
        optimizer_selected_node_ids=result.selection.selected_node_ids,
        ordered_selected_node_ids=result.rendered.ordered_node_ids,
        excluded_node_ids=result.selection.excluded_node_ids,
        dependency_forced_node_ids=result.selection.dependency_forced_node_ids,
        mandatory_node_ids=result.selection.mandatory_node_ids,
        tie_break_trace=result.selection.tie_break_trace,
        diagnostics=diagnostics,
        security_evidence=_security_evidence(result),
        artifact_path=artifact.relative_to(manifest_file.parent).as_posix(),
        artifact_content_identity=digest_bytes(result.rendered.rendered_bytes),
        build_inputs={
            "add_generation_prompt": request.add_generation_prompt,
            "developer_instruction": request.developer_instruction,
            "policy_instruction": request.policy_instruction,
            "system_instruction": request.system_instruction,
            "time_anchor": cast(str, to_canonical_primitive(request.time_anchor)),
            "tokenizer_model_id": request.tokenizer_model_id,
            "tool_schema_text": request.tool_schema_text,
            "optimizer_configuration": request.optimizer.to_dict(),
            "security_policy": to_canonical_primitive(effective_security_policy(request)),
            "source_adapter_id": request.source_adapter_id,
            "source_rules": to_canonical_primitive(request.source_rules),
        },
    ).with_computed_build_id()
    manifest.validate_internal()
    return manifest


def _pipeline_identity(request: CompileRepositoryRequest, identity: TokenizerIdentity) -> str:
    from contextc.application.compile import pipeline_configuration_identity

    return pipeline_configuration_identity(request, identity)


def write_compilation_transaction(
    *,
    request: CompileRepositoryRequest,
    result: TargetCompilation,
    artifact_path: Path,
    manifest_path: Path | None = None,
    fault_at: str | None = None,
) -> tuple[Path, Path, BuildManifest]:
    artifact = artifact_path.resolve()
    manifest_file = (
        default_manifest_path(artifact) if manifest_path is None else manifest_path.resolve()
    )
    manifest = create_build_manifest(
        request=request,
        result=result,
        artifact_path=artifact,
        manifest_path=manifest_file,
    )
    committed_artifact, committed_manifest = write_artifact_transaction(
        artifact_path=artifact,
        manifest_path=manifest_file,
        artifact_bytes=result.rendered.rendered_bytes,
        manifest=manifest,
        fault_at=fault_at,
    )
    return committed_artifact, committed_manifest, manifest


def read_build_manifest(path: Path) -> BuildManifest:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SourceValidationError(f"build manifest is not valid JSON: {error}") from error
    if not isinstance(raw, Mapping) or not all(isinstance(key, str) for key in raw):
        raise SourceValidationError("build manifest root must be an object")
    return BuildManifest.from_dict(raw)


def _target(manifest: BuildManifest) -> TargetId:
    try:
        return TargetId(manifest.target_id)
    except ValueError as error:
        raise RebuildCompatibilityError((f"unsupported target {manifest.target_id!r}",)) from error


def _load_manifest_tokenizer(manifest: BuildManifest) -> TargetTokenizer:
    target = _target(manifest)
    if target is TargetId.GENERIC:
        tokenizer: TargetTokenizer = GenericTokenizer()
    elif target is TargetId.STRUCTURED_JSON:
        tokenizer = StructuredJsonTokenizer()
    elif target is TargetId.QWEN:
        tokenizer = QwenTokenizerAdapter(
            model_id=manifest.tokenizer_id,
            revision=manifest.tokenizer_revision,
            local_files_only=True,
        )
    else:
        tokenizer = LlamaTokenizerAdapter(
            model_id=manifest.tokenizer_id,
            revision=manifest.tokenizer_revision,
            local_files_only=True,
        )
    identity = tokenizer.identity
    differences: list[str] = []
    for name, actual, expected in (
        ("target", identity.target_id, manifest.target_id),
        ("tokenizer ID", identity.tokenizer_id, manifest.tokenizer_id),
        ("tokenizer version", identity.tokenizer_version, manifest.tokenizer_version),
        ("tokenizer revision", identity.tokenizer_revision, manifest.tokenizer_revision),
        (
            "tokenizer configuration identity",
            identity.configuration_identity,
            manifest.tokenizer_configuration_identity,
        ),
    ):
        if actual != expected:
            differences.append(f"{name} differs: current={actual!r}, stored={expected!r}")
    if differences:
        raise RebuildCompatibilityError(tuple(differences))
    return tokenizer


def _request_from_manifest(
    manifest: BuildManifest,
    source_root: Path,
) -> CompileRepositoryRequest:
    from contextc.application.compile import CompileRepositoryRequest
    from contextc.optimization.models import OptimizerConfiguration
    from contextc.security.policy import policy_from_mapping
    from contextc.source_rules import source_rules_from_manifest

    inputs = manifest.build_inputs
    raw_anchor = cast(str, inputs["time_anchor"])
    try:
        anchor = datetime.fromisoformat(raw_anchor.replace("Z", "+00:00"))
    except ValueError as error:
        raise RebuildCompatibilityError(("stored time anchor is not ISO-8601",)) from error
    return CompileRepositoryRequest(
        repository=source_root,
        task=manifest.task_description,
        target_id=_target(manifest),
        token_budget=manifest.configured_token_budget,
        time_anchor=anchor,
        tokenizer_model_id=cast(str | None, inputs["tokenizer_model_id"]),
        tokenizer_revision=manifest.tokenizer_revision,
        tokenizer_local_files_only=True,
        source_revision=manifest.source_revision,
        policy_id=manifest.policy_id,
        policy_version=manifest.policy_version,
        random_seed=manifest.random_seed,
        system_instruction=cast(str, inputs["system_instruction"]),
        developer_instruction=cast(str, inputs["developer_instruction"]),
        policy_instruction=cast(str, inputs["policy_instruction"]),
        tool_schema_text=cast(str, inputs["tool_schema_text"]),
        add_generation_prompt=cast(bool, inputs["add_generation_prompt"]),
        security_policy=policy_from_mapping(cast(Mapping[str, object], inputs["security_policy"])),
        source_adapter_id=cast(str, inputs["source_adapter_id"]),
        source_rules=source_rules_from_manifest(inputs["source_rules"]),
        optimizer=OptimizerConfiguration.from_dict(
            cast(Mapping[str, object], inputs["optimizer_configuration"])
        ),
    )


def _current_source_evidence(
    manifest: BuildManifest,
    source_root: Path,
    source_revision: str | None,
) -> tuple[str, Mapping[str, str]]:
    from contextc.cross_domain.adapters import load_source_context

    if source_revision != manifest.source_revision:
        raise ManifestSourceMismatchError(
            (
                f"source revision differs: current={source_revision!r}, "
                f"stored={manifest.source_revision!r}",
            )
        )
    from contextc.source_rules import source_rules_from_manifest

    adapter_id = cast(str, manifest.build_inputs["source_adapter_id"])
    source_rules = source_rules_from_manifest(manifest.build_inputs["source_rules"])
    adapted = load_source_context(
        adapter_id, source_root, revision=source_revision, source_rules=source_rules
    )
    graph = adapted.graph
    hashes = {node.node_id: node.normalized_content_hash for node in graph.nodes}
    return graph.semantic_identity, hashes


def _verify_source(
    manifest: BuildManifest,
    source_root: Path,
    source_revision: str | None,
) -> None:
    graph_identity, hashes = _current_source_evidence(manifest, source_root, source_revision)
    differences: list[str] = []
    if graph_identity != manifest.source_graph_identity:
        differences.append(
            "source graph identity differs: "
            f"current={graph_identity}, stored={manifest.source_graph_identity}"
        )
    stored_hashes = dict(manifest.node_content_hashes)
    for node_id in sorted(set(stored_hashes) | set(hashes)):
        if stored_hashes.get(node_id) != hashes.get(node_id):
            differences.append(
                f"node content identity differs for {node_id}: "
                f"current={hashes.get(node_id)!r}, stored={stored_hashes.get(node_id)!r}"
            )
    if differences:
        raise ManifestSourceMismatchError(tuple(differences))


def _verify_semantic_inputs(
    manifest: BuildManifest,
    tokenizer: TargetTokenizer,
    source_root: Path,
) -> None:
    from contextc.application.compile import pipeline_configuration_identity, policy_identity

    request = _request_from_manifest(manifest, source_root)
    differences: list[str] = []
    if semantic_hash({"task": request.task}) != manifest.task_identity:
        differences.append("task identity differs from stored task")
    if manifest.task_id != manifest.task_identity:
        differences.append("task ID differs from task identity")
    if policy_identity(request) != manifest.policy_identity:
        differences.append("policy identity differs from stored policy inputs")
    if (
        pipeline_configuration_identity(request, tokenizer.identity)
        != manifest.pipeline_configuration_identity
    ):
        differences.append("pipeline configuration identity differs from stored inputs")
    if differences:
        raise ReproductionMismatchError(tuple(differences))


def verify_build(
    manifest_path: Path,
    *,
    source_root: Path | None = None,
    source_revision: str | None = None,
) -> VerificationResult:
    """Verify stored evidence without rebuilding or mutating any file."""

    manifest_file = manifest_path.resolve()
    manifest = read_build_manifest(manifest_file)
    manifest.validate_internal()
    artifact = (manifest_file.parent / manifest.artifact_path).resolve()
    if not artifact.is_file():
        raise ReproductionMismatchError((f"artifact does not exist: {artifact}",))
    artifact_bytes = artifact.read_bytes()
    identity = digest_bytes(artifact_bytes)
    if identity != manifest.artifact_content_identity:
        raise ReproductionMismatchError(
            (
                "artifact identity differs: "
                f"current={identity}, stored={manifest.artifact_content_identity}",
            )
        )
    try:
        text = artifact_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ReproductionMismatchError(("artifact is not valid UTF-8",)) from error
    tokenizer = _load_manifest_tokenizer(manifest)
    final_count = tokenizer.count(text)
    token_differences: list[str] = []
    if final_count != manifest.final_emitted_token_count:
        token_differences.append(
            "final token recount differs: "
            f"current={final_count}, stored={manifest.final_emitted_token_count}"
        )
    if final_count > manifest.configured_token_budget:
        token_differences.append(
            f"final token recount {final_count} exceeds budget {manifest.configured_token_budget}"
        )
    if token_differences:
        raise ReproductionMismatchError(tuple(token_differences))

    stored_source = (manifest_file.parent / manifest.source_path).resolve()
    selected_source = source_root.resolve() if source_root is not None else stored_source
    _verify_semantic_inputs(manifest, tokenizer, selected_source)
    source_checked = source_root is not None or stored_source.is_dir()
    if source_checked:
        effective_revision = (
            manifest.source_revision if source_revision is None else source_revision
        )
        _verify_source(manifest, selected_source, effective_revision)
    return VerificationResult(
        manifest_path=manifest_file,
        artifact_path=artifact,
        artifact_identity=identity,
        final_token_count=final_count,
        source_checked=source_checked,
    )


def check_rebuild_compatibility(manifest: BuildManifest) -> None:
    """Fail before rebuild when recorded deterministic semantics are unavailable."""

    differences: list[str] = []
    if manifest.compiler_version != __version__:
        differences.append(
            f"compiler version differs: current={__version__}, stored={manifest.compiler_version}"
        )
    if manifest.compiler_build_identity != COMPILER_BUILD_IDENTITY:
        differences.append("compiler build implementation identity differs")
    target = _target(manifest)
    if target in {TargetId.QWEN, TargetId.LLAMA} and manifest.tokenizer_revision is None:
        differences.append("model tokenizer revision is not pinned")
    if differences:
        raise RebuildCompatibilityError(tuple(differences))


def _semantic_manifest_differences(
    stored: BuildManifest, rebuilt: BuildManifest
) -> tuple[str, ...]:
    left = stored.semantic_form()
    right = rebuilt.semantic_form()
    return tuple(
        f"semantic manifest field {key} differs: "
        f"stored={left.get(key)!r}, rebuilt={right.get(key)!r}"
        for key in sorted(set(left) | set(right))
        if left.get(key) != right.get(key)
    )


def rebuild_build(
    manifest_path: Path,
    *,
    output_path: Path,
    source_root: Path | None = None,
    source_revision: str | None = None,
) -> RebuildResult:
    """Recompile from recorded inputs, compare, then commit a fresh pair."""

    from contextc.application.compile import compile_source_target

    manifest_file = manifest_path.resolve()
    stored = read_build_manifest(manifest_file)
    stored.validate_internal()
    check_rebuild_compatibility(stored)
    stored_source = (manifest_file.parent / stored.source_path).resolve()
    selected_source = source_root.resolve() if source_root is not None else stored_source
    if not selected_source.is_dir():
        raise RebuildCompatibilityError((f"source repository is unavailable: {selected_source}",))
    effective_revision = stored.source_revision if source_revision is None else source_revision
    verify_build(
        manifest_file,
        source_root=selected_source,
        source_revision=effective_revision,
    )
    request = _request_from_manifest(stored, selected_source)
    if effective_revision != stored.source_revision:
        raise ManifestSourceMismatchError(("source revision differs before rebuild",))
    rebuilt = compile_source_target(request)
    destination = output_path.resolve()
    rebuilt_manifest_path = default_manifest_path(destination)
    candidate = create_build_manifest(
        request=request,
        result=rebuilt,
        artifact_path=destination,
        manifest_path=rebuilt_manifest_path,
    )
    original_artifact = (manifest_file.parent / stored.artifact_path).resolve().read_bytes()
    differences = list(_semantic_manifest_differences(stored, candidate))
    if rebuilt.rendered.rendered_bytes != original_artifact:
        differences.append("rendered artifact bytes differ")
    if rebuilt.rendered.ordered_node_ids != stored.ordered_selected_node_ids:
        differences.append("selected node order differs")
    if rebuilt.rendered.exact_token_count != stored.final_emitted_token_count:
        differences.append("final token count differs")
    if differences:
        raise ReproductionMismatchError(tuple(dict.fromkeys(differences)))
    write_artifact_transaction(
        artifact_path=destination,
        manifest_path=rebuilt_manifest_path,
        artifact_bytes=rebuilt.rendered.rendered_bytes,
        manifest=candidate,
    )
    return RebuildResult(
        artifact_path=destination,
        manifest_path=rebuilt_manifest_path,
        build_id=candidate.build_id,
        artifact_identity=candidate.artifact_content_identity,
        final_token_count=candidate.final_emitted_token_count,
    )


def stored_build_evidence(manifest_path: Path) -> dict[str, object]:
    """Expose only recorded evidence; never rerun selection or optimization."""

    manifest_file = manifest_path.resolve()
    manifest = read_build_manifest(manifest_file)
    try:
        verification = verify_build(manifest_file)
        verification_status = verification.status
        verification_detail = "stored artifact and available evidence match"
    except ContextCompilerError as error:
        verification_status = "failed"
        verification_detail = str(error)
    return {
        "artifact_content_identity": manifest.artifact_content_identity,
        "artifact_path": manifest.artifact_path,
        "build_id": manifest.build_id,
        "configured_token_budget": manifest.configured_token_budget,
        "diagnostics": tuple(item.code.value for item in manifest.diagnostics),
        "diagnostic_evidence": tuple(item.to_dict() for item in manifest.diagnostics),
        "final_emitted_token_count": manifest.final_emitted_token_count,
        "optimizer_fallback_reason": manifest.optimizer_fallback_reason,
        "optimizer_requested": manifest.optimizer_requested,
        "optimizer_used": manifest.optimizer_used,
        "optimizer_objective": manifest.optimizer_objective,
        "optimizer_runtime_ms": manifest.optimizer_runtime_ms,
        "optimizer_timed_out": manifest.optimizer_timed_out,
        "optimizer_timeout_ms": manifest.optimizer_timeout_ms,
        "optimizer_tie_break_trace": manifest.tie_break_trace,
        "optimizer_selected_node_ids": manifest.optimizer_selected_node_ids,
        "dependency_forced_node_ids": manifest.dependency_forced_node_ids,
        "excluded_node_ids": manifest.excluded_node_ids,
        "optimality_proven": manifest.optimizer_status == "optimal",
        "strategy_heuristic": manifest.optimizer_status == "heuristic",
        "exact_solver_timed_out": manifest.optimizer_timed_out,
        "fallback_used": manifest.optimizer_status == "fallback",
        "optimizer_status": manifest.optimizer_status,
        "source_graph_identity": manifest.source_graph_identity,
        "source_adapter_id": manifest.build_inputs["source_adapter_id"],
        "source_rules": manifest.build_inputs["source_rules"],
        "supersession_diagnostics": tuple(
            item.to_dict() for item in manifest.diagnostics if item.code.value == "CTX210"
        ),
        "security_evidence": manifest.security_evidence,
        "target_id": manifest.target_id,
        "tokenizer_id": manifest.tokenizer_id,
        "verification_detail": verification_detail,
        "verification_status": verification_status,
    }
