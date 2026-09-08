"""Central M10b gate between M10a analysis and bounded live sink invocation."""

from __future__ import annotations

from contextc.capabilities.models import CapabilityManifest, CapabilityPolicyAction
from contextc.live_mcp.models import CapabilityCorrespondenceResult, LiveExecutionDecision


def execution_decision(
    manifest: CapabilityManifest, correspondence: tuple[CapabilityCorrespondenceResult, ...] = ()
) -> LiveExecutionDecision:
    if any(not item.matched and item.state.value == "observed_mismatch" for item in correspondence):
        return LiveExecutionDecision.BLOCK
    if any(decision.action is CapabilityPolicyAction.BLOCK for decision in manifest.decisions):
        return LiveExecutionDecision.BLOCK
    if manifest.pending_approval:
        return LiveExecutionDecision.REQUIRE_APPROVAL
    if manifest.blocked:
        return LiveExecutionDecision.BLOCK
    return LiveExecutionDecision.ALLOW


def blocked_sink_call_ids(manifest: CapabilityManifest) -> tuple[str, ...]:
    blocked: set[str] = set()
    decision_by_flow = {d.flow_identity: d for d in manifest.decisions}
    requirements = {r.flow_identity for r in manifest.approval_requirements}
    for flow in manifest.flows:
        decision = decision_by_flow.get(flow.flow_identity)
        if flow.flow_identity in requirements or (
            decision is not None and decision.action is CapabilityPolicyAction.BLOCK
        ):
            blocked.add(flow.sink_call_id)
    return tuple(sorted(blocked))
