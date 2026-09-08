"""Deterministic validation for capability declarations and proposed plans."""

from __future__ import annotations

from collections.abc import Iterable

from contextc.capabilities.models import (
    BindingKind,
    Capability,
    CapabilityPlan,
    CapabilityValidationResult,
    ResourceDeclaration,
    ToolDeclaration,
)
from contextc.diagnostics import Diagnostic, DiagnosticCode, get_definition


def _diag(
    code: DiagnosticCode,
    message: str,
    *,
    evidence: dict[str, object] | None = None,
    node_ids: tuple[str, ...] = (),
) -> Diagnostic:
    definition = get_definition(code)
    return Diagnostic(
        code=code,
        severity=definition.default_severity,
        message=message,
        node_ids=node_ids,
        evidence={} if evidence is None else evidence,
        owning_pass="capability_analysis",
    )


def validate_declarations(
    tools: Iterable[ToolDeclaration],
    resources: Iterable[ResourceDeclaration],
) -> CapabilityValidationResult:
    tool_values = tuple(
        sorted(tools, key=lambda item: (item.server_id, item.tool_id, item.identity))
    )
    resource_values = tuple(sorted(resources, key=lambda item: (item.resource_id, item.identity)))
    diagnostics: list[Diagnostic] = []

    tool_ids = [tool.tool_id for tool in tool_values]
    duplicate_tools = sorted({value for value in tool_ids if tool_ids.count(value) > 1})
    for tool_id in duplicate_tools:
        diagnostics.append(
            _diag(
                DiagnosticCode.INCOMPLETE_CAPABILITY_DECLARATIONS,
                f"duplicate tool declaration for {tool_id}",
                evidence={"tool_id": tool_id, "problem": "duplicate_tool_id"},
                node_ids=(tool_id,),
            )
        )

    resource_ids = [resource.resource_id for resource in resource_values]
    duplicate_resources = sorted({value for value in resource_ids if resource_ids.count(value) > 1})
    for resource_id in duplicate_resources:
        diagnostics.append(
            _diag(
                DiagnosticCode.INCOMPLETE_CAPABILITY_DECLARATIONS,
                f"duplicate resource declaration for {resource_id}",
                evidence={"resource_id": resource_id, "problem": "duplicate_resource_id"},
                node_ids=(resource_id,),
            )
        )

    known_resources = set(resource_ids)
    execution_caps = {Capability.CODE_EXECUTION, Capability.SHELL_EXECUTION}
    network_caps = {
        Capability.NETWORK_READ,
        Capability.NETWORK_SEND,
        Capability.EXTERNAL_READ,
        Capability.EXTERNAL_WRITE,
        Capability.MESSAGE_SEND,
        Capability.MESSAGE_READ,
    }
    for tool in tool_values:
        if tool.missing_fields:
            diagnostics.append(
                _diag(
                    DiagnosticCode.INCOMPLETE_CAPABILITY_DECLARATIONS,
                    f"tool {tool.tool_id} has incomplete capability declarations",
                    evidence={
                        "tool_id": tool.tool_id,
                        "server_id": tool.server_id,
                        "missing_fields": list(tool.missing_fields),
                    },
                    node_ids=(tool.tool_id,),
                )
            )
        missing_resources = sorted(
            (set(tool.resources_read) | set(tool.resources_written)) - known_resources
        )
        if missing_resources:
            diagnostics.append(
                _diag(
                    DiagnosticCode.INCOMPLETE_CAPABILITY_DECLARATIONS,
                    f"tool {tool.tool_id} references undeclared resources",
                    evidence={
                        "tool_id": tool.tool_id,
                        "missing_resource_ids": missing_resources,
                    },
                    node_ids=(tool.tool_id,),
                )
            )
        if tool.allows_execution is False and any(
            cap in execution_caps for cap in tool.capabilities
        ):
            diagnostics.append(
                _diag(
                    DiagnosticCode.CAPABILITY_POLICY_EVIDENCE_FAILURE,
                    f"tool {tool.tool_id} execution declarations contradict its capabilities",
                    evidence={"tool_id": tool.tool_id, "problem": "execution_flag_conflict"},
                    node_ids=(tool.tool_id,),
                )
            )
        if tool.allows_network is False and any(cap in network_caps for cap in tool.capabilities):
            diagnostics.append(
                _diag(
                    DiagnosticCode.CAPABILITY_POLICY_EVIDENCE_FAILURE,
                    f"tool {tool.tool_id} network declarations contradict its capabilities",
                    evidence={"tool_id": tool.tool_id, "problem": "network_flag_conflict"},
                    node_ids=(tool.tool_id,),
                )
            )

    for resource in resource_values:
        if resource.missing_fields:
            diagnostics.append(
                _diag(
                    DiagnosticCode.INCOMPLETE_CAPABILITY_DECLARATIONS,
                    f"resource {resource.resource_id} has incomplete capability declarations",
                    evidence={
                        "resource_id": resource.resource_id,
                        "missing_fields": list(resource.missing_fields),
                    },
                    node_ids=(resource.resource_id,),
                )
            )

    diagnostics.sort(key=lambda item: (item.code.value, item.node_ids, item.message))
    return CapabilityValidationResult(valid=not diagnostics, diagnostics=tuple(diagnostics))


def validate_plan(
    plan: CapabilityPlan,
    tools: Iterable[ToolDeclaration],
    resources: Iterable[ResourceDeclaration],
) -> CapabilityValidationResult:
    tool_ids = {tool.tool_id for tool in tools}
    resource_ids = {resource.resource_id for resource in resources}
    diagnostics: list[Diagnostic] = []
    if plan.structure_errors:
        diagnostics.append(
            _diag(
                DiagnosticCode.INVALID_CAPABILITY_PLAN,
                "capability plan is structurally invalid",
                evidence={"plan_id": plan.plan_id, "problems": list(plan.structure_errors)},
                node_ids=(plan.plan_id,),
            )
        )
    if plan.schema_error is not None:
        diagnostics.append(
            _diag(
                DiagnosticCode.INVALID_CAPABILITY_PLAN,
                "capability plan schema is invalid or unsupported",
                evidence={"plan_id": plan.plan_id, "problem": plan.schema_error},
                node_ids=(plan.plan_id,),
            )
        )

    call_ids = [call.call_id for call in plan.calls]
    duplicate_calls = sorted({value for value in call_ids if call_ids.count(value) > 1})
    for call_id in duplicate_calls:
        diagnostics.append(
            _diag(
                DiagnosticCode.INVALID_CAPABILITY_PLAN,
                f"duplicate capability plan call ID {call_id}",
                evidence={
                    "plan_id": plan.plan_id,
                    "call_id": call_id,
                    "problem": "duplicate_call_id",
                },
                node_ids=(call_id,),
            )
        )

    prior: set[str] = set()
    all_calls = set(call_ids)
    for call in plan.calls:
        if call.tool_id not in tool_ids:
            diagnostics.append(
                _diag(
                    DiagnosticCode.INVALID_CAPABILITY_PLAN,
                    f"plan call {call.call_id} references unknown tool {call.tool_id}",
                    evidence={
                        "plan_id": plan.plan_id,
                        "call_id": call.call_id,
                        "tool_id": call.tool_id,
                        "problem": "unknown_tool",
                    },
                    node_ids=(call.call_id,),
                )
            )
        for binding in call.input_bindings:
            if binding.kind is BindingKind.RESOURCE:
                if binding.resource_id not in resource_ids:
                    diagnostics.append(
                        _diag(
                            DiagnosticCode.INVALID_CAPABILITY_PLAN,
                            (
                                f"plan call {call.call_id} binds unknown resource "
                                f"{binding.resource_id}"
                            ),
                            evidence={
                                "plan_id": plan.plan_id,
                                "call_id": call.call_id,
                                "resource_id": binding.resource_id,
                                "problem": "unknown_resource_binding",
                            },
                            node_ids=(call.call_id,),
                        )
                    )
            elif binding.call_id not in prior:
                problem = (
                    "cycle_or_forward_binding"
                    if binding.call_id in all_calls
                    else "unknown_call_binding"
                )
                diagnostics.append(
                    _diag(
                        DiagnosticCode.INVALID_CAPABILITY_PLAN,
                        f"plan call {call.call_id} binding must reference a prior call output",
                        evidence={
                            "plan_id": plan.plan_id,
                            "call_id": call.call_id,
                            "referenced_call_id": binding.call_id,
                            "problem": problem,
                        },
                        node_ids=(call.call_id,),
                    )
                )
        prior.add(call.call_id)

    diagnostics.sort(key=lambda item: (item.code.value, item.node_ids, item.message))
    return CapabilityValidationResult(valid=not diagnostics, diagnostics=tuple(diagnostics))
