from __future__ import annotations

import json
from pathlib import Path

import pytest

from contextc.cache.store import ContentAddressedStore
from contextc.capabilities.approval import approval_from_mapping, load_approval
from contextc.capabilities.cache import CapabilityCache
from contextc.capabilities.mcp_tools import (
    load_declaration_directory,
    resource_from_mapping,
    tool_from_mapping,
)
from contextc.capabilities.models import (
    BindingKind,
    CapabilityLimits,
    CapabilityPlan,
    InputBinding,
    PlanCall,
    ResourceDeclaration,
    ToolDeclaration,
)
from contextc.capabilities.plan import load_plan, plan_from_mapping
from contextc.capabilities.policy import load_policy, policy_from_mapping
from contextc.capabilities.service import CapabilityService
from contextc.ir import Sensitivity, TrustDomain


def complete_tool_raw(tool_id: str = "reader") -> dict[str, object]:
    return {
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


def complete_resource_raw(resource_id: str = "r") -> dict[str, object]:
    return {
        "resource_id": resource_id,
        "kind": "local_file",
        "sensitivity": "internal",
        "trust_domain": "local_repository",
        "owner": "team",
        "allowed_sinks": ["local"],
        "allowed_actions": ["read"],
    }


def test_approval_loader_negative_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        approval_from_mapping([])
    with pytest.raises(ValueError):
        approval_from_mapping({"approval_id": "x"})
    base = {
        "approval_id": "a",
        "plan_id": "p",
        "flow_identity": "sha256:" + "1" * 64,
        "approver_identity": "user:x",
        "approver_trust_domain": "user_instruction",
        "approved": True,
    }
    with pytest.raises(ValueError):
        approval_from_mapping({**base, "approved": "yes"})
    with pytest.raises(ValueError):
        approval_from_mapping({**base, "evidence_uri": 123})
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        load_approval(path)


def test_tool_and_resource_loader_incomplete_and_invalid_paths(tmp_path: Path) -> None:
    raw = complete_tool_raw()
    del raw["possible_output_sensitivity"]
    declaration = tool_from_mapping(raw)
    assert "possible_output_sensitivity" in declaration.missing_fields

    with pytest.raises(ValueError):
        tool_from_mapping({**complete_tool_raw(), "tool_id": ""})
    with pytest.raises(ValueError):
        tool_from_mapping({**complete_tool_raw(), "capabilities": "bad"})

    resource_raw = complete_resource_raw()
    del resource_raw["allowed_actions"]
    resource = resource_from_mapping(resource_raw)
    assert "allowed_actions" in resource.missing_fields
    with pytest.raises(ValueError):
        resource_from_mapping({**complete_resource_raw(), "resource_id": ""})
    with pytest.raises(ValueError):
        resource_from_mapping({**complete_resource_raw(), "allowed_sinks": "bad"})

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError):
        load_declaration_directory(empty)


def test_declaration_loader_accepts_list_and_single_resource(tmp_path: Path) -> None:
    (tmp_path / "list.json").write_text(
        json.dumps(
            [
                {"type": "tool", **complete_tool_raw("z")},
                {"type": "resource", **complete_resource_raw("r")},
            ]
        ),
        encoding="utf-8",
    )
    tools, resources = load_declaration_directory(tmp_path)
    assert [tool.tool_id for tool in tools] == ["z"]
    assert [resource.resource_id for resource in resources] == ["r"]

    extra = tmp_path / "resource.json"
    extra.write_text(json.dumps(complete_resource_raw("r2")), encoding="utf-8")
    tools, resources = load_declaration_directory(tmp_path)
    assert [resource.resource_id for resource in resources] == ["r", "r2"]


def test_declaration_loader_rejects_bad_json_and_bad_aggregate(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        load_declaration_directory(tmp_path)
    bad.unlink()
    bad.write_text(json.dumps({"tools": "bad", "resources": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_declaration_directory(tmp_path)


def test_plan_parser_object_bindings_and_structural_errors(tmp_path: Path) -> None:
    plan = plan_from_mapping(
        {
            "schema_version": {"major": 1, "minor": 0},
            "plan_id": "p",
            "calls": [
                {
                    "call_id": "one",
                    "tool_id": "reader",
                    "input_bindings": {"r": {"resource_id": "r"}},
                    "literal_inputs": {"x": 1},
                    "requested_approvals": ["ticket-1"],
                },
                {
                    "call_id": "two",
                    "tool_id": "reader",
                    "input_bindings": {"v": {"call_id": "one", "output": "value"}},
                },
            ],
        }
    )
    assert plan.calls[0].input_bindings[0].kind is BindingKind.RESOURCE
    assert plan.calls[1].input_bindings[0].kind is BindingKind.CALL_OUTPUT

    invalid = plan_from_mapping(
        {
            "plan_id": "bad",
            "calls": [
                {
                    "call_id": "x",
                    "tool_id": "reader",
                    "input_bindings": {"v": "nonsense"},
                    "literal_inputs": [],
                    "requested_approvals": "bad",
                },
                "not-an-object",
            ],
        }
    )
    assert invalid.schema_error is not None
    assert invalid.structure_errors

    path = tmp_path / "bad-plan.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        load_plan(path)


def test_plan_parser_rejects_non_object_and_nonlist_calls() -> None:
    with pytest.raises(ValueError):
        plan_from_mapping([])
    plan = plan_from_mapping(
        {"plan_id": "x", "schema_version": {"major": 1, "minor": 0}, "calls": "bad"}
    )
    assert "plan calls must be a list" in plan.structure_errors


def test_policy_loader_negative_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        policy_from_mapping([])
    with pytest.raises(ValueError):
        policy_from_mapping({"version": "1.0.0", "rules": []})
    with pytest.raises(ValueError):
        policy_from_mapping({"policy_id": "p", "version": "1.0.0", "rules": "bad"})
    with pytest.raises(ValueError):
        policy_from_mapping(
            {
                "policy_id": "p",
                "version": "1.0.0",
                "rules": [
                    {"rule_id": "r", "risk_kinds": ["sensitive_to_external"], "action": "warn"},
                    {"rule_id": "r", "risk_kinds": ["sensitive_to_external"], "action": "warn"},
                ],
            }
        )
    with pytest.raises(ValueError):
        policy_from_mapping(
            {
                "policy_id": "p",
                "version": "1.0.0",
                "rules": [{"rule_id": "r", "risk_kinds": [], "action": "warn"}],
            }
        )
    path = tmp_path / "bad-policy.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        load_policy(path)


def test_models_enforce_basic_invariants() -> None:
    with pytest.raises(ValueError):
        InputBinding("", BindingKind.RESOURCE, resource_id="r")
    with pytest.raises(ValueError):
        InputBinding("x", BindingKind.RESOURCE)
    with pytest.raises(ValueError):
        InputBinding("x", BindingKind.CALL_OUTPUT)
    with pytest.raises(ValueError):
        PlanCall("", "tool")
    with pytest.raises(ValueError):
        PlanCall(
            "c",
            "tool",
            (
                InputBinding("x", BindingKind.RESOURCE, resource_id="r"),
                InputBinding("x", BindingKind.RESOURCE, resource_id="r"),
            ),
        )
    with pytest.raises(ValueError):
        CapabilityLimits(0, 1)
    with pytest.raises(ValueError):
        ToolDeclaration(
            "",
            "s",
            TrustDomain.VERIFIED_TOOL,
            (),
            (),
            (),
            Sensitivity.INTERNAL,
            False,
            False,
            False,
        )
    with pytest.raises(ValueError):
        ResourceDeclaration("", "local", Sensitivity.INTERNAL, TrustDomain.LOCAL_REPOSITORY)


def test_cache_malformed_payload_is_not_reused(tmp_path: Path) -> None:
    tool = tool_from_mapping(complete_tool_raw())
    plan = CapabilityPlan("p", (PlanCall("c", "reader"),))
    policy = load_policy()
    cache = CapabilityCache(tmp_path / "cache")
    limits = CapabilityLimits()
    key = cache.key_for(plan, (tool,), (), policy, (), limits)
    cache.store.put(key, b"not-json")
    assert cache.get(key) is None
    assert ContentAddressedStore(tmp_path / "cache").get(key) is None


def test_service_unknown_explain_flow_raises() -> None:
    tool = tool_from_mapping(complete_tool_raw())
    plan = CapabilityPlan("p", (PlanCall("c", "reader"),))
    manifest = CapabilityService().analyze_plan(plan, (tool,), (), load_policy())
    with pytest.raises(ValueError):
        CapabilityService().explain_flow(manifest, "sha256:" + "f" * 64)
