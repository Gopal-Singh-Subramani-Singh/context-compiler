"""Immutable, source-neutral Version-2 context nodes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from contextc.canonical import freeze_value, normalize_text, to_canonical_primitive
from contextc.decoding import (
    optional_string,
    require_mapping,
    require_string,
    require_string_tuple,
    require_text,
)
from contextc.errors import SourceValidationError
from contextc.hashing import normalized_content_hash
from contextc.ir.source import InstructionAuthority, Sensitivity, SourceReference, TrustDomain
from contextc.schema import NODE_SCHEMA, SchemaVersion, require_schema_version


class NodeKind(StrEnum):
    FILE = "file"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    CODE_BLOCK = "code_block"
    DOCUMENT = "document"
    DOCUMENT_SECTION = "document_section"
    MESSAGE = "message"
    CONVERSATION_MESSAGE = "conversation_message"
    RECORD = "record"
    TOOL_RESULT = "tool_result"
    EVENT = "event"
    OBSERVATION = "observation"
    PROCEDURE = "procedure"
    TASK = "task"


@dataclass(frozen=True, slots=True)
class ContextNode:
    """Immutable source facts; task and selection state are intentionally absent.

    CRLF and bare CR newlines normalize to LF. All other characters, including
    trailing spaces and final newlines, participate in the content hash.
    """

    node_id: str
    kind: NodeKind
    content: str
    normalized_content_hash: str
    source: SourceReference
    created_at: str | None = None
    trust_domain: TrustDomain = TrustDomain.LOCAL_REPOSITORY
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    instruction_authority: InstructionAuthority = InstructionAuthority.NONE
    transformations: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
    schema_version: SchemaVersion = NODE_SCHEMA

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, str) or not self.node_id:
            raise SourceValidationError("node_id must not be empty")
        if not isinstance(self.kind, NodeKind):
            raise SourceValidationError("node kind must be a NodeKind")
        if not isinstance(self.content, str) or not isinstance(self.normalized_content_hash, str):
            raise SourceValidationError("node content and hash must be strings")
        if not isinstance(self.source, SourceReference):
            raise SourceValidationError("node source must be a SourceReference")
        if self.created_at is not None and not isinstance(self.created_at, str):
            raise SourceValidationError("node created_at must be a string or null")
        if not isinstance(self.trust_domain, TrustDomain):
            raise SourceValidationError("node trust_domain must be a TrustDomain")
        if not isinstance(self.sensitivity, Sensitivity):
            raise SourceValidationError("node sensitivity must be a Sensitivity")
        if not isinstance(self.instruction_authority, InstructionAuthority):
            raise SourceValidationError(
                "node instruction_authority must be an InstructionAuthority"
            )
        require_schema_version(
            self.schema_version,
            expected=NODE_SCHEMA,
            artifact="ContextNode",
        )
        normalized = normalize_text(self.content)
        if self.content != normalized:
            object.__setattr__(self, "content", normalized)
        if self.normalized_content_hash != normalized_content_hash(normalized):
            raise SourceValidationError("normalized_content_hash does not match content")
        if any(not isinstance(item, str) or not item for item in self.transformations):
            raise SourceValidationError("transformations must not contain empty identifiers")
        object.__setattr__(self, "transformations", tuple(self.transformations))
        frozen_metadata = freeze_value(self.metadata)
        if not isinstance(frozen_metadata, Mapping):
            raise SourceValidationError("metadata must be a mapping")
        object.__setattr__(self, "metadata", frozen_metadata)

    @classmethod
    def create(
        cls,
        *,
        node_id: str,
        kind: NodeKind,
        content: str,
        source: SourceReference,
        created_at: str | None = None,
        trust_domain: TrustDomain = TrustDomain.LOCAL_REPOSITORY,
        sensitivity: Sensitivity = Sensitivity.INTERNAL,
        instruction_authority: InstructionAuthority = InstructionAuthority.NONE,
        transformations: tuple[str, ...] = (),
        metadata: Mapping[str, object] | None = None,
    ) -> ContextNode:
        """Construct a node while deriving its normalized content identity."""

        normalized = normalize_text(content)
        return cls(
            node_id=node_id,
            kind=kind,
            content=normalized,
            normalized_content_hash=normalized_content_hash(normalized),
            source=source,
            created_at=created_at,
            trust_domain=trust_domain,
            sensitivity=sensitivity,
            instruction_authority=instruction_authority,
            transformations=transformations,
            metadata={} if metadata is None else metadata,
        )

    def to_dict(self) -> dict[str, object]:
        primitive = to_canonical_primitive(self)
        if not isinstance(primitive, dict):
            raise AssertionError("context node did not canonicalize to an object")
        return primitive

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ContextNode:
        version = require_schema_version(
            value.get("schema_version"), expected=NODE_SCHEMA, artifact="ContextNode"
        )
        source_value = require_mapping(value.get("source"), "node.source")
        metadata = require_mapping(value.get("metadata"), "node.metadata")
        try:
            kind = NodeKind(require_string(value.get("kind"), "node.kind"))
            trust_domain = TrustDomain(
                require_string(value.get("trust_domain"), "node.trust_domain")
            )
            sensitivity = Sensitivity(require_string(value.get("sensitivity"), "node.sensitivity"))
            authority = InstructionAuthority(
                require_string(value.get("instruction_authority"), "node.instruction_authority")
            )
        except ValueError as error:
            raise SourceValidationError(f"unsupported ContextNode enum value: {error}") from error
        return cls(
            node_id=require_string(value.get("node_id"), "node.node_id"),
            kind=kind,
            content=require_text(value.get("content"), "node.content"),
            normalized_content_hash=require_string(
                value.get("normalized_content_hash"), "node.normalized_content_hash"
            ),
            source=SourceReference.from_dict(source_value),
            created_at=optional_string(value.get("created_at"), "node.created_at"),
            trust_domain=trust_domain,
            sensitivity=sensitivity,
            instruction_authority=authority,
            transformations=require_string_tuple(
                value.get("transformations"), "node.transformations"
            ),
            metadata=metadata,
            schema_version=version,
        )
