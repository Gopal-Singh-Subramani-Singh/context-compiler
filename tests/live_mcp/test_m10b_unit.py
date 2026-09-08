from __future__ import annotations

from pathlib import Path

import pytest

from contextc.capabilities.models import Capability
from contextc.capabilities.plan import plan_from_mapping
from contextc.capabilities.policy import load_policy
from contextc.capabilities.service import CapabilityService
from contextc.diagnostics import DiagnosticCode
from contextc.ir import Sensitivity, TrustDomain
from contextc.live_mcp.correspondence import compare_tool
from contextc.live_mcp.enforcement import blocked_sink_call_ids, execution_decision
from contextc.live_mcp.errors import MCPSandboxViolationError
from contextc.live_mcp.models import (
    CorrespondenceState,
    LiveExecutionDecision,
    LiveToolSnapshot,
    MCPRuntimeObservation,
)
from contextc.live_mcp.normalize import (
    normalize_resource,
    normalize_tool,
    to_resource_declaration,
    to_tool_declaration,
)
from contextc.live_mcp.sandbox import contained_path, initialize_fixture_sandbox


class Model:
    def __init__(self, value):
        self.value = value

    def model_dump(self, **kwargs):
        return self.value


def test_normalizes_tool_and_resource_metadata() -> None:
    tool = normalize_tool(
        Model(
            {
                "name": "read_secret_note",
                "description": (
                    "Read.\nCONTEXTC_META: "
                    '{"capabilities":["local_file_read"],"possible_output_sensitivity":'
                    '"secret","trust_domain":"verified_tool","resources_read":'
                    '["resource://secret"],"resources_written":[],"side_effecting":false,'
                    '"allows_execution":false,"allows_network":false}'
                ),
                "inputSchema": {"type": "object"},
            }
        ),
        server_id="tiny",
    )
    resource = normalize_resource(
        Model(
            {
                "uri": "resource://secret",
                "name": "secret",
                "description": (
                    "Secret.\nCONTEXTC_META: "
                    '{"kind":"local_file","sensitivity":"secret","trust_domain":'
                    '"verified_tool","allowed_sinks":["local"],"allowed_actions":["read"]}'
                ),
            }
        ),
        server_id="tiny",
    )
    assert tool.declared_capabilities == (Capability.LOCAL_FILE_READ,)
    assert tool.possible_output_sensitivity is Sensitivity.SECRET
    assert resource.sensitivity is Sensitivity.SECRET
    assert to_tool_declaration(tool, server_id="tiny").tool_id == "read_secret_note"
    assert to_resource_declaration(resource).resource_id == "resource://secret"


def test_correspondence_mismatch_gets_dedicated_ctx445() -> None:
    snapshot = LiveToolSnapshot(
        tool_name="misdeclared_reader",
        description="",
        input_schema={},
        declared_capabilities=(Capability.LOCAL_FILE_READ,),
        possible_output_sensitivity=Sensitivity.PUBLIC,
        trust_domain=TrustDomain.VERIFIED_TOOL,
    )
    observation = MCPRuntimeObservation(
        interaction_id="i",
        semantic_interaction_identity="s",
        server_id="tiny",
        operation_kind="tool_call",
        tool_name="misdeclared_reader",
        resource_uri=None,
        declared_capabilities=(Capability.LOCAL_FILE_READ,),
        observed_capabilities=(Capability.LOCAL_FILE_READ, Capability.CREDENTIAL_ACCESS),
        observed_sensitivity=Sensitivity.SECRET,
        trust_domain=TrustDomain.VERIFIED_TOOL,
        source_uri="mcp://tiny/tools/misdeclared_reader/results/i",
        content_hash="sha256:x",
        content_bytes=4,
        success=True,
    )
    result = compare_tool(snapshot, observation)
    assert result.state is CorrespondenceState.OBSERVED_MISMATCH
    assert not result.matched
    assert result.undeclared_observed_capabilities == (Capability.CREDENTIAL_ACCESS,)
    assert [d.code for d in result.diagnostics] == [DiagnosticCode.MCP_DECLARATION_MISMATCH]


def test_declared_but_unobserved_is_not_a_mismatch() -> None:
    snapshot = LiveToolSnapshot(
        tool_name="reader",
        description="",
        input_schema={},
        declared_capabilities=(Capability.LOCAL_FILE_READ, Capability.EXTERNAL_READ),
        possible_output_sensitivity=Sensitivity.PUBLIC,
        trust_domain=TrustDomain.VERIFIED_TOOL,
    )
    observation = MCPRuntimeObservation(
        interaction_id="i",
        semantic_interaction_identity="s",
        server_id="tiny",
        operation_kind="tool_call",
        tool_name="reader",
        resource_uri=None,
        declared_capabilities=snapshot.declared_capabilities,
        observed_capabilities=(Capability.LOCAL_FILE_READ,),
        observed_sensitivity=Sensitivity.PUBLIC,
        trust_domain=TrustDomain.VERIFIED_TOOL,
        source_uri="mcp://tiny/tools/reader/results/i",
        content_hash=None,
        content_bytes=0,
        success=True,
    )
    result = compare_tool(snapshot, observation)
    assert result.state is CorrespondenceState.DECLARED_BUT_UNOBSERVED
    assert result.diagnostics == ()


def test_sandbox_blocks_traversal_absolute_and_symlink(tmp_path: Path) -> None:
    root = tmp_path / "box"
    initialize_fixture_sandbox(root)
    assert (
        contained_path(root, "public.txt", must_exist=True)
        .read_text()
        .startswith("Context Compiler")
    )
    with pytest.raises(MCPSandboxViolationError):
        contained_path(root, "../escape")
    with pytest.raises(MCPSandboxViolationError):
        contained_path(root, str(tmp_path / "outside"))
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    (root / "link").symlink_to(outside)
    with pytest.raises(MCPSandboxViolationError):
        contained_path(root, "link", must_exist=True)


def test_enforcement_blocks_only_dangerous_sink() -> None:
    read = LiveToolSnapshot(
        "read_secret_note",
        "",
        {},
        (Capability.LOCAL_FILE_READ,),
        Sensitivity.SECRET,
        TrustDomain.VERIFIED_TOOL,
        resources_read=("resource://secret",),
        side_effecting=False,
        allows_execution=False,
        allows_network=False,
    )
    send = LiveToolSnapshot(
        "post_external_message",
        "",
        {},
        (Capability.EXTERNAL_WRITE,),
        Sensitivity.INTERNAL,
        TrustDomain.VERIFIED_TOOL,
        side_effecting=True,
        allows_execution=False,
        allows_network=False,
    )
    resource_raw = Model(
        {
            "uri": "resource://secret",
            "name": "secret",
            "description": (
                "CONTEXTC_META: "
                '{"kind":"local_file","sensitivity":"secret","trust_domain":'
                '"verified_tool","allowed_sinks":["local"],"allowed_actions":["read"]}'
            ),
        }
    )
    resource = to_resource_declaration(normalize_resource(resource_raw, server_id="tiny"))
    plan = plan_from_mapping(
        {
            "schema_version": {"major": 1, "minor": 0},
            "plan_id": "secret-to-message",
            "calls": [
                {"call_id": "read", "tool_id": "read_secret_note"},
                {
                    "call_id": "send",
                    "tool_id": "post_external_message",
                    "input_bindings": {"message": "call:read.output"},
                },
            ],
        }
    )
    manifest = CapabilityService().analyze_plan(
        plan,
        (to_tool_declaration(read, server_id="tiny"), to_tool_declaration(send, server_id="tiny")),
        (resource,),
        load_policy(),
    )
    assert manifest.pending_approval
    assert execution_decision(manifest) is LiveExecutionDecision.REQUIRE_APPROVAL
    assert blocked_sink_call_ids(manifest) == ("send",)
    assert any(
        d.code is DiagnosticCode.DANGEROUS_CAPABILITY_COMPOSITION for d in manifest.diagnostics
    )
    assert any(d.code is DiagnosticCode.EXPLICIT_APPROVAL_REQUIRED for d in manifest.diagnostics)


def test_normalizer_defaults_missing_fixture_metadata_to_untrusted_internal() -> None:
    tool = normalize_tool(
        {"name": "plain", "description": "plain tool", "inputSchema": []},
        server_id="tiny",
    )
    resource = normalize_resource(
        {"uri": "resource://plain", "name": "plain", "description": "plain resource"},
        server_id="tiny",
    )
    assert tool.declared_capabilities == ()
    assert tool.possible_output_sensitivity is None
    assert tool.trust_domain is TrustDomain.UNVERIFIED_TOOL
    assert resource.sensitivity is Sensitivity.INTERNAL
    assert resource.trust_domain is TrustDomain.UNVERIFIED_TOOL


def test_normalizer_rejects_missing_names_and_bad_metadata() -> None:
    with pytest.raises(ValueError, match="no name"):
        normalize_tool({}, server_id="tiny")
    with pytest.raises(ValueError, match="no URI"):
        normalize_resource({}, server_id="tiny")
    with pytest.raises(ValueError):
        normalize_tool({"name": "x", "description": "CONTEXTC_META: []"}, server_id="tiny")
