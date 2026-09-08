"""Versioned compilation request, selection evidence, and compiled context models."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from contextc.canonical import freeze_value, to_canonical_primitive
from contextc.decoding import (
    optional_string,
    require_float,
    require_int,
    require_mapping,
    require_sequence,
    require_string,
    require_string_tuple,
    require_text,
)
from contextc.diagnostics import Diagnostic
from contextc.errors import SourceValidationError
from contextc.optimization.models import OptimizerConfiguration
from contextc.schema import (
    COMPILATION_SCHEMA,
    COMPILED_CONTEXT_SCHEMA,
    SELECTION_SCHEMA,
    SchemaVersion,
    require_schema_version,
)

_SEMANTIC_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?\Z")


class SelectionStatus(StrEnum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    FEASIBLE_TIMEOUT = "feasible_timeout"
    HEURISTIC = "heuristic"
    FALLBACK = "fallback"
    INFEASIBLE = "infeasible"


@dataclass(frozen=True, slots=True)
class CompilationUnit:
    """Immutable semantic inputs for one compilation request."""

    task_id: str
    task_description: str
    target_id: str
    tokenizer_id: str
    token_budget: int
    policy_id: str
    time_anchor: datetime
    random_seed: int
    compiler_version: str
    pipeline_config_hash: str
    source_revision: str | None = None
    optimizer: OptimizerConfiguration = field(default_factory=OptimizerConfiguration)
    schema_version: SchemaVersion = COMPILATION_SCHEMA

    def __post_init__(self) -> None:
        identifiers = {
            "task_id": self.task_id,
            "task_description": self.task_description,
            "target_id": self.target_id,
            "tokenizer_id": self.tokenizer_id,
            "policy_id": self.policy_id,
        }
        for name, value in identifiers.items():
            if not value:
                raise SourceValidationError(f"compilation {name} must not be empty")
        if not isinstance(self.token_budget, int) or isinstance(self.token_budget, bool):
            raise SourceValidationError("compilation token_budget must be an integer")
        if self.token_budget <= 0:
            raise SourceValidationError("compilation token_budget must be positive")
        if not isinstance(self.random_seed, int) or isinstance(self.random_seed, bool):
            raise SourceValidationError("compilation random_seed must be an integer")
        if not isinstance(self.time_anchor, datetime):
            raise SourceValidationError("compilation time_anchor must be a datetime")
        if self.time_anchor.tzinfo is None or self.time_anchor.utcoffset() is None:
            raise SourceValidationError("compilation time_anchor must be timezone-aware")
        object.__setattr__(self, "time_anchor", self.time_anchor.astimezone(UTC))
        if not _VERSION.fullmatch(self.compiler_version):
            raise SourceValidationError("compiler_version must be a semantic version")
        if not _SEMANTIC_HASH.fullmatch(self.pipeline_config_hash):
            raise SourceValidationError("pipeline_config_hash must be a SHA-256 identity")
        if not isinstance(self.optimizer, OptimizerConfiguration):
            raise SourceValidationError("compilation optimizer must be OptimizerConfiguration")
        require_schema_version(
            self.schema_version,
            expected=COMPILATION_SCHEMA,
            artifact="CompilationUnit",
        )

    def to_dict(self) -> dict[str, object]:
        primitive = to_canonical_primitive(self)
        if not isinstance(primitive, dict):
            raise AssertionError("compilation unit did not canonicalize to an object")
        return primitive

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> CompilationUnit:
        version = require_schema_version(
            value.get("schema_version"),
            expected=COMPILATION_SCHEMA,
            artifact="CompilationUnit",
        )
        raw_anchor = require_string(value.get("time_anchor"), "compilation.time_anchor")
        try:
            anchor = datetime.fromisoformat(raw_anchor.replace("Z", "+00:00"))
        except ValueError as error:
            raise SourceValidationError("compilation time_anchor is not ISO-8601") from error
        return cls(
            task_id=require_string(value.get("task_id"), "compilation.task_id"),
            task_description=require_string(
                value.get("task_description"), "compilation.task_description"
            ),
            target_id=require_string(value.get("target_id"), "compilation.target_id"),
            tokenizer_id=require_string(value.get("tokenizer_id"), "compilation.tokenizer_id"),
            token_budget=require_int(value.get("token_budget"), "compilation.token_budget"),
            policy_id=require_string(value.get("policy_id"), "compilation.policy_id"),
            time_anchor=anchor,
            random_seed=require_int(value.get("random_seed"), "compilation.random_seed"),
            compiler_version=require_string(
                value.get("compiler_version"), "compilation.compiler_version"
            ),
            pipeline_config_hash=require_string(
                value.get("pipeline_config_hash"), "compilation.pipeline_config_hash"
            ),
            source_revision=optional_string(
                value.get("source_revision"), "compilation.source_revision"
            ),
            optimizer=OptimizerConfiguration.from_dict(
                require_mapping(value.get("optimizer"), "compilation.optimizer")
            ),
            schema_version=version,
        )


@dataclass(frozen=True, slots=True)
class SelectionResult:
    """Immutable final selection state and stored decision evidence."""

    selected_node_ids: tuple[str, ...]
    excluded_node_ids: tuple[str, ...] = ()
    dependency_forced_node_ids: tuple[str, ...] = ()
    mandatory_node_ids: tuple[str, ...] = ()
    requested_strategy_id: str = "auto"
    strategy_id: str = "naive"
    strategy_version: str = "2.0.0"
    optimizer_status: SelectionStatus = SelectionStatus.HEURISTIC
    objective_value: float | None = None
    used_tokens: int = 0
    available_tokens: int = 0
    solver_runtime_ms: float = 0.0
    solver_timeout_ms: int | None = None
    fallback_reason: str | None = None
    tie_break_trace: tuple[str, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    excluded_reasons: Mapping[str, str] = field(default_factory=dict)
    schema_version: SchemaVersion = SELECTION_SCHEMA

    def __post_init__(self) -> None:
        tuple_fields = (
            "selected_node_ids",
            "excluded_node_ids",
            "dependency_forced_node_ids",
            "mandatory_node_ids",
            "tie_break_trace",
            "diagnostics",
        )
        for name in tuple_fields:
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if not isinstance(self.optimizer_status, SelectionStatus):
            raise SourceValidationError("selection optimizer_status must be a SelectionStatus")
        if not all(isinstance(item, Diagnostic) for item in self.diagnostics):
            raise SourceValidationError("selection diagnostics must contain Diagnostic values")
        identifier_fields = (
            self.selected_node_ids,
            self.excluded_node_ids,
            self.dependency_forced_node_ids,
            self.mandatory_node_ids,
        )
        for values in identifier_fields:
            if any(not node_id for node_id in values) or len(values) != len(set(values)):
                raise SourceValidationError(
                    "selection node identifiers must be non-empty and unique within each field"
                )
        selected = set(self.selected_node_ids)
        excluded = set(self.excluded_node_ids)
        if selected & excluded:
            raise SourceValidationError("selected and excluded node identifiers must be disjoint")
        if not set(self.dependency_forced_node_ids) <= selected:
            raise SourceValidationError("dependency-forced nodes must be selected")
        if (
            self.optimizer_status is not SelectionStatus.INFEASIBLE
            and not set(self.mandatory_node_ids) <= selected
        ):
            raise SourceValidationError("mandatory nodes must be selected")
        if (
            not self.requested_strategy_id
            or not self.strategy_id
            or not _VERSION.fullmatch(self.strategy_version)
        ):
            raise SourceValidationError("selection strategy identity/version is invalid")
        if self.objective_value is not None and not math.isfinite(self.objective_value):
            raise SourceValidationError("selection objective value must be finite")
        for name, count in (
            ("used_tokens", self.used_tokens),
            ("available_tokens", self.available_tokens),
        ):
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise SourceValidationError(f"selection {name} must be a non-negative integer")
        if (
            not isinstance(self.solver_runtime_ms, (int, float))
            or isinstance(self.solver_runtime_ms, bool)
            or not math.isfinite(self.solver_runtime_ms)
            or self.solver_runtime_ms < 0
        ):
            raise SourceValidationError(
                "selection solver_runtime_ms must be finite and non-negative"
            )
        if self.solver_timeout_ms is not None and (
            not isinstance(self.solver_timeout_ms, int)
            or isinstance(self.solver_timeout_ms, bool)
            or self.solver_timeout_ms < 1
        ):
            raise SourceValidationError("selection solver_timeout_ms must be positive or null")
        frozen_reasons = freeze_value(self.excluded_reasons)
        if not isinstance(frozen_reasons, Mapping):
            raise SourceValidationError("selection excluded reasons must be a mapping")
        if not all(isinstance(value, str) for value in frozen_reasons.values()):
            raise SourceValidationError("selection excluded reasons must be strings")
        require_schema_version(
            self.schema_version,
            expected=SELECTION_SCHEMA,
            artifact="SelectionResult",
        )
        object.__setattr__(self, "excluded_reasons", frozen_reasons)

    @property
    def strategy(self) -> str:
        """M1-compatible strategy accessor."""

        return self.strategy_id

    @property
    def runtime_evidence(self) -> Mapping[str, object]:
        """Compatibility view over the explicit M5 solver evidence fields."""

        return freeze_value(
            {
                "runtime_ms": self.solver_runtime_ms,
                "timed_out": self.optimizer_status is SelectionStatus.FEASIBLE_TIMEOUT,
                "timeout_ms": self.solver_timeout_ms,
            }
        )  # type: ignore[return-value]

    def to_dict(self) -> dict[str, object]:
        primitive = to_canonical_primitive(self)
        if not isinstance(primitive, dict):
            raise AssertionError("selection result did not canonicalize to an object")
        return primitive

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> SelectionResult:
        version = require_schema_version(
            value.get("schema_version"),
            expected=SELECTION_SCHEMA,
            artifact="SelectionResult",
        )
        raw_status = require_string(value.get("optimizer_status"), "selection.optimizer_status")
        try:
            status = SelectionStatus(raw_status)
        except ValueError as error:
            raise SourceValidationError(f"unknown selection status: {raw_status}") from error
        raw_objective = value.get("objective_value")
        objective = (
            None
            if raw_objective is None
            else require_float(raw_objective, "selection.objective_value")
        )
        raw_diagnostics = require_sequence(value.get("diagnostics"), "selection.diagnostics")
        diagnostics = tuple(
            Diagnostic.from_dict(require_mapping(item, "selection.diagnostic"))
            for item in raw_diagnostics
        )
        raw_reasons = require_mapping(value.get("excluded_reasons"), "selection.excluded_reasons")
        reasons: dict[str, str] = {}
        for node_id, reason in raw_reasons.items():
            reasons[node_id] = require_string(reason, "selection.excluded_reason")
        return cls(
            selected_node_ids=require_string_tuple(
                value.get("selected_node_ids"), "selection.selected_node_ids"
            ),
            excluded_node_ids=require_string_tuple(
                value.get("excluded_node_ids"), "selection.excluded_node_ids"
            ),
            dependency_forced_node_ids=require_string_tuple(
                value.get("dependency_forced_node_ids"),
                "selection.dependency_forced_node_ids",
            ),
            mandatory_node_ids=require_string_tuple(
                value.get("mandatory_node_ids"), "selection.mandatory_node_ids"
            ),
            requested_strategy_id=require_string(
                value.get("requested_strategy_id"), "selection.requested_strategy_id"
            ),
            strategy_id=require_string(value.get("strategy_id"), "selection.strategy_id"),
            strategy_version=require_string(
                value.get("strategy_version"), "selection.strategy_version"
            ),
            optimizer_status=status,
            objective_value=objective,
            used_tokens=require_int(value.get("used_tokens"), "selection.used_tokens"),
            available_tokens=require_int(
                value.get("available_tokens"), "selection.available_tokens"
            ),
            solver_runtime_ms=require_float(
                value.get("solver_runtime_ms"), "selection.solver_runtime_ms"
            ),
            solver_timeout_ms=(
                None
                if value.get("solver_timeout_ms") is None
                else require_int(value.get("solver_timeout_ms"), "selection.solver_timeout_ms")
            ),
            fallback_reason=optional_string(
                value.get("fallback_reason"), "selection.fallback_reason"
            ),
            tie_break_trace=require_string_tuple(
                value.get("tie_break_trace"), "selection.tie_break_trace"
            ),
            diagnostics=diagnostics,
            excluded_reasons=reasons,
            schema_version=version,
        )


@dataclass(frozen=True, slots=True)
class CompiledContext:
    rendered_text: str
    selection: SelectionResult
    semantic_hash: str
    schema_version: SchemaVersion = COMPILED_CONTEXT_SCHEMA

    def __post_init__(self) -> None:
        if not _SEMANTIC_HASH.fullmatch(self.semantic_hash):
            raise SourceValidationError("compiled semantic_hash must be a SHA-256 identity")
        require_schema_version(
            self.schema_version,
            expected=COMPILED_CONTEXT_SCHEMA,
            artifact="CompiledContext",
        )

    def to_dict(self) -> dict[str, object]:
        primitive = to_canonical_primitive(self)
        if not isinstance(primitive, dict):
            raise AssertionError("compiled context did not canonicalize to an object")
        return primitive

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> CompiledContext:
        version = require_schema_version(
            value.get("schema_version"),
            expected=COMPILED_CONTEXT_SCHEMA,
            artifact="CompiledContext",
        )
        return cls(
            rendered_text=require_text(
                value.get("rendered_text"), "compiled_context.rendered_text"
            ),
            selection=SelectionResult.from_dict(
                require_mapping(value.get("selection"), "compiled_context.selection")
            ),
            semantic_hash=require_string(
                value.get("semantic_hash"), "compiled_context.semantic_hash"
            ),
            schema_version=version,
        )
