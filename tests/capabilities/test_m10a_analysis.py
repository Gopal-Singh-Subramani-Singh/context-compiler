from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from contextc.capabilities.analysis import CAPABILITY_ANALYSIS_VERSION
from contextc.capabilities.models import (
    ApprovalEvidence,
    BindingKind,
    Capability,
    CapabilityPlan,
    InputBinding,
    PlanCall,
    ResourceDeclaration,
    RiskKind,
    SinkKind,
    ToolDeclaration,
)
from contextc.capabilities.policy import load_policy
from contextc.capabilities.service import CapabilityService
from contextc.diagnostics import DiagnosticCode
from contextc.ir import Sensitivity, TrustDomain


def tool(
    tool_id: str,
    *capabilities: Capability,
    trust: TrustDomain = TrustDomain.VERIFIED_TOOL,
    reads: tuple[str, ...] = (),
    writes: tuple[str, ...] = (),
    output: Sensitivity = Sensitivity.INTERNAL,
    side_effecting: bool = False,
    allows_execution: bool = False,
    allows_network: bool = False,
    missing: tuple[str, ...] = (),
) -> ToolDeclaration:
    return ToolDeclaration(
        tool_id=tool_id,
        server_id="test-server",
        trust_domain=trust,
        capabilities=capabilities,
        resources_read=reads,
        resources_written=writes,
        possible_output_sensitivity=output,
        side_effecting=side_effecting,
        allows_execution=allows_execution,
        allows_network=allows_network,
        missing_fields=missing,
    )


def resource(
    resource_id: str,
    *,
    kind: str = "local_file",
    sensitivity: Sensitivity = Sensitivity.INTERNAL,
    trust: TrustDomain = TrustDomain.LOCAL_REPOSITORY,
    allowed_sinks: tuple[SinkKind, ...] = (SinkKind.LOCAL,),
) -> ResourceDeclaration:
    return ResourceDeclaration(
        resource_id=resource_id,
        kind=kind,
        sensitivity=sensitivity,
        trust_domain=trust,
        allowed_sinks=allowed_sinks,
        allowed_actions=("read",),
    )


def bind_resource(name: str, resource_id: str) -> InputBinding:
    return InputBinding(name, BindingKind.RESOURCE, resource_id=resource_id)


def bind_call(name: str, call_id: str) -> InputBinding:
    return InputBinding(name, BindingKind.CALL_OUTPUT, call_id=call_id)


def codes(manifest) -> set[DiagnosticCode]:
    return {diagnostic.code for diagnostic in manifest.diagnostics}


def sensitive_external_case():
    tools = (
        tool(
            "read_secret",
            Capability.LOCAL_FILE_READ,
            reads=("secret-file",),
            output=Sensitivity.SECRET,
        ),
        tool(
            "send_external",
            Capability.EXTERNAL_WRITE,
            side_effecting=True,
            allows_network=True,
        ),
    )
    resources = (
        resource("secret-file", sensitivity=Sensitivity.SECRET),
        resource(
            "external-api",
            kind="external",
            sensitivity=Sensitivity.PUBLIC,
            allowed_sinks=(SinkKind.EXTERNAL,),
        ),
    )
    plan = CapabilityPlan(
        "sensitive-external",
        (
            PlanCall("read", "read_secret"),
            PlanCall("send", "send_external", (bind_call("body", "read"),)),
        ),
    )
    return plan, tools, resources


def test_sensitive_read_to_external_write_requires_explicit_approval() -> None:
    plan, tools, resources = sensitive_external_case()
    result = CapabilityService().analyze_plan(plan, tools, resources, load_policy())

    assert DiagnosticCode.DANGEROUS_CAPABILITY_COMPOSITION in codes(result)
    assert DiagnosticCode.EXPLICIT_APPROVAL_REQUIRED in codes(result)
    assert result.blocked
    assert result.pending_approval
    assert any(flow.risk_kind is RiskKind.SENSITIVE_TO_EXTERNAL for flow in result.flows)
    assert result.analysis_version == CAPABILITY_ANALYSIS_VERSION
    assert result.analysis_mode == "static"
    assert not result.tool_execution_performed


def test_untrusted_output_to_shell_execution_requires_approval() -> None:
    tools = (
        tool(
            "read_ticket",
            Capability.EXTERNAL_READ,
            trust=TrustDomain.UNVERIFIED_TOOL,
            allows_network=True,
        ),
        tool(
            "shell",
            Capability.SHELL_EXECUTION,
            side_effecting=True,
            allows_execution=True,
        ),
    )
    plan = CapabilityPlan(
        "untrusted-exec",
        (
            PlanCall("ticket", "read_ticket"),
            PlanCall("execute", "shell", (bind_call("script", "ticket"),)),
        ),
    )
    result = CapabilityService().analyze_plan(plan, tools, (), load_policy())

    assert any(flow.risk_kind is RiskKind.UNTRUSTED_TO_EXECUTION for flow in result.flows)
    assert DiagnosticCode.DANGEROUS_CAPABILITY_COMPOSITION in codes(result)
    assert DiagnosticCode.EXPLICIT_APPROVAL_REQUIRED in codes(result)
    assert result.blocked


def test_credential_access_to_network_send_is_blocked_by_default() -> None:
    tools = (
        tool("credential_reader", Capability.CREDENTIAL_ACCESS, output=Sensitivity.SECRET),
        tool(
            "network_sender",
            Capability.NETWORK_SEND,
            side_effecting=True,
            allows_network=True,
        ),
    )
    plan = CapabilityPlan(
        "credential-network",
        (
            PlanCall("credential", "credential_reader"),
            PlanCall("send", "network_sender", (bind_call("payload", "credential"),)),
        ),
    )
    result = CapabilityService().analyze_plan(plan, tools, (), load_policy())

    assert any(flow.risk_kind is RiskKind.CREDENTIAL_TO_NETWORK for flow in result.flows)
    assert result.blocked
    credential_decisions = [
        decision
        for decision in result.decisions
        if next(
            flow for flow in result.flows if flow.flow_identity == decision.flow_identity
        ).risk_kind
        is RiskKind.CREDENTIAL_TO_NETWORK
    ]
    assert credential_decisions
    assert all(decision.action.value == "block" for decision in credential_decisions)


def test_safe_local_read_to_local_report_is_allowed() -> None:
    tools = (
        tool("read_local", Capability.LOCAL_FILE_READ, reads=("report-source",)),
        tool(
            "write_local",
            Capability.LOCAL_FILE_WRITE,
            writes=("local-report",),
            side_effecting=True,
        ),
    )
    resources = (
        resource("report-source"),
        resource("local-report", kind="local_report", allowed_sinks=(SinkKind.LOCAL,)),
    )
    plan = CapabilityPlan(
        "safe-local",
        (
            PlanCall("read", "read_local"),
            PlanCall("write", "write_local", (bind_call("content", "read"),)),
        ),
    )
    result = CapabilityService().analyze_plan(plan, tools, resources, load_policy())

    assert not result.flows
    assert not result.diagnostics
    assert result.allowed
    assert not result.blocked


def test_explicit_approval_permits_only_exact_approved_flow() -> None:
    plan, tools, resources = sensitive_external_case()
    first = CapabilityService().analyze_plan(plan, tools, resources, load_policy())
    assert len(first.approval_requirements) >= 1
    approved_flow = first.approval_requirements[0].flow_identity
    approval = ApprovalEvidence(
        approval_id="approval-1",
        plan_id=plan.plan_id,
        flow_identity=approved_flow,
        approver_identity="user:acceptance-test",
        approver_trust_domain=TrustDomain.USER_INSTRUCTION,
        approved=True,
        evidence_uri="approval://acceptance/1",
    )
    second = CapabilityService().analyze_plan(
        plan, tools, resources, load_policy(), approvals=(approval,)
    )

    approved_decision = next(
        decision for decision in second.decisions if decision.flow_identity == approved_flow
    )
    assert approved_decision.approval_identity == approval.identity
    remaining = {item.flow_identity for item in second.approval_requirements}
    assert approved_flow not in remaining
    if len(first.approval_requirements) > 1:
        assert remaining
        assert second.blocked


def test_incomplete_used_declaration_emits_ctx441_and_blocks() -> None:
    incomplete = tool(
        "unknown_tool",
        Capability.LOCAL_FILE_READ,
        missing=("possible_output_sensitivity", "resources_read"),
    )
    plan = CapabilityPlan("incomplete", (PlanCall("call", "unknown_tool"),))
    result = CapabilityService().analyze_plan(plan, (incomplete,), (), load_policy())

    assert DiagnosticCode.INCOMPLETE_CAPABILITY_DECLARATIONS in codes(result)
    assert result.blocked


def test_invalid_binding_emits_ctx442() -> None:
    tools = (tool("reader", Capability.LOCAL_FILE_READ),)
    plan = CapabilityPlan(
        "invalid-binding",
        (PlanCall("first", "reader", (bind_call("input", "future"),)),),
    )
    result = CapabilityService().analyze_plan(plan, tools, (), load_policy())

    assert DiagnosticCode.INVALID_CAPABILITY_PLAN in codes(result)
    assert result.blocked
    assert not result.flows


def test_policy_evidence_contradiction_emits_ctx444() -> None:
    contradictory = tool(
        "bad-shell",
        Capability.SHELL_EXECUTION,
        allows_execution=False,
    )
    plan = CapabilityPlan("contradiction", (PlanCall("call", "bad-shell"),))
    result = CapabilityService().analyze_plan(plan, (contradictory,), (), load_policy())

    assert DiagnosticCode.CAPABILITY_POLICY_EVIDENCE_FAILURE in codes(result)
    assert result.blocked


def test_deterministic_flow_order_independent_of_declaration_insertion_order() -> None:
    plan, tools, resources = sensitive_external_case()
    first = CapabilityService().analyze_plan(plan, tools, resources, load_policy())
    second = CapabilityService().analyze_plan(
        plan, tuple(reversed(tools)), tuple(reversed(resources)), load_policy()
    )

    assert [flow.flow_identity for flow in first.flows] == [
        flow.flow_identity for flow in second.flows
    ]
    assert first.policy_identity == second.policy_identity
    assert first.plan_identity == second.plan_identity
    assert [diagnostic.to_dict() for diagnostic in first.diagnostics] == [
        diagnostic.to_dict() for diagnostic in second.diagnostics
    ]


def test_capability_cache_reuses_same_semantics_and_misses_on_tool_change(tmp_path: Path) -> None:
    plan, tools, resources = sensitive_external_case()
    service = CapabilityService(cache_root=tmp_path / "cache")
    first = service.analyze_plan(plan, tools, resources, load_policy())
    second = service.analyze_plan(plan, tools, resources, load_policy())
    changed_tools = (
        replace(tools[0], possible_output_sensitivity=Sensitivity.SENSITIVE),
        tools[1],
    )
    third = service.analyze_plan(plan, changed_tools, resources, load_policy())

    assert first.cache_status == "recomputed"
    assert second.cache_status == "reused"
    assert third.cache_status == "recomputed"
    assert first.cache_key_identity == second.cache_key_identity
    assert third.cache_key_identity != first.cache_key_identity


def test_literal_secret_is_not_written_to_manifest_diagnostics_or_cache(tmp_path: Path) -> None:
    canary = "M10A-RAW-SECRET-CANARY-81cfd"
    tools = (tool("local_writer", Capability.LOCAL_FILE_WRITE, side_effecting=True),)
    plan = CapabilityPlan(
        "literal-secret",
        (PlanCall("write", "local_writer", literal_inputs={"payload": canary}),),
    )
    cache_root = tmp_path / "cache"
    result = CapabilityService(cache_root=cache_root).analyze_plan(plan, tools, (), load_policy())

    assert canary not in str(result.to_dict())
    assert not any(
        canary.encode() in path.read_bytes() for path in cache_root.rglob("*") if path.is_file()
    )


def test_explain_flow_is_ordered_and_secret_safe() -> None:
    plan, tools, resources = sensitive_external_case()
    service = CapabilityService()
    result = service.analyze_plan(plan, tools, resources, load_policy())
    flow = next(flow for flow in result.flows if flow.source_id == "secret-file")
    explanation = service.explain_flow(result, flow.flow_identity)

    assert explanation["analysis_mode"] == "static"
    assert explanation["tool_execution_performed"] is False
    path = explanation["ordered_path"]
    assert path[0]["kind"] == "source"
    assert path[-1]["kind"] == "sink"
    assert [item["call_id"] for item in path if item["kind"] == "call"] == ["read", "send"]


def test_capability_graph_is_deterministic_and_explicit() -> None:
    plan, tools, resources = sensitive_external_case()
    service = CapabilityService()
    first = service.build_graph(plan, tools, resources)
    second = service.build_graph(plan, tuple(reversed(tools)), tuple(reversed(resources)))

    assert first.identity == second.identity
    assert first.nodes == second.nodes
    assert first.edges == second.edges
    assert any(edge.kind == "declared_read" for edge in first.edges)
    assert any(edge.kind.startswith("binding:") for edge in first.edges)
    assert any(node.kind == "capability" for node in first.nodes)


def test_path_enumeration_is_bounded() -> None:
    tools = (
        *(tool(f"step-{index}", Capability.LOCAL_FILE_READ) for index in range(5)),
        tool("send", Capability.EXTERNAL_WRITE, allows_network=True, side_effecting=True),
    )
    secret = resource("secret", sensitivity=Sensitivity.SECRET)
    calls = [PlanCall("c0", "step-0", (bind_resource("value", "secret"),))]
    for index in range(1, 5):
        calls.append(PlanCall(f"c{index}", f"step-{index}", (bind_call("value", f"c{index - 1}"),)))
    calls.append(PlanCall("send", "send", (bind_call("value", "c4"),)))
    from contextc.capabilities.models import CapabilityLimits

    result = CapabilityService().analyze_plan(
        CapabilityPlan("bounded", tuple(calls)),
        tools,
        (secret,),
        load_policy(),
        limits=CapabilityLimits(max_path_length=3, max_reported_flows=4),
    )
    assert result.truncated
    assert len(result.flows) <= 4


def test_capability_cache_does_not_touch_unrelated_parse_entry(tmp_path: Path) -> None:
    from contextc.cache.stagekeys import stage_key
    from contextc.cache.store import ContentAddressedStore

    root = tmp_path / "shared-cache"
    store = ContentAddressedStore(root)
    parse_key = stage_key("parse", {"fixture": "unrelated"})
    store.put(parse_key, b"unrelated-parse-payload")

    plan, tools, resources = sensitive_external_case()
    service = CapabilityService(cache_root=root)
    service.analyze_plan(plan, tools, resources, load_policy())
    changed = (replace(tools[0], possible_output_sensitivity=Sensitivity.SENSITIVE), tools[1])
    service.analyze_plan(plan, changed, resources, load_policy())

    entry = ContentAddressedStore(root).get(parse_key)
    assert entry is not None
    assert entry.payload == b"unrelated-parse-payload"


def test_declared_external_resource_write_is_an_explicit_sink() -> None:
    tools = (
        tool("read", Capability.LOCAL_FILE_READ, reads=("secret",), output=Sensitivity.INTERNAL),
        tool("write", writes=("external-destination",), side_effecting=True, allows_network=True),
    )
    resources = (
        resource("secret", sensitivity=Sensitivity.SECRET),
        ResourceDeclaration(
            resource_id="external-destination",
            kind="external_endpoint",
            sensitivity=Sensitivity.PUBLIC,
            trust_domain=TrustDomain.EXTERNAL_CONTENT,
            allowed_sinks=(SinkKind.EXTERNAL,),
            allowed_actions=("write",),
        ),
    )
    plan = CapabilityPlan(
        "resource-sink",
        (
            PlanCall("read-call", "read"),
            PlanCall("write-call", "write", (bind_call("payload", "read-call"),)),
        ),
    )
    result = CapabilityService().analyze_plan(plan, tools, resources, load_policy())
    assert any(
        flow.risk_kind is RiskKind.SENSITIVE_TO_EXTERNAL and flow.sink_kind is SinkKind.EXTERNAL
        for flow in result.flows
    )
    assert DiagnosticCode.DANGEROUS_CAPABILITY_COMPOSITION in codes(result)
