"""Strict canonical M4 build-manifest model."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from pathlib import PurePosixPath
from typing import cast

from contextc.canonical import freeze_value, to_canonical_primitive
from contextc.decoding import (
    optional_string,
    require_bool,
    require_float,
    require_int,
    require_mapping,
    require_sequence,
    require_string,
    require_string_tuple,
    require_text,
)
from contextc.diagnostics import Diagnostic
from contextc.errors import ReproductionMismatchError, SourceValidationError
from contextc.hashing import semantic_hash
from contextc.schema import (
    BUILD_MANIFEST_SCHEMA,
    TRIM_EVIDENCE_SCHEMA,
    SchemaVersion,
    require_schema_version,
)
from contextc.targets import TrimEvidence

_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?\Z")
_BUILD_INPUT_KEYS = frozenset(
    {
        "add_generation_prompt",
        "developer_instruction",
        "policy_instruction",
        "system_instruction",
        "time_anchor",
        "tokenizer_model_id",
        "tool_schema_text",
        "optimizer_configuration",
        "security_policy",
        "source_adapter_id",
        "source_rules",
    }
)


def _portable_path(value: str, field: str, *, allow_parent: bool = False) -> str:
    if not value or "\\" in value:
        raise SourceValidationError(f"{field} must be a non-empty portable POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or (not allow_parent and ".." in path.parts):
        raise SourceValidationError(f"{field} must be relative and may not escape its root")
    return path.as_posix()


def _require_hash(value: str, field: str) -> str:
    if not _HASH.fullmatch(value):
        raise SourceValidationError(f"{field} must be a SHA-256 identity")
    return value


@dataclass(frozen=True, slots=True)
class BuildManifest:
    """Complete stored evidence for verification and deterministic rebuild."""

    compiler_version: str
    compiler_build_identity: str
    build_id: str
    task_id: str
    task_identity: str
    task_description: str
    source_path: str
    source_revision: str | None
    source_graph_identity: str
    node_content_hashes: Mapping[str, str]
    analysis_identity: str
    policy_id: str
    policy_version: str
    policy_identity: str
    target_id: str
    tokenizer_id: str
    tokenizer_version: str
    tokenizer_revision: str | None
    tokenizer_configuration_identity: str
    configured_token_budget: int
    source_allowance_tokens: int
    pre_render_selected_tokens: int
    final_emitted_token_count: int
    trim_evidence: tuple[TrimEvidence, ...]
    optimizer_requested: str
    optimizer_used: str
    optimizer_version: str
    optimizer_status: str
    optimizer_objective: float | None
    optimizer_runtime_ms: float
    optimizer_timed_out: bool
    optimizer_timeout_ms: int | None
    optimizer_fallback_reason: str | None
    pipeline_configuration_identity: str
    random_seed: int
    optimizer_selected_node_ids: tuple[str, ...]
    ordered_selected_node_ids: tuple[str, ...]
    excluded_node_ids: tuple[str, ...]
    dependency_forced_node_ids: tuple[str, ...]
    mandatory_node_ids: tuple[str, ...]
    tie_break_trace: tuple[str, ...]
    diagnostics: tuple[Diagnostic, ...]
    security_evidence: Mapping[str, object]
    artifact_path: str
    artifact_content_identity: str
    build_inputs: Mapping[str, object]
    schema_version: SchemaVersion = BUILD_MANIFEST_SCHEMA

    def __post_init__(self) -> None:
        text_fields = (
            "task_id",
            "task_description",
            "policy_id",
            "target_id",
            "tokenizer_id",
            "tokenizer_version",
            "optimizer_requested",
            "optimizer_used",
            "optimizer_status",
        )
        for field_name in text_fields:
            if not getattr(self, field_name):
                raise SourceValidationError(f"manifest {field_name} must not be empty")
        for field_name in ("compiler_version", "policy_version", "optimizer_version"):
            if not _VERSION.fullmatch(getattr(self, field_name)):
                raise SourceValidationError(f"manifest {field_name} must be semantic version")
        for field_name in (
            "compiler_build_identity",
            "build_id",
            "task_identity",
            "source_graph_identity",
            "analysis_identity",
            "policy_identity",
            "tokenizer_configuration_identity",
            "pipeline_configuration_identity",
            "artifact_content_identity",
        ):
            _require_hash(getattr(self, field_name), f"manifest.{field_name}")
        object.__setattr__(
            self,
            "source_path",
            _portable_path(self.source_path, "source_path", allow_parent=True),
        )
        object.__setattr__(
            self, "artifact_path", _portable_path(self.artifact_path, "artifact_path")
        )
        tuple_fields = (
            "trim_evidence",
            "optimizer_selected_node_ids",
            "ordered_selected_node_ids",
            "excluded_node_ids",
            "dependency_forced_node_ids",
            "mandatory_node_ids",
            "tie_break_trace",
            "diagnostics",
        )
        for field_name in tuple_fields:
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        for field_name in (
            "optimizer_selected_node_ids",
            "ordered_selected_node_ids",
            "excluded_node_ids",
            "dependency_forced_node_ids",
            "mandatory_node_ids",
        ):
            values = getattr(self, field_name)
            if any(not value for value in values) or len(values) != len(set(values)):
                raise SourceValidationError(f"manifest {field_name} must contain unique IDs")
        counts = (
            self.configured_token_budget,
            self.source_allowance_tokens,
            self.pre_render_selected_tokens,
            self.final_emitted_token_count,
        )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counts
        ):
            raise SourceValidationError("manifest token counts must be non-negative integers")
        if not isinstance(self.random_seed, int) or isinstance(self.random_seed, bool):
            raise SourceValidationError("manifest random_seed must be an integer")
        if not math.isfinite(self.optimizer_runtime_ms) or self.optimizer_runtime_ms < 0:
            raise SourceValidationError(
                "manifest optimizer runtime must be finite and non-negative"
            )
        if self.optimizer_objective is not None and not math.isfinite(self.optimizer_objective):
            raise SourceValidationError("manifest optimizer objective must be finite")
        if not isinstance(self.optimizer_timed_out, bool):
            raise SourceValidationError("manifest optimizer_timed_out must be boolean")
        if self.optimizer_timeout_ms is not None and (
            not isinstance(self.optimizer_timeout_ms, int)
            or isinstance(self.optimizer_timeout_ms, bool)
            or self.optimizer_timeout_ms < 1
        ):
            raise SourceValidationError("manifest optimizer_timeout_ms must be positive or null")
        hashes = dict(self.node_content_hashes)
        if any(not node_id for node_id in hashes):
            raise SourceValidationError("manifest node hash identifiers must not be empty")
        for node_hash in hashes.values():
            _require_hash(node_hash, "manifest.node_content_hash")
        frozen_hashes = freeze_value(hashes)
        frozen_inputs = freeze_value(self.build_inputs)
        frozen_security = freeze_value(self.security_evidence)
        if (
            not isinstance(frozen_hashes, Mapping)
            or not isinstance(frozen_inputs, Mapping)
            or not isinstance(frozen_security, Mapping)
        ):
            raise SourceValidationError("manifest maps must be mappings")
        if set(frozen_inputs) != _BUILD_INPUT_KEYS:
            raise SourceValidationError(
                f"manifest build_inputs must contain exactly {sorted(_BUILD_INPUT_KEYS)}"
            )
        for key in _BUILD_INPUT_KEYS - {
            "add_generation_prompt",
            "optimizer_configuration",
            "security_policy",
            "source_adapter_id",
            "source_rules",
        }:
            value = frozen_inputs[key]
            if key == "tokenizer_model_id" and value is None:
                continue
            if not isinstance(value, str):
                raise SourceValidationError(f"manifest build_inputs.{key} must be text")
        if not isinstance(frozen_inputs["add_generation_prompt"], bool):
            raise SourceValidationError("manifest build_inputs.add_generation_prompt must be bool")
        if not isinstance(frozen_inputs["optimizer_configuration"], Mapping):
            raise SourceValidationError(
                "manifest build_inputs.optimizer_configuration must be a mapping"
            )
        if not isinstance(frozen_inputs["source_rules"], tuple):
            raise SourceValidationError("manifest build_inputs.source_rules must be a sequence")
        if not isinstance(frozen_inputs["security_policy"], Mapping):
            raise SourceValidationError("manifest build_inputs.security_policy must be a mapping")
        required_security = {
            "analysis_version",
            "blocked_node_ids",
            "decisions",
            "diagnostic_codes",
            "excluded_node_ids",
            "node_facts",
            "policy_id",
            "policy_identity",
            "policy_version",
            "rule_ids_triggered",
            "taint_paths",
            "token_deltas",
            "transformations",
        }
        if set(frozen_security) != required_security:
            raise SourceValidationError(
                "manifest security_evidence fields differ; "
                f"expected={sorted(required_security)}, actual={sorted(frozen_security)}"
            )
        security_identity = frozen_security["policy_identity"]
        if not isinstance(security_identity, str):
            raise SourceValidationError("manifest security policy identity must be text")
        _require_hash(security_identity, "manifest.security_evidence.policy_identity")
        for field_name in ("analysis_version", "policy_id", "policy_version"):
            value = frozen_security[field_name]
            if not isinstance(value, str) or not value:
                raise SourceValidationError(
                    f"manifest security_evidence.{field_name} must be non-empty text"
                )
        object.__setattr__(self, "node_content_hashes", frozen_hashes)
        object.__setattr__(self, "build_inputs", frozen_inputs)
        object.__setattr__(self, "security_evidence", frozen_security)
        require_schema_version(
            self.schema_version,
            expected=BUILD_MANIFEST_SCHEMA,
            artifact="BuildManifest",
        )

    def semantic_form(self) -> dict[str, object]:
        """Return identity-bearing fields, excluding portable storage location."""

        value = self.to_dict()
        value.pop("build_id")
        value.pop("artifact_path")
        value.pop("source_path")
        value.pop("optimizer_runtime_ms")
        return value

    @property
    def expected_build_id(self) -> str:
        return semantic_hash(self.semantic_form())

    def with_computed_build_id(self) -> BuildManifest:
        return replace(self, build_id=self.expected_build_id)

    def internal_differences(self) -> tuple[str, ...]:
        differences: list[str] = []
        if self.build_id != self.expected_build_id:
            differences.append("build_id does not match canonical semantic manifest fields")
        if self.final_emitted_token_count > self.configured_token_budget:
            differences.append("final emitted token count exceeds configured budget")
        if self.source_allowance_tokens > self.configured_token_budget:
            differences.append("source allowance exceeds configured budget")
        optimizer_selected = set(self.optimizer_selected_node_ids)
        final_selected = set(self.ordered_selected_node_ids)
        if not final_selected <= optimizer_selected:
            differences.append("final selected nodes are not a subset of optimizer selection")
        if set(self.dependency_forced_node_ids) - optimizer_selected:
            differences.append("dependency-forced nodes are absent from optimizer selection")
        if set(self.mandatory_node_ids) - final_selected:
            differences.append("mandatory nodes are absent from final selection")
        if set(self.excluded_node_ids) & optimizer_selected:
            differences.append("excluded nodes overlap optimizer selection")
        security = self.security_evidence
        security_policy = self.build_inputs["security_policy"]
        if semantic_hash(security_policy) != security["policy_identity"]:
            differences.append("security policy identity differs from stored policy input")
        if security["blocked_node_ids"]:
            differences.append("successful manifest records blocked security nodes")
        security_excluded = set(cast(tuple[str, ...], security["excluded_node_ids"]))
        if security_excluded - set(self.excluded_node_ids):
            differences.append("security-excluded nodes are absent from final exclusions")
        security_codes = set(cast(tuple[str, ...], security["diagnostic_codes"]))
        manifest_codes = {diagnostic.code.value for diagnostic in self.diagnostics}
        if security_codes - manifest_codes:
            differences.append("security diagnostic codes are absent from manifest diagnostics")
        for diagnostic in self.diagnostics:
            if (
                diagnostic.code.value == "CTX210"
                and diagnostic.node_ids
                and diagnostic.node_ids[0] not in set(self.excluded_node_ids)
            ):
                differences.append("superseded node is absent from final exclusions")
        if self.trim_evidence:
            previous = self.pre_render_selected_tokens
            removed: set[str] = set()
            for expected_iteration, trim in enumerate(self.trim_evidence, start=1):
                if trim.iteration != expected_iteration:
                    differences.append("trim iterations are not contiguous")
                if trim.token_count_before != previous:
                    differences.append("trim token-count chain is inconsistent")
                previous = trim.token_count_after
                removed.update(trim.removed_node_ids)
            if previous != self.final_emitted_token_count:
                differences.append("final trim count differs from emitted token count")
            if removed != optimizer_selected - final_selected:
                differences.append("trimmed nodes differ from optimizer/final selection delta")
        elif self.pre_render_selected_tokens != self.final_emitted_token_count:
            differences.append("untrimmed pre-render and final token counts differ")
        return tuple(dict.fromkeys(differences))

    def validate_internal(self) -> None:
        differences = self.internal_differences()
        if differences:
            raise ReproductionMismatchError(differences)

    def to_dict(self) -> dict[str, object]:
        primitive = to_canonical_primitive(self)
        if not isinstance(primitive, dict):
            raise AssertionError("build manifest did not canonicalize to an object")
        return primitive

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> BuildManifest:
        expected_fields = {field.name for field in fields(cls)}
        if set(value) != expected_fields:
            missing = sorted(expected_fields - set(value))
            extra = sorted(set(value) - expected_fields)
            raise SourceValidationError(
                f"BuildManifest fields differ; missing={missing}, extra={extra}"
            )
        version = require_schema_version(
            value.get("schema_version"),
            expected=BUILD_MANIFEST_SCHEMA,
            artifact="BuildManifest",
        )
        raw_hashes = require_mapping(value.get("node_content_hashes"), "node_content_hashes")
        hashes = {
            node_id: require_string(node_hash, "node_content_hash")
            for node_id, node_hash in raw_hashes.items()
        }
        trims = tuple(
            _trim_from_dict(require_mapping(item, "trim_evidence"))
            for item in require_sequence(value.get("trim_evidence"), "trim_evidence")
        )
        diagnostics = tuple(
            Diagnostic.from_dict(require_mapping(item, "diagnostic"))
            for item in require_sequence(value.get("diagnostics"), "diagnostics")
        )
        raw_objective = value.get("optimizer_objective")
        return cls(
            compiler_version=require_string(value.get("compiler_version"), "compiler_version"),
            compiler_build_identity=require_string(
                value.get("compiler_build_identity"), "compiler_build_identity"
            ),
            build_id=require_string(value.get("build_id"), "build_id"),
            task_id=require_string(value.get("task_id"), "task_id"),
            task_identity=require_string(value.get("task_identity"), "task_identity"),
            task_description=require_string(value.get("task_description"), "task_description"),
            source_path=require_string(value.get("source_path"), "source_path"),
            source_revision=optional_string(value.get("source_revision"), "source_revision"),
            source_graph_identity=require_string(
                value.get("source_graph_identity"), "source_graph_identity"
            ),
            node_content_hashes=hashes,
            analysis_identity=require_string(value.get("analysis_identity"), "analysis_identity"),
            policy_id=require_string(value.get("policy_id"), "policy_id"),
            policy_version=require_string(value.get("policy_version"), "policy_version"),
            policy_identity=require_string(value.get("policy_identity"), "policy_identity"),
            target_id=require_string(value.get("target_id"), "target_id"),
            tokenizer_id=require_string(value.get("tokenizer_id"), "tokenizer_id"),
            tokenizer_version=require_string(value.get("tokenizer_version"), "tokenizer_version"),
            tokenizer_revision=optional_string(
                value.get("tokenizer_revision"), "tokenizer_revision"
            ),
            tokenizer_configuration_identity=require_string(
                value.get("tokenizer_configuration_identity"),
                "tokenizer_configuration_identity",
            ),
            configured_token_budget=require_int(
                value.get("configured_token_budget"), "configured_token_budget"
            ),
            source_allowance_tokens=require_int(
                value.get("source_allowance_tokens"), "source_allowance_tokens"
            ),
            pre_render_selected_tokens=require_int(
                value.get("pre_render_selected_tokens"), "pre_render_selected_tokens"
            ),
            final_emitted_token_count=require_int(
                value.get("final_emitted_token_count"), "final_emitted_token_count"
            ),
            trim_evidence=trims,
            optimizer_requested=require_string(
                value.get("optimizer_requested"), "optimizer_requested"
            ),
            optimizer_used=require_string(value.get("optimizer_used"), "optimizer_used"),
            optimizer_version=require_string(value.get("optimizer_version"), "optimizer_version"),
            optimizer_status=require_string(value.get("optimizer_status"), "optimizer_status"),
            optimizer_objective=(
                None
                if raw_objective is None
                else require_float(raw_objective, "optimizer_objective")
            ),
            optimizer_runtime_ms=require_float(
                value.get("optimizer_runtime_ms"), "optimizer_runtime_ms"
            ),
            optimizer_timed_out=require_bool(
                value.get("optimizer_timed_out"), "optimizer_timed_out"
            ),
            optimizer_timeout_ms=(
                None
                if value.get("optimizer_timeout_ms") is None
                else require_int(value.get("optimizer_timeout_ms"), "optimizer_timeout_ms")
            ),
            optimizer_fallback_reason=optional_string(
                value.get("optimizer_fallback_reason"), "optimizer_fallback_reason"
            ),
            pipeline_configuration_identity=require_string(
                value.get("pipeline_configuration_identity"),
                "pipeline_configuration_identity",
            ),
            random_seed=require_int(value.get("random_seed"), "random_seed"),
            optimizer_selected_node_ids=require_string_tuple(
                value.get("optimizer_selected_node_ids"), "optimizer_selected_node_ids"
            ),
            ordered_selected_node_ids=require_string_tuple(
                value.get("ordered_selected_node_ids"), "ordered_selected_node_ids"
            ),
            excluded_node_ids=require_string_tuple(
                value.get("excluded_node_ids"), "excluded_node_ids"
            ),
            dependency_forced_node_ids=require_string_tuple(
                value.get("dependency_forced_node_ids"), "dependency_forced_node_ids"
            ),
            mandatory_node_ids=require_string_tuple(
                value.get("mandatory_node_ids"), "mandatory_node_ids"
            ),
            tie_break_trace=require_string_tuple(value.get("tie_break_trace"), "tie_break_trace"),
            diagnostics=diagnostics,
            security_evidence=require_mapping(value.get("security_evidence"), "security_evidence"),
            artifact_path=require_string(value.get("artifact_path"), "artifact_path"),
            artifact_content_identity=require_string(
                value.get("artifact_content_identity"), "artifact_content_identity"
            ),
            build_inputs=require_mapping(value.get("build_inputs"), "build_inputs"),
            schema_version=version,
        )


def _trim_from_dict(value: Mapping[str, object]) -> TrimEvidence:
    version = require_schema_version(
        value.get("schema_version"),
        expected=TRIM_EVIDENCE_SCHEMA,
        artifact="TrimEvidence",
    )
    return TrimEvidence(
        iteration=require_int(value.get("iteration"), "trim.iteration"),
        removed_node_ids=require_string_tuple(
            value.get("removed_node_ids"), "trim.removed_node_ids"
        ),
        token_count_before=require_int(value.get("token_count_before"), "trim.token_count_before"),
        token_count_after=require_int(value.get("token_count_after"), "trim.token_count_after"),
        reason=require_text(value.get("reason"), "trim.reason"),
        schema_version=version,
    )
