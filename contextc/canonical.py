"""Deterministic semantic conversion and JSON encoding."""

from __future__ import annotations

import dataclasses
import json
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum
from types import MappingProxyType
from typing import TypeAlias

from contextc.errors import CanonicalizationError

FrozenValue: TypeAlias = object


def normalize_text(value: str) -> str:
    """Normalize all common newline spellings to LF."""

    return value.replace("\r\n", "\n").replace("\r", "\n")


def freeze_value(value: object) -> FrozenValue:
    """Return a recursively immutable copy suitable for source facts."""

    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError("immutable mapping keys must be strings")
            frozen[key] = freeze_value(item)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(freeze_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((freeze_value(item) for item in value), key=canonical_json_bytes))
    if value is None or isinstance(value, (str, int, float, bool, Enum)):
        return value
    raise CanonicalizationError(f"unsupported immutable value: {type(value).__name__}")


def _mapping_to_primitive(value: Mapping[object, object]) -> dict[str, object]:
    primitive: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise CanonicalizationError("canonical mapping keys must be strings")
        primitive[key] = to_canonical_primitive(item)
    return primitive


def to_canonical_primitive(value: object) -> object:
    """Convert supported values into deterministic JSON primitives."""

    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalizationError("NaN and infinity are not canonical")
        return value
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise CanonicalizationError("naive datetimes are not canonical")
        normalized = value.astimezone(UTC).isoformat(timespec="microseconds")
        return normalized.replace("+00:00", "Z")
    if isinstance(value, Enum):
        return to_canonical_primitive(value.value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_canonical_primitive(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return _mapping_to_primitive(value)
    if isinstance(value, (list, tuple)):
        return [to_canonical_primitive(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [to_canonical_primitive(item) for item in value]
        return sorted(items, key=canonical_json_bytes)
    raise CanonicalizationError(f"unsupported canonical value: {type(value).__name__}")


def canonical_json_bytes(value: object) -> bytes:
    """Serialize semantic data as canonical UTF-8 JSON bytes."""

    primitive = to_canonical_primitive(value)
    try:
        encoded = json.dumps(
            primitive,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise CanonicalizationError(str(error)) from error
    return encoded.encode("utf-8")


def canonical_json_text(value: object) -> str:
    """Return canonical semantic JSON as text."""

    return canonical_json_bytes(value).decode("utf-8")
