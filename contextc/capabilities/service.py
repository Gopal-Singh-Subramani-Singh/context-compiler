"""Typed application service for static M10a capability analysis. Never executes tools."""

from __future__ import annotations

from pathlib import Path

from contextc.capabilities.analysis import analyze_capabilities
from contextc.capabilities.cache import CapabilityCache
from contextc.capabilities.graph import CapabilityGraph, build_capability_graph
from contextc.capabilities.models import (
    ApprovalEvidence,
    ApprovalRequirement,
    CapabilityLimits,
    CapabilityManifest,
    CapabilityPlan,
    CapabilityPolicy,
    CapabilityValidationResult,
    ResourceDeclaration,
    ToolDeclaration,
)
from contextc.capabilities.validation import validate_declarations, validate_plan


class CapabilityService:
    """Static-only service boundary for declaration, plan, flow, and approval analysis."""

    def __init__(self, cache_root: Path | None = None) -> None:
        self.cache_root = cache_root

    def validate_declarations(
        self,
        tools: tuple[ToolDeclaration, ...],
        resources: tuple[ResourceDeclaration, ...],
    ) -> CapabilityValidationResult:
        return validate_declarations(tools, resources)

    def validate_plan(
        self,
        plan: CapabilityPlan,
        tools: tuple[ToolDeclaration, ...],
        resources: tuple[ResourceDeclaration, ...],
    ) -> CapabilityValidationResult:
        declaration_result = validate_declarations(tools, resources)
        plan_result = validate_plan(plan, tools, resources)
        diagnostics = tuple(
            sorted(
                declaration_result.diagnostics + plan_result.diagnostics,
                key=lambda item: (item.code.value, item.node_ids, item.message),
            )
        )
        return CapabilityValidationResult(valid=not diagnostics, diagnostics=diagnostics)

    def build_graph(
        self,
        plan: CapabilityPlan,
        tools: tuple[ToolDeclaration, ...],
        resources: tuple[ResourceDeclaration, ...],
    ) -> CapabilityGraph:
        return build_capability_graph(plan, tools, resources)

    def analyze_plan(
        self,
        plan: CapabilityPlan,
        tools: tuple[ToolDeclaration, ...],
        resources: tuple[ResourceDeclaration, ...],
        policy: CapabilityPolicy,
        *,
        approvals: tuple[ApprovalEvidence, ...] = (),
        limits: CapabilityLimits | None = None,
    ) -> CapabilityManifest:
        actual_limits = CapabilityLimits() if limits is None else limits
        ordered_tools = tuple(
            sorted(tools, key=lambda item: (item.server_id, item.tool_id, item.identity))
        )
        ordered_resources = tuple(
            sorted(resources, key=lambda item: (item.resource_id, item.identity))
        )
        ordered_approvals = tuple(
            sorted(
                approvals, key=lambda item: (item.flow_identity, item.approval_id, item.identity)
            )
        )
        if self.cache_root is None:
            return analyze_capabilities(
                plan,
                ordered_tools,
                ordered_resources,
                policy,
                ordered_approvals,
                actual_limits,
            )
        cache = CapabilityCache(self.cache_root)
        key = cache.key_for(
            plan,
            ordered_tools,
            ordered_resources,
            policy,
            tuple(approval.identity for approval in ordered_approvals),
            actual_limits,
        )
        cached = cache.get(key)
        if cached is not None:
            return cached
        result = analyze_capabilities(
            plan,
            ordered_tools,
            ordered_resources,
            policy,
            ordered_approvals,
            actual_limits,
        )
        return cache.put(key, result, tools=ordered_tools, resources=ordered_resources)

    def explain_flow(self, manifest: CapabilityManifest, flow_identity: str) -> dict[str, object]:
        flow = next(
            (item for item in manifest.flows if item.flow_identity == flow_identity),
            None,
        )
        if flow is None:
            raise ValueError(f"unknown capability flow identity {flow_identity}")
        decision = next(
            (item for item in manifest.decisions if item.flow_identity == flow_identity),
            None,
        )
        requirement = next(
            (
                item
                for item in manifest.approval_requirements
                if item.flow_identity == flow_identity
            ),
            None,
        )
        ordered_path: list[dict[str, object]] = [
            {
                "kind": "source",
                "resource_or_origin": flow.source_id,
                "source_kind": flow.source_kind,
                "sensitivity": flow.source_sensitivity.value,
                "trust_domain": flow.source_trust_domain.value,
                "allowed_sinks": [value.value for value in flow.source_allowed_sinks],
            }
        ]
        for index, call_id in enumerate(flow.call_ids):
            ordered_path.append(
                {
                    "kind": "call",
                    "call_id": call_id,
                    "tool_id": flow.tool_ids[index] if index < len(flow.tool_ids) else None,
                }
            )
        ordered_path.append(
            {
                "kind": "sink",
                "sink_kind": flow.sink_kind.value,
                "call_id": flow.sink_call_id,
                "tool_id": flow.sink_tool_id,
            }
        )
        return {
            "analysis_mode": "static",
            "tool_execution_performed": False,
            "flow_identity": flow.flow_identity,
            "risk_kind": flow.risk_kind.value,
            "capabilities": [value.value for value in flow.capabilities],
            "ordered_path": ordered_path,
            "decision": (
                None
                if decision is None
                else {
                    "rule_id": decision.rule_id,
                    "action": decision.action.value,
                    "approval_identity": decision.approval_identity,
                }
            ),
            "approval_requirement": (
                None
                if requirement is None
                else {
                    "plan_id": requirement.plan_id,
                    "rule_id": requirement.rule_id,
                    "flow_identity": requirement.flow_identity,
                }
            ),
        }

    def list_approval_requirements(
        self, manifest: CapabilityManifest
    ) -> tuple[ApprovalRequirement, ...]:
        return manifest.approval_requirements
