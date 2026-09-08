"""Typed M9 security policy and evidence models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from contextc.canonical import freeze_value, to_canonical_primitive
from contextc.diagnostics import Diagnostic
from contextc.ir import ContextNode, Sensitivity, TrustDomain


class PolicyAction(StrEnum):
    ALLOW = "allow"
    QUOTE_AS_DATA = "quote_as_data"
    REDACT = "redact"
    EXCLUDE = "exclude"
    BLOCK_COMPILATION = "block_compilation"
    REQUIRE_EXPLICIT_ALLOW = "require_explicit_allow"


@dataclass(frozen=True, slots=True)
class SecurityRule:
    rule_id: str
    action: PolicyAction
    diagnostic_code: str | None = None
    source_domains: tuple[TrustDomain, ...] = ()
    sensitivities: tuple[Sensitivity, ...] = ()
    signal_categories: tuple[str, ...] = ()
    sink_kinds: tuple[str, ...] = ()
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class SecurityPolicy:
    policy_id: str
    version: str
    rules: tuple[SecurityRule, ...]
    trust_dominates: tuple[tuple[TrustDomain, TrustDomain], ...] = ()
    untrusted_domains: tuple[TrustDomain, ...] = (
        TrustDomain.UNVERIFIED_TOOL,
        TrustDomain.EXTERNAL_CONTENT,
        TrustDomain.RETRIEVED_DOCUMENT,
    )
    external_sink_kinds: tuple[str, ...] = ("external", "tool", "network")
    instruction_sink_kinds: tuple[str, ...] = ("instruction", "system", "developer")

    @property
    def identity_payload(self) -> Mapping[str, object]:
        value = to_canonical_primitive(self)
        assert isinstance(value, Mapping)
        return value


@dataclass(frozen=True, slots=True)
class PatternSignal:
    category: str
    node_id: str
    matched_fragment_hash: str
    confidence: float


@dataclass(frozen=True, slots=True)
class TaintPath:
    rule_id: str
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    source_node_id: str
    sink_node_id: str


@dataclass(frozen=True, slots=True)
class TaintLimits:
    max_path_length: int = 8
    max_reported_paths: int = 32

    def __post_init__(self) -> None:
        if self.max_path_length < 1 or self.max_reported_paths < 1:
            raise ValueError("taint limits must be positive")


@dataclass(frozen=True, slots=True)
class SecurityDecision:
    node_id: str
    rule_id: str
    action: PolicyAction
    diagnostic_code: str | None
    reason: str
    taint_path: TaintPath | None = None


@dataclass(frozen=True, slots=True)
class SecurityResult:
    policy_id: str
    policy_version: str
    policy_identity: str
    analysis_version: str
    nodes: tuple[ContextNode, ...]
    diagnostics: tuple[Diagnostic, ...]
    decisions: tuple[SecurityDecision, ...]
    taint_paths: tuple[TaintPath, ...]
    excluded_node_ids: tuple[str, ...] = ()
    blocked_node_ids: tuple[str, ...] = ()
    transformations: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    blocked: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "transformations", freeze_value(self.transformations))
