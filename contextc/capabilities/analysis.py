"""Bounded deterministic static capability-flow and policy analysis."""

from __future__ import annotations

from dataclasses import dataclass

from contextc.capabilities.models import (
    ApprovalEvidence,
    ApprovalRequirement,
    BindingKind,
    Capability,
    CapabilityDecision,
    CapabilityFlow,
    CapabilityLimits,
    CapabilityManifest,
    CapabilityPlan,
    CapabilityPolicy,
    CapabilityPolicyAction,
    CapabilityPolicyRule,
    ResourceDeclaration,
    RiskKind,
    SinkKind,
    ToolDeclaration,
)
from contextc.capabilities.validation import validate_declarations, validate_plan
from contextc.diagnostics import Diagnostic, DiagnosticCode, Severity, get_definition
from contextc.hashing import semantic_hash
from contextc.ir import Sensitivity, TrustDomain

CAPABILITY_ANALYSIS_VERSION = "1.0.0"

_SENSITIVITY_RANK = {
    Sensitivity.PUBLIC: 0,
    Sensitivity.INTERNAL: 1,
    Sensitivity.SENSITIVE: 2,
    Sensitivity.SECRET: 3,
}


@dataclass(frozen=True, slots=True)
class _Provenance:
    source_id: str
    source_kind: str
    sensitivity: Sensitivity
    trust_domain: TrustDomain
    allowed_sinks: tuple[SinkKind, ...]
    call_ids: tuple[str, ...]
    tool_ids: tuple[str, ...]
    capabilities: tuple[Capability, ...]


def _diag(
    code: DiagnosticCode,
    message: str,
    *,
    evidence: dict[str, object] | None = None,
    node_ids: tuple[str, ...] = (),
    severity: Severity | None = None,
) -> Diagnostic:
    definition = get_definition(code)
    return Diagnostic(
        code=code,
        severity=definition.default_severity if severity is None else severity,
        message=message,
        node_ids=node_ids,
        evidence={} if evidence is None else evidence,
        owning_pass="capability_analysis",
    )


def _max_sensitivity(left: Sensitivity, right: Sensitivity | None) -> Sensitivity:
    if right is None or _SENSITIVITY_RANK[left] >= _SENSITIVITY_RANK[right]:
        return left
    return right


def _append_provenance(
    provenance: _Provenance,
    call_id: str,
    tool: ToolDeclaration,
) -> _Provenance:
    capabilities = tuple(sorted(set(provenance.capabilities) | set(tool.capabilities), key=str))
    return _Provenance(
        source_id=provenance.source_id,
        source_kind=provenance.source_kind,
        sensitivity=_max_sensitivity(provenance.sensitivity, tool.possible_output_sensitivity),
        trust_domain=provenance.trust_domain,
        allowed_sinks=provenance.allowed_sinks,
        call_ids=(*provenance.call_ids, call_id),
        tool_ids=(*provenance.tool_ids, tool.tool_id),
        capabilities=capabilities,
    )


def _sink_kind(
    tool: ToolDeclaration, resource_by_id: dict[str, ResourceDeclaration]
) -> SinkKind | None:
    capabilities = set(tool.capabilities)
    if Capability.NETWORK_SEND in capabilities:
        return SinkKind.NETWORK
    if Capability.EXTERNAL_WRITE in capabilities:
        return SinkKind.EXTERNAL
    if Capability.MESSAGE_SEND in capabilities:
        return SinkKind.MESSAGE
    if Capability.SHELL_EXECUTION in capabilities or Capability.CODE_EXECUTION in capabilities:
        return SinkKind.EXECUTION
    for resource_id in sorted(tool.resources_written):
        resource = resource_by_id.get(resource_id)
        if resource is None:
            continue
        kind = resource.kind.lower()
        if "network" in kind:
            return SinkKind.NETWORK
        if "external" in kind:
            return SinkKind.EXTERNAL
        if "message" in kind:
            return SinkKind.MESSAGE
    return None


def _resource_provenance(resource: ResourceDeclaration) -> _Provenance:
    return _Provenance(
        source_id=resource.resource_id,
        source_kind=resource.kind,
        sensitivity=resource.sensitivity,
        trust_domain=resource.trust_domain,
        allowed_sinks=resource.allowed_sinks,
        call_ids=(),
        tool_ids=(),
        capabilities=(),
    )


def _synthetic_tool_provenance(call_id: str, tool: ToolDeclaration) -> tuple[_Provenance, ...]:
    values: list[_Provenance] = []
    if Capability.CREDENTIAL_ACCESS in tool.capabilities:
        values.append(
            _Provenance(
                source_id=f"capability://{call_id}/credential_access",
                source_kind="credential",
                sensitivity=Sensitivity.SECRET,
                trust_domain=tool.trust_domain,
                allowed_sinks=(),
                call_ids=(call_id,),
                tool_ids=(tool.tool_id,),
                capabilities=tool.capabilities,
            )
        )
    if Capability.ENVIRONMENT_READ in tool.capabilities:
        values.append(
            _Provenance(
                source_id=f"capability://{call_id}/environment_read",
                source_kind="environment",
                sensitivity=Sensitivity.SECRET,
                trust_domain=tool.trust_domain,
                allowed_sinks=(),
                call_ids=(call_id,),
                tool_ids=(tool.tool_id,),
                capabilities=tool.capabilities,
            )
        )
    values.append(
        _Provenance(
            source_id=f"tool-output://{tool.server_id}/{tool.tool_id}/{call_id}",
            source_kind="tool_output",
            sensitivity=tool.possible_output_sensitivity or Sensitivity.INTERNAL,
            trust_domain=tool.trust_domain,
            allowed_sinks=(),
            call_ids=(call_id,),
            tool_ids=(tool.tool_id,),
            capabilities=tool.capabilities,
        )
    )
    return tuple(values)


def _flow(
    risk: RiskKind,
    provenance: _Provenance,
    sink_kind: SinkKind,
    call_id: str,
    tool: ToolDeclaration,
) -> CapabilityFlow:
    call_ids = provenance.call_ids
    tool_ids = provenance.tool_ids
    if not call_ids or call_ids[-1] != call_id:
        call_ids = (*call_ids, call_id)
        tool_ids = (*tool_ids, tool.tool_id)
    capabilities = tuple(sorted(set(provenance.capabilities) | set(tool.capabilities), key=str))
    payload = {
        "risk_kind": risk.value,
        "source_id": provenance.source_id,
        "source_kind": provenance.source_kind,
        "source_sensitivity": provenance.sensitivity.value,
        "source_trust_domain": provenance.trust_domain.value,
        "source_allowed_sinks": [value.value for value in provenance.allowed_sinks],
        "call_ids": call_ids,
        "tool_ids": tool_ids,
        "capabilities": [value.value for value in capabilities],
        "sink_kind": sink_kind.value,
        "sink_call_id": call_id,
        "sink_tool_id": tool.tool_id,
    }
    return CapabilityFlow(
        flow_identity=semantic_hash(payload),
        risk_kind=risk,
        source_id=provenance.source_id,
        source_kind=provenance.source_kind,
        source_sensitivity=provenance.sensitivity,
        source_trust_domain=provenance.trust_domain,
        source_allowed_sinks=provenance.allowed_sinks,
        call_ids=call_ids,
        tool_ids=tool_ids,
        capabilities=capabilities,
        sink_kind=sink_kind,
        sink_call_id=call_id,
        sink_tool_id=tool.tool_id,
    )


def enumerate_flows(
    plan: CapabilityPlan,
    tools: tuple[ToolDeclaration, ...],
    resources: tuple[ResourceDeclaration, ...],
    policy: CapabilityPolicy,
    limits: CapabilityLimits,
) -> tuple[tuple[CapabilityFlow, ...], bool]:
    tool_by_id = {tool.tool_id: tool for tool in tools}
    resource_by_id = {resource.resource_id: resource for resource in resources}
    outputs: dict[str, tuple[_Provenance, ...]] = {}
    flows: dict[str, CapabilityFlow] = {}
    truncated = False

    for call in plan.calls:
        tool = tool_by_id.get(call.tool_id)
        if tool is None:
            continue
        incoming: list[_Provenance] = []
        for binding in call.input_bindings:
            if binding.kind is BindingKind.RESOURCE and binding.resource_id in resource_by_id:
                incoming.append(_resource_provenance(resource_by_id[binding.resource_id]))
            elif binding.kind is BindingKind.CALL_OUTPUT and binding.call_id in outputs:
                incoming.extend(outputs[binding.call_id])
        for resource_id in tool.resources_read:
            resource = resource_by_id.get(resource_id)
            if resource is not None:
                incoming.append(_resource_provenance(resource))

        # Deduplicate identical source paths before sink analysis.
        unique_incoming = {
            (
                value.source_id,
                value.source_kind,
                value.sensitivity.value,
                value.trust_domain.value,
                value.call_ids,
                value.tool_ids,
            ): value
            for value in incoming
        }
        ordered_incoming = tuple(unique_incoming[key] for key in sorted(unique_incoming))
        sink = _sink_kind(tool, resource_by_id)
        if sink is not None:
            for provenance in ordered_incoming:
                if len(provenance.call_ids) + 1 > limits.max_path_length:
                    truncated = True
                    continue
                if (
                    sink in {SinkKind.NETWORK, SinkKind.EXTERNAL, SinkKind.MESSAGE}
                    and _SENSITIVITY_RANK[provenance.sensitivity]
                    >= _SENSITIVITY_RANK[Sensitivity.SENSITIVE]
                    and sink not in provenance.allowed_sinks
                ):
                    value = _flow(
                        RiskKind.SENSITIVE_TO_EXTERNAL, provenance, sink, call.call_id, tool
                    )
                    flows[value.flow_identity] = value
                if (
                    sink is SinkKind.EXECUTION
                    and provenance.trust_domain in policy.untrusted_domains
                ):
                    value = _flow(
                        RiskKind.UNTRUSTED_TO_EXECUTION, provenance, sink, call.call_id, tool
                    )
                    flows[value.flow_identity] = value
                if sink is SinkKind.NETWORK and (
                    provenance.source_kind in {"credential", "environment"}
                    or Capability.CREDENTIAL_ACCESS in provenance.capabilities
                    or Capability.ENVIRONMENT_READ in provenance.capabilities
                ):
                    value = _flow(
                        RiskKind.CREDENTIAL_TO_NETWORK, provenance, sink, call.call_id, tool
                    )
                    flows[value.flow_identity] = value

        next_values: list[_Provenance] = []
        for provenance in ordered_incoming:
            if len(provenance.call_ids) + 1 <= limits.max_path_length:
                next_values.append(_append_provenance(provenance, call.call_id, tool))
            else:
                truncated = True
        next_values.extend(_synthetic_tool_provenance(call.call_id, tool))
        deduped = {
            (
                value.source_id,
                value.source_kind,
                value.sensitivity.value,
                value.trust_domain.value,
                value.call_ids,
                value.tool_ids,
            ): value
            for value in next_values
            if len(value.call_ids) <= limits.max_path_length
        }
        outputs[call.call_id] = tuple(deduped[key] for key in sorted(deduped))

    ordered = tuple(
        sorted(
            flows.values(),
            key=lambda value: (
                value.risk_kind.value,
                value.source_id,
                value.call_ids,
                value.sink_kind.value,
                value.flow_identity,
            ),
        )
    )
    if len(ordered) > limits.max_reported_flows:
        truncated = True
        ordered = ordered[: limits.max_reported_flows]
    return ordered, truncated


def _matching_rule(flow: CapabilityFlow, policy: CapabilityPolicy) -> CapabilityPolicyRule | None:
    for rule in policy.rules:
        if rule.enabled and flow.risk_kind in rule.risk_kinds:
            return rule
    return None


def analyze_capabilities(
    plan: CapabilityPlan,
    tools: tuple[ToolDeclaration, ...],
    resources: tuple[ResourceDeclaration, ...],
    policy: CapabilityPolicy,
    approvals: tuple[ApprovalEvidence, ...] = (),
    limits: CapabilityLimits | None = None,
) -> CapabilityManifest:
    actual_limits = CapabilityLimits() if limits is None else limits
    declaration_validation = validate_declarations(tools, resources)
    plan_validation = validate_plan(plan, tools, resources)
    diagnostics: list[Diagnostic] = list(declaration_validation.diagnostics)
    diagnostics.extend(plan_validation.diagnostics)

    tool_ids_used = {call.tool_id for call in plan.calls}
    resource_ids_used = {
        binding.resource_id
        for call in plan.calls
        for binding in call.input_bindings
        if binding.kind is BindingKind.RESOURCE and binding.resource_id is not None
    }
    tool_by_id = {tool.tool_id: tool for tool in tools}
    for tool_id in tool_ids_used:
        tool = tool_by_id.get(tool_id)
        if tool is not None:
            resource_ids_used.update(tool.resources_read)
            resource_ids_used.update(tool.resources_written)

    used_declaration_failure = any(
        diagnostic.code
        in {
            DiagnosticCode.INCOMPLETE_CAPABILITY_DECLARATIONS,
            DiagnosticCode.CAPABILITY_POLICY_EVIDENCE_FAILURE,
        }
        and any(
            node_id in tool_ids_used or node_id in resource_ids_used
            for node_id in diagnostic.node_ids
        )
        for diagnostic in declaration_validation.diagnostics
    )
    invalid_plan = not plan_validation.valid

    valid_approvals: dict[str, ApprovalEvidence] = {}
    approval_evidence_failures = False
    for approval in sorted(
        approvals, key=lambda item: (item.flow_identity, item.approval_id, item.identity)
    ):
        problems: list[str] = []
        if approval.plan_id != plan.plan_id:
            problems.append("plan_id_mismatch")
        if approval.approver_trust_domain not in policy.trusted_approval_domains:
            problems.append("untrusted_approver_domain")
        if not approval.approved:
            problems.append("approval_not_granted")
        if problems:
            approval_evidence_failures = True
            diagnostics.append(
                _diag(
                    DiagnosticCode.CAPABILITY_POLICY_EVIDENCE_FAILURE,
                    f"approval evidence {approval.approval_id} is not valid for this plan",
                    evidence={
                        "approval_id": approval.approval_id,
                        "approval_identity": approval.identity,
                        "flow_identity": approval.flow_identity,
                        "problems": problems,
                    },
                    node_ids=(approval.approval_id,),
                )
            )
        else:
            valid_approvals[approval.flow_identity] = approval

    flows: tuple[CapabilityFlow, ...] = ()
    truncated = False
    if not invalid_plan:
        flows, truncated = enumerate_flows(plan, tools, resources, policy, actual_limits)

    known_flow_ids = {flow.flow_identity for flow in flows}
    for flow_identity, approval in tuple(valid_approvals.items()):
        if flow_identity not in known_flow_ids:
            approval_evidence_failures = True
            diagnostics.append(
                _diag(
                    DiagnosticCode.CAPABILITY_POLICY_EVIDENCE_FAILURE,
                    (
                        f"approval evidence {approval.approval_id} references "
                        "an unknown capability flow"
                    ),
                    evidence={
                        "approval_id": approval.approval_id,
                        "approval_identity": approval.identity,
                        "flow_identity": flow_identity,
                        "problems": ["unknown_flow_identity"],
                    },
                    node_ids=(approval.approval_id,),
                )
            )
            del valid_approvals[flow_identity]

    decisions: list[CapabilityDecision] = []
    requirements: list[ApprovalRequirement] = []
    blocked = invalid_plan or used_declaration_failure or approval_evidence_failures
    pending = False

    for flow in flows:
        rule = _matching_rule(flow, policy)
        if rule is None:
            blocked = True
            diagnostics.append(
                _diag(
                    DiagnosticCode.CAPABILITY_POLICY_EVIDENCE_FAILURE,
                    "dangerous capability flow has no matching capability-policy rule",
                    evidence={
                        "flow_identity": flow.flow_identity,
                        "risk_kind": flow.risk_kind.value,
                    },
                    node_ids=flow.call_ids,
                )
            )
            continue

        severity = (
            Severity.WARNING
            if rule.action
            in {
                CapabilityPolicyAction.ALLOW,
                CapabilityPolicyAction.WARN,
            }
            else None
        )
        diagnostics.append(
            _diag(
                DiagnosticCode.DANGEROUS_CAPABILITY_COMPOSITION,
                f"dangerous static capability composition detected: {flow.risk_kind.value}",
                evidence={
                    "flow_identity": flow.flow_identity,
                    "risk_kind": flow.risk_kind.value,
                    "rule_id": rule.rule_id,
                    "source_id": flow.source_id,
                    "source_sensitivity": flow.source_sensitivity.value,
                    "sink_kind": flow.sink_kind.value,
                    "sink_call_id": flow.sink_call_id,
                },
                node_ids=flow.call_ids,
                severity=severity,
            )
        )

        flow_approval = valid_approvals.get(flow.flow_identity)
        if rule.action is CapabilityPolicyAction.REQUIRE_APPROVAL:
            if flow_approval is None:
                blocked = True
                pending = True
                requirements.append(
                    ApprovalRequirement(
                        flow_identity=flow.flow_identity,
                        rule_id=rule.rule_id,
                        plan_id=plan.plan_id,
                    )
                )
                diagnostics.append(
                    _diag(
                        DiagnosticCode.EXPLICIT_APPROVAL_REQUIRED,
                        "explicit trusted approval is required for this capability flow",
                        evidence={
                            "flow_identity": flow.flow_identity,
                            "rule_id": rule.rule_id,
                            "plan_id": plan.plan_id,
                        },
                        node_ids=flow.call_ids,
                    )
                )
                decisions.append(
                    CapabilityDecision(
                        flow_identity=flow.flow_identity,
                        rule_id=rule.rule_id,
                        action=rule.action,
                    )
                )
            else:
                decisions.append(
                    CapabilityDecision(
                        flow_identity=flow.flow_identity,
                        rule_id=rule.rule_id,
                        action=rule.action,
                        approval_identity=flow_approval.identity,
                    )
                )
        elif rule.action is CapabilityPolicyAction.BLOCK:
            blocked = True
            decisions.append(
                CapabilityDecision(
                    flow_identity=flow.flow_identity,
                    rule_id=rule.rule_id,
                    action=rule.action,
                )
            )
        else:
            decisions.append(
                CapabilityDecision(
                    flow_identity=flow.flow_identity,
                    rule_id=rule.rule_id,
                    action=rule.action,
                )
            )

    diagnostics.sort(
        key=lambda item: (
            item.code.value,
            item.node_ids,
            str(item.evidence.get("flow_identity", "")),
            item.message,
        )
    )
    requirements.sort(key=lambda item: (item.flow_identity, item.rule_id, item.plan_id))
    decisions.sort(key=lambda item: (item.flow_identity, item.rule_id, item.action.value))
    return CapabilityManifest(
        analysis_version=CAPABILITY_ANALYSIS_VERSION,
        analysis_mode="static",
        tool_execution_performed=False,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        policy_identity=policy.identity,
        plan_id=plan.plan_id,
        plan_identity=plan.identity,
        tool_declaration_identities={
            tool.tool_id: tool.identity for tool in sorted(tools, key=lambda item: item.tool_id)
        },
        resource_declaration_identities={
            resource.resource_id: resource.identity
            for resource in sorted(resources, key=lambda item: item.resource_id)
        },
        flows=flows,
        decisions=tuple(decisions),
        diagnostics=tuple(diagnostics),
        approval_requirements=tuple(requirements),
        approval_evidence_identities=tuple(sorted(approval.identity for approval in approvals)),
        rule_ids_triggered=tuple(sorted({decision.rule_id for decision in decisions})),
        blocked=blocked,
        pending_approval=pending,
        allowed=not blocked,
        truncated=truncated,
    )
