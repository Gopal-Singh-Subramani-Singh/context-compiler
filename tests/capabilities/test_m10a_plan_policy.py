from __future__ import annotations

import json
from pathlib import Path

from contextc.capabilities.approval import approval_from_mapping
from contextc.capabilities.mcp_tools import load_declaration_directory, tool_from_mapping
from contextc.capabilities.plan import plan_from_mapping
from contextc.capabilities.policy import load_policy
from contextc.capabilities.service import CapabilityService
from contextc.diagnostics import DiagnosticCode


def complete_tool(tool_id: str) -> dict[str, object]:
    return {
        "type": "tool",
        "tool_id": tool_id,
        "server_id": "server",
        "trust_domain": "verified_tool",
        "capabilities": ["local_file_read"],
        "resources_read": [],
        "resources_written": [],
        "possible_output_sensitivity": "internal",
        "side_effecting": False,
        "allows_execution": False,
        "allows_network": False,
    }


def test_unsupported_plan_schema_is_ctx442() -> None:
    plan = plan_from_mapping(
        {
            "schema_version": {"major": 2, "minor": 0},
            "plan_id": "future",
            "calls": [{"call_id": "one", "tool_id": "reader"}],
        }
    )
    tool = tool_from_mapping(complete_tool("reader"))
    result = CapabilityService().validate_plan(plan, (tool,), ())
    assert not result.valid
    assert any(d.code is DiagnosticCode.INVALID_CAPABILITY_PLAN for d in result.diagnostics)


def test_forward_call_binding_is_ctx442() -> None:
    plan = plan_from_mapping(
        {
            "schema_version": {"major": 1, "minor": 0},
            "plan_id": "forward",
            "calls": [
                {
                    "call_id": "one",
                    "tool_id": "reader",
                    "input_bindings": {"value": "call:two.output"},
                },
                {"call_id": "two", "tool_id": "reader"},
            ],
        }
    )
    tool = tool_from_mapping(complete_tool("reader"))
    result = CapabilityService().validate_plan(plan, (tool,), ())
    assert any(d.code is DiagnosticCode.INVALID_CAPABILITY_PLAN for d in result.diagnostics)


def test_policy_comment_only_change_preserves_identity(tmp_path: Path) -> None:
    first = tmp_path / "one.json"
    second = tmp_path / "two.json"
    first.write_text(
        '{"policy_id":"p","version":"1.0.0","rules":[{"rule_id":"r","risk_kinds":["sensitive_to_external"],"action":"warn"}]}',
        encoding="utf-8",
    )
    second.write_text(
        (
            '# comment\n// another\n{\n"policy_id":"p","version":"1.0.0",'
            '"rules":[{"rule_id":"r","risk_kinds":["sensitive_to_external"],'
            '"action":"warn"}]\n}'
        ),
        encoding="utf-8",
    )
    assert load_policy(first).identity == load_policy(second).identity


def test_declaration_directory_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "z.json").write_text(json.dumps(complete_tool("z")), encoding="utf-8")
    (tmp_path / "a.json").write_text(json.dumps(complete_tool("a")), encoding="utf-8")
    tools, resources = load_declaration_directory(tmp_path)
    assert [tool.tool_id for tool in tools] == ["a", "z"]
    assert resources == ()


def test_invalid_approval_domain_becomes_ctx444() -> None:
    # Deliberately use a plan that needs approval; invalid evidence must not satisfy it.
    policy = load_policy()
    from contextc.capabilities.models import Capability, CapabilityPlan, PlanCall, ToolDeclaration
    from contextc.ir import Sensitivity, TrustDomain

    reader = ToolDeclaration(
        "external_reader",
        "server",
        TrustDomain.UNVERIFIED_TOOL,
        (Capability.EXTERNAL_READ,),
        (),
        (),
        Sensitivity.INTERNAL,
        False,
        False,
        True,
    )
    shell = ToolDeclaration(
        "shell",
        "server",
        TrustDomain.VERIFIED_TOOL,
        (Capability.SHELL_EXECUTION,),
        (),
        (),
        Sensitivity.INTERNAL,
        True,
        True,
        False,
    )
    from contextc.capabilities.models import BindingKind, InputBinding

    plan = CapabilityPlan(
        "approval-evidence",
        (
            PlanCall("read", "external_reader"),
            PlanCall(
                "exec", "shell", (InputBinding("script", BindingKind.CALL_OUTPUT, call_id="read"),)
            ),
        ),
    )
    first = CapabilityService().analyze_plan(plan, (reader, shell), (), policy)
    flow = first.approval_requirements[0].flow_identity
    approval = approval_from_mapping(
        {
            "approval_id": "bad",
            "plan_id": plan.plan_id,
            "flow_identity": flow,
            "approver_identity": "tool:untrusted",
            "approver_trust_domain": "unverified_tool",
            "approved": True,
        }
    )
    result = CapabilityService().analyze_plan(
        plan, (reader, shell), (), policy, approvals=(approval,)
    )
    assert any(
        d.code is DiagnosticCode.CAPABILITY_POLICY_EVIDENCE_FAILURE for d in result.diagnostics
    )
    assert result.blocked


def test_missing_required_plan_fields_are_ctx442_not_generic_failure() -> None:
    plan = plan_from_mapping(
        {
            "schema_version": {"major": 1, "minor": 0},
            "calls": [{"tool_id": "reader"}],
        }
    )
    tool = tool_from_mapping(complete_tool("reader"))
    result = CapabilityService().validate_plan(plan, (tool,), ())
    assert not result.valid
    assert any(d.code is DiagnosticCode.INVALID_CAPABILITY_PLAN for d in result.diagnostics)


def test_approval_for_unknown_flow_is_ctx444() -> None:
    from contextc.capabilities.models import Capability, CapabilityPlan, PlanCall, ToolDeclaration
    from contextc.ir import Sensitivity, TrustDomain

    reader = ToolDeclaration(
        "reader",
        "server",
        TrustDomain.VERIFIED_TOOL,
        (Capability.LOCAL_FILE_READ,),
        (),
        (),
        Sensitivity.INTERNAL,
        False,
        False,
        False,
    )
    plan = CapabilityPlan("unknown-flow-approval", (PlanCall("read", "reader"),))
    approval = approval_from_mapping(
        {
            "approval_id": "approval-x",
            "plan_id": plan.plan_id,
            "flow_identity": "sha256:" + "0" * 64,
            "approver_identity": "user:test",
            "approver_trust_domain": "user_instruction",
            "approved": True,
        }
    )
    result = CapabilityService().analyze_plan(
        plan, (reader,), (), load_policy(), approvals=(approval,)
    )
    assert any(
        d.code is DiagnosticCode.CAPABILITY_POLICY_EVIDENCE_FAILURE for d in result.diagnostics
    )
    assert result.blocked
