from __future__ import annotations

from pathlib import Path

import pytest

from contextc.capabilities.plan import load_plan
from contextc.diagnostics import DiagnosticCode
from contextc.live_mcp.models import CorrespondenceState, LiveExecutionDecision
from contextc.live_mcp.service import LiveMCPValidationService

pytest.importorskip("mcp")
pytestmark = pytest.mark.live_mcp

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "contextc/demos/live_mcp/tiny_server.py"
PLANS = ROOT / "examples/live_mcp/plans"


def spec(tmp_path: Path):
    return LiveMCPValidationService.fixture_spec(SERVER, tmp_path / "sandbox", timeout_seconds=8.0)


def test_real_stdio_lifecycle_discovery_and_resource_read(tmp_path: Path) -> None:
    service = LiveMCPValidationService()
    inspection = service.inspect_server(spec(tmp_path))
    assert inspection.initialized
    assert inspection.transport == "stdio"
    assert len(inspection.tools) >= 8
    assert len(inspection.resources) == 3
    assert {t.tool_name for t in inspection.tools} >= {
        "read_public_note",
        "read_secret_note",
        "post_external_message",
        "execute_fake_command",
        "fake_http_post",
    }
    value = service.read_resource(spec(tmp_path), "resource://contextc/public/readme")
    assert value


def test_safe_public_read_and_local_write_execute(tmp_path: Path) -> None:
    service = LiveMCPValidationService()
    server = spec(tmp_path)
    public = service.execute_validated_plan(server, load_plan(PLANS / "public-read.json"))
    assert public.decision is LiveExecutionDecision.ALLOW
    assert public.invoked_call_ids == ("read",)
    local = service.execute_validated_plan(server, load_plan(PLANS / "public-to-local.json"))
    assert local.decision is LiveExecutionDecision.ALLOW
    assert local.invoked_call_ids == ("read", "write")
    assert (Path(server.sandbox) / "copied-public.txt").exists()


def test_secret_external_blocks_sink_and_keeps_ledger_empty(tmp_path: Path) -> None:
    service = LiveMCPValidationService()
    server = spec(tmp_path)
    result = service.execute_validated_plan(
        server, load_plan(PLANS / "secret-to-message.json"), audit_path=tmp_path / "audit.json"
    )
    assert result.decision is LiveExecutionDecision.REQUIRE_APPROVAL
    assert "read-secret" in result.invoked_call_ids
    assert "send-message" in result.blocked_call_ids
    assert (Path(server.sandbox) / "outbound-ledger.jsonl").read_text() == ""
    assert "CONTEXTC_TEST_SECRET_7F31" not in (tmp_path / "audit.json").read_text()
    codes = {d["code"] for d in result.static_manifest["diagnostics"]}
    assert DiagnosticCode.DANGEROUS_CAPABILITY_COMPOSITION.value in codes


def test_untrusted_execution_and_credential_network_block_sinks(tmp_path: Path) -> None:
    service = LiveMCPValidationService()
    server = spec(tmp_path)
    untrusted = service.execute_validated_plan(
        server, load_plan(PLANS / "untrusted-to-execution.json")
    )
    assert "sink" not in untrusted.invoked_call_ids
    assert (Path(server.sandbox) / "execution-ledger.jsonl").read_text() == ""
    credential = service.execute_validated_plan(
        server, load_plan(PLANS / "credential-to-network.json")
    )
    assert credential.decision is LiveExecutionDecision.BLOCK
    assert "network" not in credential.invoked_call_ids
    assert (Path(server.sandbox) / "network-ledger.jsonl").read_text() == ""


def test_misdeclared_fixture_emits_ctx445_and_reduces_trust(tmp_path: Path) -> None:
    service = LiveMCPValidationService()
    result = service.execute_validated_plan(
        spec(tmp_path), load_plan(PLANS / "misdeclared-reader.json")
    )
    corr = result.correspondence_results[0]
    assert corr.state is CorrespondenceState.OBSERVED_MISMATCH
    assert any(d.code is DiagnosticCode.MCP_DECLARATION_MISMATCH for d in corr.diagnostics)
    assert result.decision is LiveExecutionDecision.BLOCK


def test_static_declaration_hash_ignores_sandbox_path(tmp_path: Path) -> None:
    service = LiveMCPValidationService()
    left = service.inspect_server(spec(tmp_path / "a"))
    right = service.inspect_server(spec(tmp_path / "b"))
    assert left.server_declaration_hash == right.server_declaration_hash
    assert [t.declaration_hash for t in left.tools] == [t.declaration_hash for t in right.tools]


def test_trusted_explicit_approvals_allow_only_fake_external_sink(tmp_path: Path) -> None:
    from contextc.capabilities.models import ApprovalEvidence
    from contextc.ir import TrustDomain

    service = LiveMCPValidationService()
    server = spec(tmp_path)
    plan = load_plan(PLANS / "secret-to-message.json")
    inspection = service.inspect_server(server)
    manifest = service.analyze_plan(inspection, plan, fixture_version=server.fixture_version)
    approvals = tuple(
        ApprovalEvidence(
            approval_id=f"live-{index}",
            plan_id=plan.plan_id,
            flow_identity=req.flow_identity,
            approver_identity="m10b-test-fixture",
            approver_trust_domain=TrustDomain.USER_INSTRUCTION,
            approved=True,
            evidence_uri=f"approval://m10b/{index}",
        )
        for index, req in enumerate(manifest.approval_requirements, start=1)
    )
    audit = tmp_path / "approved-audit.json"
    result = service.execute_validated_plan(server, plan, approvals=approvals, audit_path=audit)
    assert result.decision is LiveExecutionDecision.ALLOW
    assert "send-message" in result.invoked_call_ids
    assert result.synthetic_secret_reached_sink is True
    assert (
        "CONTEXTC_TEST_SECRET_7F31" in (Path(server.sandbox) / "outbound-ledger.jsonl").read_text()
    )
    assert "CONTEXTC_TEST_SECRET_7F31" not in audit.read_text()


def test_live_tool_rejects_parent_traversal(tmp_path: Path) -> None:
    from contextc.capabilities.plan import plan_from_mapping
    from contextc.live_mcp.errors import MCPToolInvocationError

    service = LiveMCPValidationService()
    plan = plan_from_mapping(
        {
            "schema_version": {"major": 1, "minor": 0},
            "plan_id": "traversal",
            "calls": [
                {
                    "call_id": "read",
                    "tool_id": "read_public_note",
                    "literal_inputs": {"relative_name": "../escape.txt"},
                }
            ],
        }
    )
    with pytest.raises(MCPToolInvocationError):
        service.execute_validated_plan(spec(tmp_path), plan)


def test_live_tool_timeout_is_bounded(tmp_path: Path) -> None:
    from contextc.capabilities.plan import plan_from_mapping
    from contextc.live_mcp.errors import MCPTimeoutError

    service = LiveMCPValidationService()
    # Real stdio process initialization can legitimately take more than a few
    # milliseconds.  Use a bound that comfortably permits initialization while
    # remaining shorter than the fixture tool delay so this test exercises the
    # tools/call timeout rather than startup timing.
    server = LiveMCPValidationService.fixture_spec(
        SERVER,
        tmp_path / "sandbox",
        timeout_seconds=5.0,
        operation_timeout_seconds=1.0,
    )
    plan = plan_from_mapping(
        {
            "schema_version": {"major": 1, "minor": 0},
            "plan_id": "timeout",
            "calls": [
                {
                    "call_id": "source",
                    "tool_id": "echo_untrusted_text",
                    "literal_inputs": {"text": "bounded", "delay_ms": 1500},
                }
            ],
        }
    )
    with pytest.raises(MCPTimeoutError):
        service.execute_validated_plan(server, plan)


def test_connection_failure_and_unknown_resource_are_typed(tmp_path: Path) -> None:
    from contextc.live_mcp.errors import MCPConnectionError, MCPResourceReadError
    from contextc.live_mcp.models import LiveMCPServerSpec

    service = LiveMCPValidationService()
    bad = LiveMCPServerSpec(
        server_id="tiny",
        command=str(tmp_path / "definitely-not-an-executable"),
        args=(),
        sandbox=str(tmp_path),
        timeout_seconds=0.2,
    )
    with pytest.raises(MCPConnectionError):
        service.inspect_server(bad)
    with pytest.raises(MCPResourceReadError):
        service.read_resource(spec(tmp_path / "good"), "resource://contextc/unknown")


def test_tiny_server_source_contains_no_real_network_or_shell_execution() -> None:
    source = SERVER.read_text(encoding="utf-8")
    forbidden = (
        "subprocess.run",
        "subprocess.Popen",
        "os.system",
        "shell=True",
        "import socket",
        "import requests",
        "import httpx",
        "urllib.request",
    )
    assert not [token for token in forbidden if token in source]
