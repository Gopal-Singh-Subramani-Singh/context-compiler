"""Strict helpers for explicit semantic-artifact deserialization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from contextc.errors import SourceValidationError


def require_mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise SourceValidationError(f"{field} must be an object with string keys")
    return value


def require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise SourceValidationError(f"{field} must be a non-empty string")
    return value


def require_text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise SourceValidationError(f"{field} must be a string")
    return value


def optional_string(value: object, field: str) -> str | None:
    if value is None:
        return None
    return require_string(value, field)


def optional_int(value: object, field: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise SourceValidationError(f"{field} must be an integer or null")
    return value


def require_int(value: object, field: str) -> int:
    parsed = optional_int(value, field)
    if parsed is None:
        raise SourceValidationError(f"{field} must be an integer")
    return parsed


def require_float(value: object, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise SourceValidationError(f"{field} must be numeric")
    return float(value)


def require_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise SourceValidationError(f"{field} must be a boolean")
    return value


def require_sequence(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise SourceValidationError(f"{field} must be an array")
    return value


def require_string_tuple(value: object, field: str) -> tuple[str, ...]:
    sequence = require_sequence(value, field)
    if not all(isinstance(item, str) and item for item in sequence):
        raise SourceValidationError(f"{field} must contain non-empty strings")
    return tuple(sequence)  # type: ignore[arg-type]
