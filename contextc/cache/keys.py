"""Typed semantic computation keys for M8."""

from __future__ import annotations

from dataclasses import dataclass

from contextc.canonical import canonical_json_bytes
from contextc.hashing import semantic_hash

CACHE_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ComputationKey:
    namespace: str
    stage: str
    semantic_input_identity: str
    cache_schema_version: int = CACHE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.namespace or not self.stage or not self.semantic_input_identity:
            raise ValueError("cache computation key fields must not be empty")
        if self.cache_schema_version < 1:
            raise ValueError("cache schema version must be positive")

    @property
    def identity(self) -> str:
        return semantic_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "namespace": self.namespace,
            "stage": self.stage,
            "cache_schema_version": self.cache_schema_version,
            "semantic_input_identity": self.semantic_input_identity,
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())
