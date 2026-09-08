"""Task-specific analysis values kept separate from source IR."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

from contextc.canonical import freeze_value, to_canonical_primitive
from contextc.decoding import (
    require_bool,
    require_float,
    require_mapping,
    require_string,
)
from contextc.errors import SourceValidationError
from contextc.schema import ANALYSIS_SCHEMA, SchemaVersion, require_schema_version


@dataclass(frozen=True, slots=True)
class NodeAnalysis:
    """Immutable task analysis for one reusable source node."""

    node_id: str
    relevance: float = 0.0
    trust_score: float = 0.0
    freshness: float = 0.0
    security_risk: float = 0.0
    redundancy_score: float = 0.0
    token_counts: Mapping[str, int] = field(default_factory=dict)
    mandatory: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)
    schema_version: SchemaVersion = ANALYSIS_SCHEMA

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, str) or not self.node_id:
            raise SourceValidationError("analysis node_id must not be empty")
        scores = {
            "relevance": self.relevance,
            "trust_score": self.trust_score,
            "freshness": self.freshness,
            "security_risk": self.security_risk,
            "redundancy_score": self.redundancy_score,
        }
        for name, score in scores.items():
            if (
                not isinstance(score, (int, float))
                or isinstance(score, bool)
                or not math.isfinite(score)
                or not 0.0 <= score <= 1.0
            ):
                raise SourceValidationError(f"analysis {name} must be finite and within [0, 1]")
        if not isinstance(self.token_counts, Mapping):
            raise SourceValidationError("token_counts must be a mapping")
        for key, count in self.token_counts.items():
            if not key:
                raise SourceValidationError("token count keys must not be empty")
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise SourceValidationError("token counts must be non-negative integers")
        if not isinstance(self.mandatory, bool):
            raise SourceValidationError("analysis mandatory must be a boolean")
        require_schema_version(
            self.schema_version,
            expected=ANALYSIS_SCHEMA,
            artifact="NodeAnalysis",
        )
        frozen_counts = freeze_value(dict(self.token_counts))
        frozen_metadata = freeze_value(self.metadata)
        if not isinstance(frozen_counts, Mapping) or not isinstance(frozen_metadata, Mapping):
            raise SourceValidationError("analysis maps must be mappings")
        object.__setattr__(self, "token_counts", frozen_counts)
        object.__setattr__(self, "metadata", frozen_metadata)

    def to_dict(self) -> dict[str, object]:
        primitive = to_canonical_primitive(self)
        if not isinstance(primitive, dict):
            raise AssertionError("node analysis did not canonicalize to an object")
        return primitive

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> NodeAnalysis:
        version = require_schema_version(
            value.get("schema_version"), expected=ANALYSIS_SCHEMA, artifact="NodeAnalysis"
        )
        raw_counts = require_mapping(value.get("token_counts"), "analysis.token_counts")
        token_counts: dict[str, int] = {}
        for key, count in raw_counts.items():
            if not isinstance(count, int) or isinstance(count, bool):
                raise SourceValidationError("analysis token counts must be integers")
            token_counts[key] = count
        return cls(
            node_id=require_string(value.get("node_id"), "analysis.node_id"),
            relevance=require_float(value.get("relevance"), "analysis.relevance"),
            trust_score=require_float(value.get("trust_score"), "analysis.trust_score"),
            freshness=require_float(value.get("freshness"), "analysis.freshness"),
            security_risk=require_float(value.get("security_risk"), "analysis.security_risk"),
            redundancy_score=require_float(
                value.get("redundancy_score"), "analysis.redundancy_score"
            ),
            token_counts=token_counts,
            mandatory=require_bool(value.get("mandatory"), "analysis.mandatory"),
            metadata=require_mapping(value.get("metadata"), "analysis.metadata"),
            schema_version=version,
        )
