"""Explicit schema-version contracts for semantic artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from contextc.errors import SchemaVersionError, SourceValidationError


@dataclass(frozen=True, slots=True, order=True)
class SchemaVersion:
    """A semantic schema version with independently validated major/minor parts."""

    major: int
    minor: int = 0

    def __post_init__(self) -> None:
        if self.major < 1:
            raise SourceValidationError("schema major version must be positive")
        if self.minor < 0:
            raise SourceValidationError("schema minor version must not be negative")

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> SchemaVersion:
        """Parse the structured representation without legacy coercion."""

        if set(value) != {"major", "minor"}:
            raise SchemaVersionError("malformed schema version object")
        major = value["major"]
        minor = value["minor"]
        if (
            not isinstance(major, int)
            or isinstance(major, bool)
            or not isinstance(minor, int)
            or isinstance(minor, bool)
        ):
            raise SchemaVersionError("schema major and minor versions must be integers")
        try:
            return cls(major=major, minor=minor)
        except SourceValidationError as error:
            raise SchemaVersionError(str(error)) from error


def require_schema_version(
    value: object,
    *,
    expected: SchemaVersion,
    artifact: str,
    compatible_minors: frozenset[int] = frozenset(),
) -> SchemaVersion:
    """Validate an artifact version using an explicit compatibility allowlist."""

    if isinstance(value, SchemaVersion):
        parsed = value
    elif isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise SchemaVersionError(f"malformed {artifact} schema version")
        parsed = SchemaVersion.from_dict(value)
    else:
        raise SchemaVersionError(f"malformed {artifact} schema version")
    if parsed.major != expected.major:
        raise SchemaVersionError(
            f"unsupported {artifact} schema major {parsed.major}; expected {expected.major}"
        )
    allowed_minors = compatible_minors | {expected.minor}
    if parsed.minor not in allowed_minors:
        raise SchemaVersionError(
            f"unsupported {artifact} schema minor {parsed.minor}; "
            f"explicitly supported: {sorted(allowed_minors)}"
        )
    return parsed


def migrate_legacy_major_version(value: object) -> SchemaVersion:
    """Explicitly migrate the M1 integer-major representation to major.minor."""

    if not isinstance(value, int) or isinstance(value, bool):
        raise SchemaVersionError("legacy schema version must be an integer major")
    try:
        return SchemaVersion(major=value, minor=0)
    except SourceValidationError as error:
        raise SchemaVersionError(str(error)) from error


SOURCE_SCHEMA = SchemaVersion(1, 0)
NODE_SCHEMA = SchemaVersion(2, 0)
ANALYSIS_SCHEMA = SchemaVersion(1, 0)
EDGE_SCHEMA = SchemaVersion(1, 0)
GRAPH_SCHEMA = SchemaVersion(1, 0)
COMPILATION_SCHEMA = SchemaVersion(1, 1)
SELECTION_SCHEMA = SchemaVersion(1, 1)
DIAGNOSTIC_SCHEMA = SchemaVersion(1, 0)
COMPILED_CONTEXT_SCHEMA = SchemaVersion(1, 0)
EXPLANATION_SCHEMA = SchemaVersion(1, 0)
SERIALIZATION_SCHEMA = SchemaVersion(1, 0)
TOKENIZER_IDENTITY_SCHEMA = SchemaVersion(1, 0)
SOURCE_MAP_SCHEMA = SchemaVersion(1, 0)
TRIM_EVIDENCE_SCHEMA = SchemaVersion(1, 0)
BUDGET_EVIDENCE_SCHEMA = SchemaVersion(1, 0)
RENDERED_CONTEXT_SCHEMA = SchemaVersion(1, 0)
TARGET_MANIFEST_FIELDS_SCHEMA = SchemaVersion(1, 0)
BUILD_MANIFEST_SCHEMA = SchemaVersion(1, 4)
OBJECTIVE_WEIGHTS_SCHEMA = SchemaVersion(1, 0)
OPTIMIZER_CONFIGURATION_SCHEMA = SchemaVersion(1, 0)
GROUND_TRUTH_SCHEMA = SchemaVersion(1, 0)
BENCHMARK_METRICS_SCHEMA = SchemaVersion(1, 0)
BENCHMARK_RUN_SCHEMA = SchemaVersion(1, 0)
TOP_K_TRACE_SCHEMA = SchemaVersion(1, 0)
CASE_STUDY_PUBLIC_TASK_SCHEMA = SchemaVersion(1, 0)
CASE_STUDY_LABELS_SCHEMA = SchemaVersion(1, 0)
CASE_STUDY_REVIEW_SCHEMA = SchemaVersion(1, 0)
CASE_STUDY_REPORT_SCHEMA = SchemaVersion(1, 0)
