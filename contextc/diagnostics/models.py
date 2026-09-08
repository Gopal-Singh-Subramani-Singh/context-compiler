"""Structured diagnostics emitted by compiler components."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from contextc.canonical import freeze_value, to_canonical_primitive
from contextc.decoding import (
    optional_string,
    require_mapping,
    require_string,
    require_string_tuple,
)
from contextc.diagnostics.codes import DiagnosticCode
from contextc.errors import SourceValidationError
from contextc.schema import DIAGNOSTIC_SCHEMA, SchemaVersion, require_schema_version


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class DiagnosticDefinition:
    code: DiagnosticCode
    title: str
    description: str
    default_severity: Severity
    owning_component: str
    may_continue: bool


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: DiagnosticCode
    severity: Severity
    message: str
    node_ids: tuple[str, ...] = ()
    evidence: Mapping[str, object] = field(default_factory=dict)
    owning_pass: str = "unknown"
    suggested_action: str | None = None
    schema_version: SchemaVersion = DIAGNOSTIC_SCHEMA

    def __post_init__(self) -> None:
        if not self.message:
            raise SourceValidationError("diagnostic message must not be empty")
        if not self.owning_pass:
            raise SourceValidationError("diagnostic owning_pass must not be empty")
        require_schema_version(
            self.schema_version,
            expected=DIAGNOSTIC_SCHEMA,
            artifact="Diagnostic",
        )
        object.__setattr__(self, "node_ids", tuple(self.node_ids))
        frozen = freeze_value(self.evidence)
        if not isinstance(frozen, Mapping):
            raise SourceValidationError("diagnostic evidence must be a mapping")
        object.__setattr__(self, "evidence", frozen)

    def to_dict(self) -> dict[str, object]:
        """Return complete machine-readable diagnostic evidence."""

        primitive = to_canonical_primitive(self)
        if not isinstance(primitive, dict):
            raise AssertionError("diagnostic canonicalization did not produce an object")
        return primitive

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> Diagnostic:
        version = require_schema_version(
            value.get("schema_version"),
            expected=DIAGNOSTIC_SCHEMA,
            artifact="Diagnostic",
        )
        raw_code = require_string(value.get("code"), "diagnostic.code")
        raw_severity = require_string(value.get("severity"), "diagnostic.severity")
        try:
            code = DiagnosticCode(raw_code)
            severity = Severity(raw_severity)
        except ValueError as error:
            raise SourceValidationError(f"unknown diagnostic enum value: {error}") from error
        return cls(
            code=code,
            severity=severity,
            message=require_string(value.get("message"), "diagnostic.message"),
            node_ids=require_string_tuple(value.get("node_ids"), "diagnostic.node_ids"),
            evidence=require_mapping(value.get("evidence"), "diagnostic.evidence"),
            owning_pass=require_string(value.get("owning_pass"), "diagnostic.owning_pass"),
            suggested_action=optional_string(
                value.get("suggested_action"), "diagnostic.suggested_action"
            ),
            schema_version=version,
        )
