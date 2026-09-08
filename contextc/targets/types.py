"""Immutable target-lowering requests and exact rendered evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from contextc.diagnostics import Diagnostic
from contextc.errors import SourceValidationError
from contextc.ir.compilation import CompilationUnit, SelectionResult
from contextc.ir.graph import ContextGraph
from contextc.schema import (
    BUDGET_EVIDENCE_SCHEMA,
    RENDERED_CONTEXT_SCHEMA,
    SOURCE_MAP_SCHEMA,
    TARGET_MANIFEST_FIELDS_SCHEMA,
    TRIM_EVIDENCE_SCHEMA,
    SchemaVersion,
    require_schema_version,
)
from contextc.tokenizers.types import TokenizerIdentity


class TargetId(StrEnum):
    GENERIC = "generic"
    QWEN = "qwen"
    LLAMA = "llama"
    STRUCTURED_JSON = "structured-json"


@dataclass(frozen=True, slots=True)
class TargetRenderRequest:
    graph: ContextGraph
    selection: SelectionResult
    compilation: CompilationUnit
    system_instruction: str = ""
    developer_instruction: str = ""
    user_instruction: str = ""
    policy_instruction: str = ""
    tool_schema_text: str = ""
    add_generation_prompt: bool = True
    blocked_node_ids: tuple[str, ...] = ()
    max_trim_iterations: int = 10_000

    def __post_init__(self) -> None:
        object.__setattr__(self, "blocked_node_ids", tuple(self.blocked_node_ids))
        if len(self.blocked_node_ids) != len(set(self.blocked_node_ids)):
            raise SourceValidationError("blocked node identifiers must be unique")
        if self.max_trim_iterations < 1:
            raise SourceValidationError("max trim iterations must be positive")


@dataclass(frozen=True, slots=True)
class SourceMapEntry:
    output_start_char: int
    output_end_char: int
    compiler_generated: bool
    node_id: str | None = None
    source_uri: str | None = None
    source_start_line: int | None = None
    source_end_line: int | None = None
    transformations: tuple[str, ...] = ()
    schema_version: SchemaVersion = SOURCE_MAP_SCHEMA

    def __post_init__(self) -> None:
        if self.output_start_char < 0 or self.output_end_char <= self.output_start_char:
            raise SourceValidationError("source-map output span must be non-empty and ordered")
        if self.compiler_generated:
            if self.node_id is not None or self.source_uri is not None:
                raise SourceValidationError("compiler-generated spans cannot claim source nodes")
        elif not self.node_id or not self.source_uri:
            raise SourceValidationError("source spans require node and source identifiers")
        object.__setattr__(self, "transformations", tuple(self.transformations))
        require_schema_version(
            self.schema_version,
            expected=SOURCE_MAP_SCHEMA,
            artifact="SourceMapEntry",
        )


@dataclass(frozen=True, slots=True)
class TrimEvidence:
    iteration: int
    removed_node_ids: tuple[str, ...]
    token_count_before: int
    token_count_after: int
    reason: str = "exact_final_budget_overflow"
    schema_version: SchemaVersion = TRIM_EVIDENCE_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "removed_node_ids", tuple(self.removed_node_ids))
        if self.iteration < 1 or not self.removed_node_ids:
            raise SourceValidationError("trim evidence requires an iteration and removed nodes")
        if min(self.token_count_before, self.token_count_after) < 0:
            raise SourceValidationError("trim token counts must not be negative")
        if not self.reason:
            raise SourceValidationError("trim reason must not be empty")
        require_schema_version(
            self.schema_version,
            expected=TRIM_EVIDENCE_SCHEMA,
            artifact="TrimEvidence",
        )


@dataclass(frozen=True, slots=True)
class TokenBudgetEvidence:
    configured_budget: int
    fixed_overhead_tokens: int
    source_allowance_tokens: int
    pre_trim_selected_tokens: int
    final_token_count: int
    schema_version: SchemaVersion = BUDGET_EVIDENCE_SCHEMA

    def __post_init__(self) -> None:
        values = (
            self.configured_budget,
            self.fixed_overhead_tokens,
            self.source_allowance_tokens,
            self.pre_trim_selected_tokens,
            self.final_token_count,
        )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values
        ):
            raise SourceValidationError("budget evidence counts must be non-negative integers")
        if self.source_allowance_tokens != max(
            0, self.configured_budget - self.fixed_overhead_tokens
        ):
            raise SourceValidationError("source allowance does not match budget minus overhead")
        if self.final_token_count > self.configured_budget:
            raise SourceValidationError("successful final target exceeds configured budget")
        require_schema_version(
            self.schema_version,
            expected=BUDGET_EVIDENCE_SCHEMA,
            artifact="TokenBudgetEvidence",
        )


@dataclass(frozen=True, slots=True)
class RenderedContext:
    target_id: TargetId
    rendered_text: str
    exact_token_count: int
    ordered_node_ids: tuple[str, ...]
    source_map: tuple[SourceMapEntry, ...]
    trim_evidence: tuple[TrimEvidence, ...]
    diagnostics: tuple[Diagnostic, ...]
    tokenizer_identity: TokenizerIdentity
    budget_evidence: TokenBudgetEvidence
    schema_version: SchemaVersion = RENDERED_CONTEXT_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "ordered_node_ids", tuple(self.ordered_node_ids))
        object.__setattr__(self, "source_map", tuple(self.source_map))
        object.__setattr__(self, "trim_evidence", tuple(self.trim_evidence))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if self.exact_token_count != self.budget_evidence.final_token_count:
            raise SourceValidationError("rendered and budget token counts disagree")
        if self.tokenizer_identity.target_id != self.target_id.value:
            raise SourceValidationError("rendered target and tokenizer target disagree")
        if len(self.ordered_node_ids) != len(set(self.ordered_node_ids)):
            raise SourceValidationError("rendered node order contains duplicates")
        cursor = 0
        for entry in self.source_map:
            if entry.output_start_char != cursor:
                raise SourceValidationError("source map must be ordered and contiguous")
            cursor = entry.output_end_char
        if cursor != len(self.rendered_text):
            raise SourceValidationError("source map must cover the complete rendered target")
        require_schema_version(
            self.schema_version,
            expected=RENDERED_CONTEXT_SCHEMA,
            artifact="RenderedContext",
        )

    @property
    def rendered_bytes(self) -> bytes:
        return self.rendered_text.encode("utf-8")


@dataclass(frozen=True, slots=True)
class TargetManifestFields:
    target_id: str
    tokenizer_id: str
    tokenizer_version: str
    tokenizer_revision: str | None
    tokenizer_configuration_identity: str
    configured_token_budget: int
    source_allowance_tokens: int
    pre_render_selected_tokens: int
    exact_final_token_count: int
    ordered_node_ids: tuple[str, ...]
    trim_iterations: int
    trim_evidence: tuple[TrimEvidence, ...]
    schema_version: SchemaVersion = TARGET_MANIFEST_FIELDS_SCHEMA

    @classmethod
    def from_rendered(cls, rendered: RenderedContext) -> TargetManifestFields:
        identity = rendered.tokenizer_identity
        return cls(
            target_id=rendered.target_id.value,
            tokenizer_id=identity.tokenizer_id,
            tokenizer_version=identity.tokenizer_version,
            tokenizer_revision=identity.tokenizer_revision,
            tokenizer_configuration_identity=identity.configuration_identity,
            configured_token_budget=rendered.budget_evidence.configured_budget,
            source_allowance_tokens=rendered.budget_evidence.source_allowance_tokens,
            pre_render_selected_tokens=rendered.budget_evidence.pre_trim_selected_tokens,
            exact_final_token_count=rendered.exact_token_count,
            ordered_node_ids=rendered.ordered_node_ids,
            trim_iterations=len(rendered.trim_evidence),
            trim_evidence=rendered.trim_evidence,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "ordered_node_ids", tuple(self.ordered_node_ids))
        object.__setattr__(self, "trim_evidence", tuple(self.trim_evidence))
        if not self.target_id or not self.tokenizer_id or not self.tokenizer_version:
            raise SourceValidationError("target manifest identity fields must not be empty")
        counts = (
            self.configured_token_budget,
            self.source_allowance_tokens,
            self.pre_render_selected_tokens,
            self.exact_final_token_count,
            self.trim_iterations,
        )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counts
        ):
            raise SourceValidationError("target manifest counts must be non-negative integers")
        if self.exact_final_token_count > self.configured_token_budget:
            raise SourceValidationError("target manifest final count exceeds budget")
        if self.source_allowance_tokens > self.configured_token_budget:
            raise SourceValidationError("target manifest allowance exceeds budget")
        if self.trim_iterations != len(self.trim_evidence):
            raise SourceValidationError("target manifest trim count disagrees with evidence")
        require_schema_version(
            self.schema_version,
            expected=TARGET_MANIFEST_FIELDS_SCHEMA,
            artifact="TargetManifestFields",
        )
