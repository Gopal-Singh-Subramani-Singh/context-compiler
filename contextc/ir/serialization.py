"""Versioned canonical serialization and explicit typed deserialization."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import TypeVar

from contextc.canonical import canonical_json_bytes, to_canonical_primitive
from contextc.decoding import require_mapping, require_string
from contextc.errors import SourceValidationError
from contextc.schema import SERIALIZATION_SCHEMA, require_schema_version

T = TypeVar("T")


def serialize_ir(value: object) -> bytes:
    """Serialize one version-bearing IR artifact into a canonical envelope."""

    primitive = to_canonical_primitive(value)
    if not isinstance(primitive, Mapping) or "schema_version" not in primitive:
        raise SourceValidationError("serialized IR value must carry schema_version")
    return canonical_json_bytes(
        {
            "artifact_type": type(value).__name__,
            "schema_version": SERIALIZATION_SCHEMA,
            "value": primitive,
        }
    )


def deserialize_ir(
    payload: bytes,
    *,
    expected_artifact_type: str,
    decoder: Callable[[Mapping[str, object]], T],
) -> T:
    """Decode an envelope only through the caller's explicit artifact decoder."""

    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceValidationError("IR payload is not valid UTF-8 JSON") from error
    envelope = require_mapping(raw, "IR envelope")
    require_schema_version(
        envelope.get("schema_version"),
        expected=SERIALIZATION_SCHEMA,
        artifact="IR serialization envelope",
    )
    artifact_type = require_string(envelope.get("artifact_type"), "IR artifact_type")
    if artifact_type != expected_artifact_type:
        raise SourceValidationError(
            f"IR artifact type {artifact_type!r} does not match {expected_artifact_type!r}"
        )
    return decoder(require_mapping(envelope.get("value"), "IR value"))
