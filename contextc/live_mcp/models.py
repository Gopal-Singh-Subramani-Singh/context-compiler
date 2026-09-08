"""Typed evidence models for bounded M10b live MCP validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from contextc.canonical import freeze_value, to_canonical_primitive
from contextc.capabilities.models import Capability
from contextc.diagnostics import Diagnostic
from contextc.hashing import semantic_hash
from contextc.ir import Sensitivity, TrustDomain
from contextc.schema import SchemaVersion

LIVE_MCP_SCHEMA = SchemaVersion(1, 0)


class LiveExecutionDecision(StrEnum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    BLOCK = "block"


class CorrespondenceState(StrEnum):
    OBSERVED_MATCH = "observed_match"
    DECLARED_BUT_UNOBSERVED = "declared_but_unobserved"
    OBSERVED_MISMATCH = "observed_mismatch"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class LiveMCPServerSpec:
    server_id: str
    command: str
    args: tuple[str, ...]
    sandbox: str
    fixture_version: str = "1"
    timeout_seconds: float = 5.0
    operation_timeout_seconds: float | None = None
    transport: str = "stdio"
    schema_version: SchemaVersion = LIVE_MCP_SCHEMA

    def __post_init__(self) -> None:
        if not self.server_id or not self.command or not self.sandbox:
            raise ValueError("live MCP server identity, command, and sandbox are required")
        if self.transport != "stdio":
            raise ValueError("M10b supports stdio transport only")
        if self.timeout_seconds <= 0:
            raise ValueError("live MCP initialization timeout must be positive")
        if self.operation_timeout_seconds is not None and self.operation_timeout_seconds <= 0:
            raise ValueError("live MCP operation timeout must be positive")


@dataclass(frozen=True, slots=True)
class LiveToolSnapshot:
    tool_name: str
    description: str
    input_schema: Mapping[str, object]
    declared_capabilities: tuple[Capability, ...]
    possible_output_sensitivity: Sensitivity | None
    trust_domain: TrustDomain
    resources_read: tuple[str, ...] = ()
    resources_written: tuple[str, ...] = ()
    side_effecting: bool | None = None
    allows_execution: bool | None = None
    allows_network: bool | None = None
    declaration_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_schema", freeze_value(dict(self.input_schema)))
        object.__setattr__(
            self, "declared_capabilities", tuple(sorted(set(self.declared_capabilities), key=str))
        )
        object.__setattr__(self, "resources_read", tuple(sorted(set(self.resources_read))))
        object.__setattr__(self, "resources_written", tuple(sorted(set(self.resources_written))))
        if not self.declaration_hash:
            payload = {
                "tool_name": self.tool_name,
                "description": self.description,
                "input_schema": self.input_schema,
                "declared_capabilities": [v.value for v in self.declared_capabilities],
                "possible_output_sensitivity": None
                if self.possible_output_sensitivity is None
                else self.possible_output_sensitivity.value,
                "trust_domain": self.trust_domain.value,
                "resources_read": self.resources_read,
                "resources_written": self.resources_written,
                "side_effecting": self.side_effecting,
                "allows_execution": self.allows_execution,
                "allows_network": self.allows_network,
            }
            object.__setattr__(self, "declaration_hash", semantic_hash(payload))


@dataclass(frozen=True, slots=True)
class LiveResourceSnapshot:
    resource_uri: str
    name: str
    description: str
    kind: str
    sensitivity: Sensitivity
    trust_domain: TrustDomain
    allowed_sinks: tuple[str, ...] = ()
    allowed_actions: tuple[str, ...] = ()
    declaration_hash: str = ""

    def __post_init__(self) -> None:
        if not self.declaration_hash:
            object.__setattr__(
                self,
                "declaration_hash",
                semantic_hash(
                    {
                        "resource_uri": self.resource_uri,
                        "name": self.name,
                        "description": self.description,
                        "kind": self.kind,
                        "sensitivity": self.sensitivity.value,
                        "trust_domain": self.trust_domain.value,
                        "allowed_sinks": self.allowed_sinks,
                        "allowed_actions": self.allowed_actions,
                    }
                ),
            )


@dataclass(frozen=True, slots=True)
class MCPRuntimeObservation:
    interaction_id: str
    semantic_interaction_identity: str
    server_id: str
    operation_kind: str
    tool_name: str | None
    resource_uri: str | None
    declared_capabilities: tuple[Capability, ...]
    observed_capabilities: tuple[Capability, ...]
    observed_sensitivity: Sensitivity | None
    trust_domain: TrustDomain
    source_uri: str
    content_hash: str | None
    content_bytes: int
    success: bool
    error_type: str | None = None
    sentinel_flags: Mapping[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sentinel_flags", freeze_value(dict(self.sentinel_flags)))


@dataclass(frozen=True, slots=True)
class CapabilityCorrespondenceResult:
    tool_name: str
    declared_capabilities: tuple[Capability, ...]
    observed_capabilities: tuple[Capability, ...]
    matched: bool
    state: CorrespondenceState
    undeclared_observed_capabilities: tuple[Capability, ...]
    declared_but_unobserved_capabilities: tuple[Capability, ...]
    declared_sensitivity: Sensitivity | None
    observed_sensitivity: Sensitivity | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class LiveMCPAuditEvent:
    interaction_id: str
    plan_id: str | None
    server_id: str
    transport: str
    operation: str
    tool_or_resource: str | None
    arguments_hash: str | None
    result_hash: str | None
    result_sensitivity: Sensitivity | None
    trust_domain: TrustDomain | None
    static_decision: LiveExecutionDecision
    approval_state: str
    invocation_attempted: bool
    invocation_performed: bool
    policy_id: str | None
    policy_hash: str | None
    diagnostics: tuple[str, ...]
    duration_ms: float | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class LiveMCPInspectionResult:
    server_id: str
    initialized: bool
    transport: str
    server_declaration_hash: str
    tools: tuple[LiveToolSnapshot, ...]
    resources: tuple[LiveResourceSnapshot, ...]

    def to_dict(self) -> dict[str, object]:
        value = to_canonical_primitive(self)
        assert isinstance(value, dict)
        return value


@dataclass(frozen=True, slots=True)
class LivePlanExecutionResult:
    server_id: str
    transport: str
    server_declaration_hash: str
    fixture_version: str
    validation_profile_id: str
    plan_id: str
    decision: LiveExecutionDecision
    static_manifest: Mapping[str, object]
    observations: tuple[MCPRuntimeObservation, ...]
    correspondence_results: tuple[CapabilityCorrespondenceResult, ...]
    audit_events: tuple[LiveMCPAuditEvent, ...]
    invoked_call_ids: tuple[str, ...]
    blocked_call_ids: tuple[str, ...]
    synthetic_secret_reached_sink: bool
    real_network_calls: int = 0
    real_shell_commands: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "static_manifest", freeze_value(dict(self.static_manifest)))

    def to_dict(self) -> dict[str, object]:
        value = to_canonical_primitive(self)
        assert isinstance(value, dict)
        return value

    def semantic_form(self) -> dict[str, object]:
        manifest = dict(self.static_manifest)
        manifest.pop("cache_status", None)
        manifest.pop("cache_key_identity", None)
        return {
            "server_id": self.server_id,
            "transport": self.transport,
            "server_declaration_hash": self.server_declaration_hash,
            "fixture_version": self.fixture_version,
            "validation_profile_id": self.validation_profile_id,
            "plan_id": self.plan_id,
            "decision": self.decision.value,
            "static_manifest": to_canonical_primitive(manifest),
            "observations": [
                {
                    "semantic_interaction_identity": item.semantic_interaction_identity,
                    "server_id": item.server_id,
                    "operation_kind": item.operation_kind,
                    "tool_name": item.tool_name,
                    "resource_uri": item.resource_uri,
                    "declared_capabilities": [v.value for v in item.declared_capabilities],
                    "observed_capabilities": [v.value for v in item.observed_capabilities],
                    "observed_sensitivity": None
                    if item.observed_sensitivity is None
                    else item.observed_sensitivity.value,
                    "trust_domain": item.trust_domain.value,
                    "source_uri": item.source_uri,
                    "content_hash": item.content_hash,
                    "content_bytes": item.content_bytes,
                    "success": item.success,
                    "error_type": item.error_type,
                    "sentinel_flags": to_canonical_primitive(item.sentinel_flags),
                }
                for item in self.observations
            ],
            "correspondence": [
                {
                    "tool_name": item.tool_name,
                    "state": item.state.value,
                    "matched": item.matched,
                    "diagnostic_codes": [d.code.value for d in item.diagnostics],
                }
                for item in self.correspondence_results
            ],
            "invoked_call_ids": list(self.invoked_call_ids),
            "blocked_call_ids": list(self.blocked_call_ids),
            "synthetic_secret_reached_sink": self.synthetic_secret_reached_sink,
            "real_network_calls": self.real_network_calls,
            "real_shell_commands": self.real_shell_commands,
        }


@dataclass(frozen=True, slots=True)
class LiveMCPValidationResult:
    server_id: str
    initialized: bool
    tools_discovered: int
    resources_discovered: int
    scenarios_run: int
    scenarios_passed: int
    correspondence_results: tuple[CapabilityCorrespondenceResult, ...]
    blocked_operations: tuple[str, ...]
    approval_required_operations: tuple[str, ...]
    diagnostics: tuple[Diagnostic, ...]
    audit_events: tuple[LiveMCPAuditEvent, ...]
    real_external_network_calls: int
    real_messages_sent: int
    real_shell_commands: int
    real_credentials_accessed: int
    synthetic_secret_leaks: int
    orphan_processes: int
    semantic_identity: str

    def to_dict(self) -> dict[str, object]:
        value = to_canonical_primitive(self)
        assert isinstance(value, dict)
        return value

    def semantic_form(self) -> dict[str, object]:
        return {
            "server_id": self.server_id,
            "initialized": self.initialized,
            "tools_discovered": self.tools_discovered,
            "resources_discovered": self.resources_discovered,
            "scenarios_run": self.scenarios_run,
            "scenarios_passed": self.scenarios_passed,
            "correspondence": [
                {
                    "tool_name": item.tool_name,
                    "state": item.state.value,
                    "matched": item.matched,
                    "diagnostic_codes": [d.code.value for d in item.diagnostics],
                }
                for item in self.correspondence_results
            ],
            "blocked_operations": list(self.blocked_operations),
            "approval_required_operations": list(self.approval_required_operations),
            "diagnostic_codes": [d.code.value for d in self.diagnostics],
            "real_external_network_calls": self.real_external_network_calls,
            "real_messages_sent": self.real_messages_sent,
            "real_shell_commands": self.real_shell_commands,
            "real_credentials_accessed": self.real_credentials_accessed,
            "synthetic_secret_leaks": self.synthetic_secret_leaks,
            "orphan_processes": self.orphan_processes,
        }
