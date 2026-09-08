"""M8 content-addressed cache integration for M10a capability analysis."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from contextc.cache.dependency_index import DependencyIndex
from contextc.cache.keys import ComputationKey
from contextc.cache.source_index import SourceIndex
from contextc.cache.stagekeys import stage_key
from contextc.cache.store import ContentAddressedStore
from contextc.canonical import canonical_json_bytes
from contextc.capabilities.analysis import CAPABILITY_ANALYSIS_VERSION
from contextc.capabilities.models import (
    ApprovalRequirement,
    Capability,
    CapabilityDecision,
    CapabilityFlow,
    CapabilityLimits,
    CapabilityManifest,
    CapabilityPlan,
    CapabilityPolicy,
    CapabilityPolicyAction,
    ResourceDeclaration,
    RiskKind,
    SinkKind,
    ToolDeclaration,
)
from contextc.diagnostics import Diagnostic
from contextc.ir import Sensitivity, TrustDomain


def capability_cache_inputs(
    plan: CapabilityPlan,
    tools: tuple[ToolDeclaration, ...],
    resources: tuple[ResourceDeclaration, ...],
    policy: CapabilityPolicy,
    approval_identities: tuple[str, ...],
    limits: CapabilityLimits,
) -> dict[str, object]:
    return {
        "analysis_version": CAPABILITY_ANALYSIS_VERSION,
        "plan_identity": plan.identity,
        "tool_declaration_identities": sorted(tool.identity for tool in tools),
        "resource_declaration_identities": sorted(resource.identity for resource in resources),
        "policy_identity": policy.identity,
        "approval_evidence_identities": sorted(approval_identities),
        "limits": {
            "max_path_length": limits.max_path_length,
            "max_reported_flows": limits.max_reported_flows,
        },
    }


def _list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return value


def manifest_from_mapping(raw: Mapping[str, object]) -> CapabilityManifest:
    flows_raw = raw.get("flows", [])
    decisions_raw = raw.get("decisions", [])
    diagnostics_raw = raw.get("diagnostics", [])
    requirements_raw = raw.get("approval_requirements", [])
    if (
        not isinstance(flows_raw, list)
        or not isinstance(decisions_raw, list)
        or not isinstance(diagnostics_raw, list)
        or not isinstance(requirements_raw, list)
    ):
        raise ValueError("cached capability manifest arrays are malformed")
    flows: list[CapabilityFlow] = []
    for value in flows_raw:
        if not isinstance(value, Mapping):
            raise ValueError("cached capability flow is malformed")
        flows.append(
            CapabilityFlow(
                flow_identity=str(value["flow_identity"]),
                risk_kind=RiskKind(str(value["risk_kind"])),
                source_id=str(value["source_id"]),
                source_kind=str(value["source_kind"]),
                source_sensitivity=Sensitivity(str(value["source_sensitivity"])),
                source_trust_domain=TrustDomain(str(value["source_trust_domain"])),
                source_allowed_sinks=tuple(
                    SinkKind(str(v))
                    for v in _list(value.get("source_allowed_sinks", []), "source_allowed_sinks")
                ),
                call_ids=tuple(str(v) for v in _list(value.get("call_ids"), "call_ids")),
                tool_ids=tuple(str(v) for v in _list(value.get("tool_ids"), "tool_ids")),
                capabilities=tuple(
                    Capability(str(v)) for v in _list(value.get("capabilities"), "capabilities")
                ),
                sink_kind=SinkKind(str(value["sink_kind"])),
                sink_call_id=str(value["sink_call_id"]),
                sink_tool_id=str(value["sink_tool_id"]),
            )
        )
    decisions: list[CapabilityDecision] = []
    for value in decisions_raw:
        if not isinstance(value, Mapping):
            raise ValueError("cached capability decision is malformed")
        approval_identity = value.get("approval_identity")
        decisions.append(
            CapabilityDecision(
                flow_identity=str(value["flow_identity"]),
                rule_id=str(value["rule_id"]),
                action=CapabilityPolicyAction(str(value["action"])),
                approval_identity=str(approval_identity) if approval_identity is not None else None,
            )
        )
    requirements: list[ApprovalRequirement] = []
    for value in requirements_raw:
        if not isinstance(value, Mapping):
            raise ValueError("cached approval requirement is malformed")
        requirements.append(
            ApprovalRequirement(
                flow_identity=str(value["flow_identity"]),
                rule_id=str(value["rule_id"]),
                plan_id=str(value["plan_id"]),
            )
        )
    tools_raw = raw.get("tool_declaration_identities", {})
    resources_raw = raw.get("resource_declaration_identities", {})
    if not isinstance(tools_raw, Mapping) or not isinstance(resources_raw, Mapping):
        raise ValueError("cached capability declaration identities are malformed")
    return CapabilityManifest(
        analysis_version=str(raw["analysis_version"]),
        analysis_mode=str(raw["analysis_mode"]),
        tool_execution_performed=bool(raw["tool_execution_performed"]),
        policy_id=str(raw["policy_id"]),
        policy_version=str(raw["policy_version"]),
        policy_identity=str(raw["policy_identity"]),
        plan_id=str(raw["plan_id"]),
        plan_identity=str(raw["plan_identity"]),
        tool_declaration_identities={str(k): str(v) for k, v in tools_raw.items()},
        resource_declaration_identities={str(k): str(v) for k, v in resources_raw.items()},
        flows=tuple(flows),
        decisions=tuple(decisions),
        diagnostics=tuple(
            Diagnostic.from_dict(value) for value in diagnostics_raw if isinstance(value, Mapping)
        ),
        approval_requirements=tuple(requirements),
        approval_evidence_identities=tuple(
            str(v)
            for v in _list(
                raw.get("approval_evidence_identities", []),
                "approval_evidence_identities",
            )
        ),
        rule_ids_triggered=tuple(
            str(v) for v in _list(raw.get("rule_ids_triggered", []), "rule_ids_triggered")
        ),
        blocked=bool(raw["blocked"]),
        pending_approval=bool(raw["pending_approval"]),
        allowed=bool(raw["allowed"]),
        truncated=bool(raw["truncated"]),
        cache_status="disabled",
        cache_key_identity=None,
    )


class CapabilityCache:
    """Narrow cache wrapper whose keys contain only static capability semantics."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.store = ContentAddressedStore(root)
        self.dependencies = DependencyIndex(root / "dependency-index.json")
        self.sources = SourceIndex(root / "source-index" / "sources.json")

    def key_for(
        self,
        plan: CapabilityPlan,
        tools: tuple[ToolDeclaration, ...],
        resources: tuple[ResourceDeclaration, ...],
        policy: CapabilityPolicy,
        approval_identities: tuple[str, ...],
        limits: CapabilityLimits,
    ) -> ComputationKey:
        return stage_key(
            "capability_analysis",
            capability_cache_inputs(plan, tools, resources, policy, approval_identities, limits),
            namespace="contextc.capabilities",
        )

    def get(self, key: ComputationKey) -> CapabilityManifest | None:
        entry = self.store.get(key)
        if entry is None:
            return None
        try:
            raw = json.loads(entry.payload.decode("utf-8"))
            if not isinstance(raw, Mapping):
                raise ValueError("cached capability manifest must be an object")
            manifest = manifest_from_mapping(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, KeyError, TypeError):
            self.store.delete_key_identity(key.identity)
            return None
        return replace(manifest, cache_status="reused", cache_key_identity=key.identity)

    def put(
        self,
        key: ComputationKey,
        manifest: CapabilityManifest,
        *,
        tools: tuple[ToolDeclaration, ...],
        resources: tuple[ResourceDeclaration, ...],
    ) -> CapabilityManifest:
        stored = replace(manifest, cache_status="disabled", cache_key_identity=None)
        source_uris = tuple(
            sorted(
                [f"capability://tool/{tool.server_id}/{tool.tool_id}" for tool in tools]
                + [f"capability://resource/{resource.resource_id}" for resource in resources]
            )
        )
        self.store.put(key, canonical_json_bytes(stored.to_dict()), source_uris=source_uris)
        self.dependencies.record(key.identity, ())
        for uri in source_uris:
            self.sources.record(uri, key.identity)
        return replace(manifest, cache_status="recomputed", cache_key_identity=key.identity)
