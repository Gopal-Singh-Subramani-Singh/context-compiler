"""Immutable source references and stable source classifications."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from contextc.canonical import to_canonical_primitive
from contextc.decoding import optional_int, optional_string, require_string
from contextc.errors import SourceValidationError
from contextc.schema import SOURCE_SCHEMA, SchemaVersion, require_schema_version


class TrustDomain(StrEnum):
    SYSTEM_POLICY = "system_policy"
    DEVELOPER_INSTRUCTION = "developer_instruction"
    USER_INSTRUCTION = "user_instruction"
    LOCAL_REPOSITORY = "local_repository"
    RETRIEVED_DOCUMENT = "retrieved_document"
    CONVERSATION_HISTORY = "conversation_history"
    VERIFIED_TOOL = "verified_tool"
    UNVERIFIED_TOOL = "unverified_tool"
    EXTERNAL_CONTENT = "external_content"
    MODEL_GENERATED = "model_generated"


class Sensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    SECRET = "secret"


class InstructionAuthority(StrEnum):
    NONE = "none"
    USER = "user"
    DEVELOPER = "developer"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class SourceReference:
    """A stable location inside a retained source revision."""

    uri: str
    revision: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    start_byte: int | None = None
    end_byte: int | None = None
    language: str | None = None
    schema_version: SchemaVersion = SOURCE_SCHEMA

    def __post_init__(self) -> None:
        if not isinstance(self.uri, str) or not self.uri:
            raise SourceValidationError("source URI must not be empty")
        for name, value in (("revision", self.revision), ("language", self.language)):
            if value is not None and (not isinstance(value, str) or not value):
                raise SourceValidationError(f"source {name} must be a non-empty string or null")
        self._validate_range("line", self.start_line, self.end_line, minimum=1)
        self._validate_range("byte", self.start_byte, self.end_byte, minimum=0)
        require_schema_version(
            self.schema_version,
            expected=SOURCE_SCHEMA,
            artifact="SourceReference",
        )

    @staticmethod
    def _validate_range(label: str, start: int | None, end: int | None, *, minimum: int) -> None:
        for value in (start, end):
            if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
                raise SourceValidationError(f"{label} range values must be integers")
        if (start is None) != (end is None):
            raise SourceValidationError(f"{label} range requires both start and end")
        if start is not None and end is not None:
            if start < minimum or end < minimum:
                raise SourceValidationError(f"{label} range is below {minimum}")
            if end < start:
                raise SourceValidationError(f"{label} range end precedes start")

    def to_dict(self) -> dict[str, object]:
        primitive = to_canonical_primitive(self)
        if not isinstance(primitive, dict):
            raise AssertionError("source reference did not canonicalize to an object")
        return primitive

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> SourceReference:
        version = require_schema_version(
            value.get("schema_version"),
            expected=SOURCE_SCHEMA,
            artifact="SourceReference",
        )
        return cls(
            uri=require_string(value.get("uri"), "source.uri"),
            revision=optional_string(value.get("revision"), "source.revision"),
            start_line=optional_int(value.get("start_line"), "source.start_line"),
            end_line=optional_int(value.get("end_line"), "source.end_line"),
            start_byte=optional_int(value.get("start_byte"), "source.start_byte"),
            end_byte=optional_int(value.get("end_byte"), "source.end_byte"),
            language=optional_string(value.get("language"), "source.language"),
            schema_version=version,
        )
