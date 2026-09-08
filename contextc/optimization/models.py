"""Versioned, immutable optimizer configuration and cascade limits."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from contextc.canonical import to_canonical_primitive
from contextc.decoding import (
    require_float,
    require_int,
    require_mapping,
    require_string,
    require_string_tuple,
)
from contextc.errors import SourceValidationError
from contextc.schema import (
    OBJECTIVE_WEIGHTS_SCHEMA,
    OPTIMIZER_CONFIGURATION_SCHEMA,
    SchemaVersion,
    require_schema_version,
)

OPTIMIZER_IDS = (
    "naive",
    "recency",
    "top_k",
    "relevance_greedy",
    "density_greedy",
    "brute_force",
    "dynamic_programming",
    "ilp",
    "graph_closure_greedy",
)
REQUESTED_OPTIMIZER_IDS = ("auto", *OPTIMIZER_IDS)


@dataclass(frozen=True, slots=True)
class ObjectiveWeights:
    """Authoritative M5 objective weights; every component is in [0, 1000]."""

    relevance: float = 1.0
    trust: float = 0.2
    freshness: float = 0.2
    dependency_coverage: float = 0.1
    redundancy_penalty: float = 0.2
    security_risk_penalty: float = 0.5
    schema_version: SchemaVersion = OBJECTIVE_WEIGHTS_SCHEMA

    def __post_init__(self) -> None:
        for name in (
            "relevance",
            "trust",
            "freshness",
            "dependency_coverage",
            "redundancy_penalty",
            "security_risk_penalty",
        ):
            value = getattr(self, name)
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                or not 0.0 <= value <= 1000.0
            ):
                raise SourceValidationError(
                    f"objective weight {name} must be finite and within [0, 1000]"
                )
        require_schema_version(
            self.schema_version,
            expected=OBJECTIVE_WEIGHTS_SCHEMA,
            artifact="ObjectiveWeights",
        )

    def to_dict(self) -> dict[str, object]:
        value = to_canonical_primitive(self)
        if not isinstance(value, dict):
            raise AssertionError("objective weights did not canonicalize to an object")
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ObjectiveWeights:
        version = require_schema_version(
            value.get("schema_version"),
            expected=OBJECTIVE_WEIGHTS_SCHEMA,
            artifact="ObjectiveWeights",
        )
        return cls(
            relevance=require_float(value.get("relevance"), "objective.relevance"),
            trust=require_float(value.get("trust"), "objective.trust"),
            freshness=require_float(value.get("freshness"), "objective.freshness"),
            dependency_coverage=require_float(
                value.get("dependency_coverage"), "objective.dependency_coverage"
            ),
            redundancy_penalty=require_float(
                value.get("redundancy_penalty"), "objective.redundancy_penalty"
            ),
            security_risk_penalty=require_float(
                value.get("security_risk_penalty"), "objective.security_risk_penalty"
            ),
            schema_version=version,
        )


@dataclass(frozen=True, slots=True)
class OptimizerLimits:
    max_bruteforce_nodes: int = 16
    max_dp_nodes: int = 256
    max_dp_budget: int = 100_000
    max_dp_states: int = 2_000_000
    max_dp_memory_bytes: int = 256 * 1024 * 1024
    ilp_timeout_ms: int = 2_000
    ilp_max_nodes: int = 120
    ilp_max_dependency_edges: int = 2_000

    def __post_init__(self) -> None:
        for name in (
            "max_bruteforce_nodes",
            "max_dp_nodes",
            "max_dp_budget",
            "max_dp_states",
            "max_dp_memory_bytes",
            "ilp_timeout_ms",
            "ilp_max_nodes",
            "ilp_max_dependency_edges",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise SourceValidationError(f"optimizer limit {name} must be a positive integer")

    def to_dict(self) -> dict[str, object]:
        value = to_canonical_primitive(self)
        if not isinstance(value, dict):
            raise AssertionError("optimizer limits did not canonicalize to an object")
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> OptimizerLimits:
        return cls(
            **{
                name: require_int(value.get(name), f"optimizer_limits.{name}")
                for name in (
                    "max_bruteforce_nodes",
                    "max_dp_nodes",
                    "max_dp_budget",
                    "max_dp_states",
                    "max_dp_memory_bytes",
                    "ilp_timeout_ms",
                    "ilp_max_nodes",
                    "ilp_max_dependency_edges",
                )
            }
        )


@dataclass(frozen=True, slots=True)
class OptimizerConfiguration:
    """All policy-independent inputs shared by every optimizer strategy."""

    requested_strategy: str = "auto"
    source_content_allowance: int | None = None
    mandatory_node_ids: tuple[str, ...] = ()
    blocked_node_ids: tuple[str, ...] = ()
    policy_eligible_node_ids: tuple[str, ...] | None = None
    objective_weights: ObjectiveWeights = ObjectiveWeights()
    limits: OptimizerLimits = OptimizerLimits()
    schema_version: SchemaVersion = OPTIMIZER_CONFIGURATION_SCHEMA

    def __post_init__(self) -> None:
        if self.requested_strategy not in REQUESTED_OPTIMIZER_IDS:
            raise SourceValidationError(
                f"unknown optimizer strategy {self.requested_strategy!r}; "
                f"expected one of {REQUESTED_OPTIMIZER_IDS}"
            )
        if self.source_content_allowance is not None and (
            not isinstance(self.source_content_allowance, int)
            or isinstance(self.source_content_allowance, bool)
            or self.source_content_allowance < 0
        ):
            raise SourceValidationError("source content allowance must be non-negative or null")
        for name in ("mandatory_node_ids", "blocked_node_ids"):
            values = tuple(getattr(self, name))
            if any(not item for item in values) or len(values) != len(set(values)):
                raise SourceValidationError(f"optimizer {name} must contain unique non-empty IDs")
            object.__setattr__(self, name, values)
        if self.policy_eligible_node_ids is not None:
            eligible = tuple(self.policy_eligible_node_ids)
            if any(not item for item in eligible) or len(eligible) != len(set(eligible)):
                raise SourceValidationError(
                    "optimizer policy_eligible_node_ids must contain unique non-empty IDs"
                )
            object.__setattr__(self, "policy_eligible_node_ids", eligible)
        require_schema_version(
            self.schema_version,
            expected=OPTIMIZER_CONFIGURATION_SCHEMA,
            artifact="OptimizerConfiguration",
        )

    def to_dict(self) -> dict[str, object]:
        value = to_canonical_primitive(self)
        if not isinstance(value, dict):
            raise AssertionError("optimizer configuration did not canonicalize to an object")
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> OptimizerConfiguration:
        version = require_schema_version(
            value.get("schema_version"),
            expected=OPTIMIZER_CONFIGURATION_SCHEMA,
            artifact="OptimizerConfiguration",
        )
        raw_eligible = value.get("policy_eligible_node_ids")
        return cls(
            requested_strategy=require_string(
                value.get("requested_strategy"), "optimizer.requested_strategy"
            ),
            source_content_allowance=(
                None
                if value.get("source_content_allowance") is None
                else require_int(
                    value.get("source_content_allowance"), "optimizer.source_content_allowance"
                )
            ),
            mandatory_node_ids=require_string_tuple(
                value.get("mandatory_node_ids"), "optimizer.mandatory_node_ids"
            ),
            blocked_node_ids=require_string_tuple(
                value.get("blocked_node_ids"), "optimizer.blocked_node_ids"
            ),
            policy_eligible_node_ids=(
                None
                if raw_eligible is None
                else require_string_tuple(raw_eligible, "optimizer.policy_eligible_node_ids")
            ),
            objective_weights=ObjectiveWeights.from_dict(
                require_mapping(value.get("objective_weights"), "optimizer.objective_weights")
            ),
            limits=OptimizerLimits.from_dict(
                require_mapping(value.get("limits"), "optimizer.limits")
            ),
            schema_version=version,
        )
