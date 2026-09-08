"""Immutable typed graph relationships with deterministic identities."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from contextc.canonical import freeze_value, to_canonical_primitive
from contextc.decoding import require_float, require_mapping, require_string
from contextc.errors import SourceValidationError
from contextc.hashing import semantic_hash
from contextc.schema import EDGE_SCHEMA, SchemaVersion, require_schema_version


class EdgeType(StrEnum):
    IMPORTS = "imports"
    CALLS = "calls"
    DEFINES = "defines"
    REQUIRES = "requires"
    SUPPORTS = "supports"
    CONFLICTS = "conflicts"
    SUPERSEDES = "supersedes"
    DERIVED_FROM = "derived_from"
    TAINTS = "taints"
    ENABLES = "enables"
    REFERENCES = "references"
    CONTRADICTS = "contradicts"
    RESPONDS_TO = "responds_to"
    CAUSES = "causes"
    RESOLVES = "resolves"
    CORRELATES_WITH = "correlates_with"


# Self-edges are rejected for every currently defined relationship. A future
# relationship must opt in explicitly instead of inheriting accidental behavior.
SELF_EDGE_ALLOWED: frozenset[EdgeType] = frozenset()


@dataclass(frozen=True, slots=True)
class ContextEdge:
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType
    confidence: float = 1.0
    evidence: Mapping[str, object] = field(default_factory=dict)
    edge_id: str = ""
    schema_version: SchemaVersion = EDGE_SCHEMA

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_node_id, str)
            or not self.source_node_id
            or not isinstance(self.target_node_id, str)
            or not self.target_node_id
        ):
            raise SourceValidationError("edge endpoints must not be empty")
        if not isinstance(self.edge_type, EdgeType):
            raise SourceValidationError("edge type must be an EdgeType")
        if self.source_node_id == self.target_node_id and self.edge_type not in SELF_EDGE_ALLOWED:
            raise SourceValidationError(f"self-edge is not allowed for {self.edge_type.value}")
        if (
            not isinstance(self.confidence, (int, float))
            or isinstance(self.confidence, bool)
            or not math.isfinite(self.confidence)
            or not 0.0 <= self.confidence <= 1.0
        ):
            raise SourceValidationError("edge confidence must be finite and within [0, 1]")
        require_schema_version(
            self.schema_version,
            expected=EDGE_SCHEMA,
            artifact="ContextEdge",
        )
        frozen_evidence = freeze_value(self.evidence)
        if not isinstance(frozen_evidence, Mapping):
            raise SourceValidationError("edge evidence must be a mapping")
        object.__setattr__(self, "evidence", frozen_evidence)
        expected_id = self.identity_for(
            source_node_id=self.source_node_id,
            target_node_id=self.target_node_id,
            edge_type=self.edge_type,
            confidence=self.confidence,
            evidence=frozen_evidence,
        )
        if self.edge_id and self.edge_id != expected_id:
            raise SourceValidationError("edge_id does not match deterministic edge identity")
        object.__setattr__(self, "edge_id", expected_id)

    @staticmethod
    def identity_for(
        *,
        source_node_id: str,
        target_node_id: str,
        edge_type: EdgeType,
        confidence: float,
        evidence: Mapping[str, object],
    ) -> str:
        digest = semantic_hash(
            {
                "source_node_id": source_node_id,
                "target_node_id": target_node_id,
                "edge_type": edge_type,
                "confidence": confidence,
                "evidence": evidence,
                "schema_version": EDGE_SCHEMA,
            }
        )
        return f"edge-{digest.removeprefix('sha256:')[:24]}"

    def to_dict(self) -> dict[str, object]:
        primitive = to_canonical_primitive(self)
        if not isinstance(primitive, dict):
            raise AssertionError("context edge did not canonicalize to an object")
        return primitive

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ContextEdge:
        version = require_schema_version(
            value.get("schema_version"), expected=EDGE_SCHEMA, artifact="ContextEdge"
        )
        raw_kind = require_string(value.get("edge_type"), "edge.edge_type")
        try:
            edge_type = EdgeType(raw_kind)
        except ValueError as error:
            raise SourceValidationError(f"unknown edge type: {raw_kind}") from error
        return cls(
            source_node_id=require_string(value.get("source_node_id"), "edge.source_node_id"),
            target_node_id=require_string(value.get("target_node_id"), "edge.target_node_id"),
            edge_type=edge_type,
            confidence=require_float(value.get("confidence"), "edge.confidence"),
            evidence=require_mapping(value.get("evidence"), "edge.evidence"),
            edge_id=require_string(value.get("edge_id"), "edge.edge_id"),
            schema_version=version,
        )
