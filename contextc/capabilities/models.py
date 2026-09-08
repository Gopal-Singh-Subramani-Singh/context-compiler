"""Typed static capability-composition models for M10a."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from contextc.canonical import freeze_value, to_canonical_primitive
from contextc.diagnostics import Diagnostic
from contextc.hashing import semantic_hash
from contextc.ir import Sensitivity, TrustDomain
from contextc.schema import SchemaVersion

CAPABILITY_DECLARATION_SCHEMA = SchemaVersion(1, 0)
CAPABILITY_PLAN_SCHEMA = SchemaVersion(1, 0)
CAPABILITY_POLICY_SCHEMA = SchemaVersion(1, 0)
CAPABILITY_APPROVAL_SCHEMA = SchemaVersion(1, 0)
CAPABILITY_MANIFEST_SCHEMA = SchemaVersion(1, 0)


class Capability(StrEnum):
    LOCAL_FILE_READ = "local_file_read"
    LOCAL_FILE_WRITE = "local_file_write"
    DATABASE_READ = "database_read"
    DATABASE_WRITE = "database_write"
    CREDENTIAL_ACCESS = "credential_access"
    ENVIRONMENT_READ = "environment_read"
    NETWORK_READ = "network_read"
    NETWORK_SEND = "network_send"
    EXTERNAL_READ = "external_read"
    EXTERNAL_WRITE = "external_write"
    CODE_EXECUTION = "code_execution"
    SHELL_EXECUTION = "shell_execution"
    MESSAGE_READ = "message_read"
    MESSAGE_SEND = "message_send"
    USER_DATA_READ = "user_data_read"
    USER_DATA_WRITE = "user_data_write"
    APPROVAL_REQUEST = "approval_request"


class CapabilityPolicyAction(StrEnum):
    ALLOW = "allow"
    WARN = "warn"
    REQUIRE_APPROVAL = "require_explicit_approval"
    BLOCK = "block"


class RiskKind(StrEnum):
    SENSITIVE_TO_EXTERNAL = "sensitive_to_external"
    UNTRUSTED_TO_EXECUTION = "untrusted_to_execution"
    CREDENTIAL_TO_NETWORK = "credential_to_network"


class SinkKind(StrEnum):
    LOCAL = "local"
    EXTERNAL = "external"
    NETWORK = "network"
    MESSAGE = "message"
    EXECUTION = "execution"


class BindingKind(StrEnum):
    RESOURCE = "resource"
    CALL_OUTPUT = "call_output"


@dataclass(frozen=True, slots=True)
class ToolDeclaration:
    tool_id: str
    server_id: str
    trust_domain: TrustDomain
    capabilities: tuple[Capability, ...]
    resources_read: tuple[str, ...]
    resources_written: tuple[str, ...]
    possible_output_sensitivity: Sensitivity | None
    side_effecting: bool | None
    allows_execution: bool | None
    allows_network: bool | None
    missing_fields: tuple[str, ...] = ()
    schema_version: SchemaVersion = CAPABILITY_DECLARATION_SCHEMA

    def __post_init__(self) -> None:
        if not self.tool_id or not self.server_id:
            raise ValueError("tool_id and server_id must be non-empty")
        object.__setattr__(self, "capabilities", tuple(sorted(set(self.capabilities), key=str)))
        object.__setattr__(self, "resources_read", tuple(sorted(set(self.resources_read))))
        object.__setattr__(self, "resources_written", tuple(sorted(set(self.resources_written))))
        object.__setattr__(self, "missing_fields", tuple(sorted(set(self.missing_fields))))

    @property
    def identity(self) -> str:
        return semantic_hash(to_canonical_primitive(self))


@dataclass(frozen=True, slots=True)
class ResourceDeclaration:
    resource_id: str
    kind: str
    sensitivity: Sensitivity
    trust_domain: TrustDomain
    owner: str | None = None
    allowed_sinks: tuple[SinkKind, ...] = ()
    allowed_actions: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    schema_version: SchemaVersion = CAPABILITY_DECLARATION_SCHEMA

    def __post_init__(self) -> None:
        if not self.resource_id or not self.kind:
            raise ValueError("resource_id and kind must be non-empty")
        object.__setattr__(self, "allowed_sinks", tuple(sorted(set(self.allowed_sinks), key=str)))
        object.__setattr__(self, "allowed_actions", tuple(sorted(set(self.allowed_actions))))
        object.__setattr__(self, "missing_fields", tuple(sorted(set(self.missing_fields))))

    @property
    def identity(self) -> str:
        return semantic_hash(to_canonical_primitive(self))


@dataclass(frozen=True, slots=True)
class InputBinding:
    input_name: str
    kind: BindingKind
    resource_id: str | None = None
    call_id: str | None = None
    output_name: str = "output"

    def __post_init__(self) -> None:
        if not self.input_name:
            raise ValueError("input binding name must be non-empty")
        if self.kind is BindingKind.RESOURCE:
            if not self.resource_id or self.call_id is not None:
                raise ValueError("resource binding requires resource_id only")
        elif not self.call_id or self.resource_id is not None:
            raise ValueError("call-output binding requires call_id only")


@dataclass(frozen=True, slots=True)
class PlanCall:
    call_id: str
    tool_id: str
    input_bindings: tuple[InputBinding, ...] = ()
    literal_inputs: Mapping[str, object] = field(default_factory=dict)
    requested_approvals: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.call_id or not self.tool_id:
            raise ValueError("call_id and tool_id must be non-empty")
        names = [binding.input_name for binding in self.input_bindings]
        if len(names) != len(set(names)):
            raise ValueError("input binding names must be unique per call")
        object.__setattr__(self, "literal_inputs", freeze_value(dict(self.literal_inputs)))
        object.__setattr__(
            self, "requested_approvals", tuple(sorted(set(self.requested_approvals)))
        )


@dataclass(frozen=True, slots=True)
class CapabilityPlan:
    plan_id: str
    calls: tuple[PlanCall, ...]
    structure_errors: tuple[str, ...] = ()
    schema_error: str | None = None
    schema_version: SchemaVersion = CAPABILITY_PLAN_SCHEMA

    def __post_init__(self) -> None:
        if not self.plan_id:
            raise ValueError("plan_id must be non-empty")
        object.__setattr__(self, "structure_errors", tuple(self.structure_errors))

    @property
    def identity(self) -> str:
        return semantic_hash(to_canonical_primitive(self))


@dataclass(frozen=True, slots=True)
class ApprovalEvidence:
    approval_id: str
    plan_id: str
    flow_identity: str
    approver_identity: str
    approver_trust_domain: TrustDomain
    approved: bool
    evidence_uri: str | None = None
    schema_version: SchemaVersion = CAPABILITY_APPROVAL_SCHEMA

    def __post_init__(self) -> None:
        if not all((self.approval_id, self.plan_id, self.flow_identity, self.approver_identity)):
            raise ValueError("approval identity fields must be non-empty")

    @property
    def identity(self) -> str:
        return semantic_hash(to_canonical_primitive(self))


@dataclass(frozen=True, slots=True)
class CapabilityFlow:
    flow_identity: str
    risk_kind: RiskKind
    source_id: str
    source_kind: str
    source_sensitivity: Sensitivity
    source_trust_domain: TrustDomain
    source_allowed_sinks: tuple[SinkKind, ...]
    call_ids: tuple[str, ...]
    tool_ids: tuple[str, ...]
    capabilities: tuple[Capability, ...]
    sink_kind: SinkKind
    sink_call_id: str
    sink_tool_id: str


@dataclass(frozen=True, slots=True)
class CapabilityPolicyRule:
    rule_id: str
    risk_kinds: tuple[RiskKind, ...]
    action: CapabilityPolicyAction
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.rule_id:
            raise ValueError("capability rule_id must be non-empty")
        object.__setattr__(self, "risk_kinds", tuple(sorted(set(self.risk_kinds), key=str)))


@dataclass(frozen=True, slots=True)
class CapabilityPolicy:
    policy_id: str
    version: str
    rules: tuple[CapabilityPolicyRule, ...]
    trusted_approval_domains: tuple[TrustDomain, ...] = (
        TrustDomain.USER_INSTRUCTION,
        TrustDomain.DEVELOPER_INSTRUCTION,
        TrustDomain.SYSTEM_POLICY,
    )
    untrusted_domains: tuple[TrustDomain, ...] = (
        TrustDomain.UNVERIFIED_TOOL,
        TrustDomain.EXTERNAL_CONTENT,
        TrustDomain.RETRIEVED_DOCUMENT,
    )
    schema_version: SchemaVersion = CAPABILITY_POLICY_SCHEMA

    def __post_init__(self) -> None:
        if not self.policy_id or not self.version:
            raise ValueError("capability policy identity fields must be non-empty")

    @property
    def identity(self) -> str:
        return semantic_hash(to_canonical_primitive(self))


@dataclass(frozen=True, slots=True)
class CapabilityDecision:
    flow_identity: str
    rule_id: str
    action: CapabilityPolicyAction
    approval_identity: str | None = None


@dataclass(frozen=True, slots=True)
class ApprovalRequirement:
    flow_identity: str
    rule_id: str
    plan_id: str


@dataclass(frozen=True, slots=True)
class CapabilityLimits:
    max_path_length: int = 8
    max_reported_flows: int = 64

    def __post_init__(self) -> None:
        if self.max_path_length < 1 or self.max_reported_flows < 1:
            raise ValueError("capability limits must be positive")


@dataclass(frozen=True, slots=True)
class CapabilityValidationResult:
    valid: bool
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class CapabilityManifest:
    analysis_version: str
    analysis_mode: str
    tool_execution_performed: bool
    policy_id: str
    policy_version: str
    policy_identity: str
    plan_id: str
    plan_identity: str
    tool_declaration_identities: Mapping[str, str]
    resource_declaration_identities: Mapping[str, str]
    flows: tuple[CapabilityFlow, ...]
    decisions: tuple[CapabilityDecision, ...]
    diagnostics: tuple[Diagnostic, ...]
    approval_requirements: tuple[ApprovalRequirement, ...]
    approval_evidence_identities: tuple[str, ...]
    rule_ids_triggered: tuple[str, ...]
    blocked: bool
    pending_approval: bool
    allowed: bool
    truncated: bool
    cache_status: str = "disabled"
    cache_key_identity: str | None = None
    schema_version: SchemaVersion = CAPABILITY_MANIFEST_SCHEMA

    def __post_init__(self) -> None:
        if self.analysis_mode != "static" or self.tool_execution_performed:
            raise ValueError("M10a capability manifests must represent static analysis only")
        for name in ("tool_declaration_identities", "resource_declaration_identities"):
            value = freeze_value(dict(getattr(self, name)))
            if not isinstance(value, Mapping):
                raise ValueError(f"{name} must be a mapping")
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, object]:
        value = to_canonical_primitive(self)
        if not isinstance(value, dict):
            raise AssertionError("capability manifest canonicalization failed")
        return value
