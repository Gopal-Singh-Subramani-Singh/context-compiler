from __future__ import annotations

from pathlib import Path

from contextc.capabilities.models import Capability
from contextc.ir import InstructionAuthority, Sensitivity, TrustDomain
from contextc.live_mcp.audit import write_audit
from contextc.live_mcp.models import LiveExecutionDecision, LiveMCPAuditEvent, LiveToolSnapshot
from contextc.live_mcp.observation import observe_tool_result


class Result:
    def model_dump(self, **kwargs):
        return {
            "structuredContent": {
                "value": "CONTEXTC_TEST_SECRET_7F31\n",
                "observed_capabilities": ["local_file_read"],
                "observed_sensitivity": "secret",
            }
        }


def test_runtime_observation_uses_mcp_uri_and_none_authority() -> None:
    snapshot = LiveToolSnapshot(
        "read_secret_note",
        "",
        {},
        (Capability.LOCAL_FILE_READ,),
        Sensitivity.SECRET,
        TrustDomain.VERIFIED_TOOL,
    )
    obs, node, raw = observe_tool_result(
        server_id="tiny-contextc-server",
        plan_id="p",
        call_id="c",
        snapshot=snapshot,
        arguments={},
        result=Result(),
        fixture_version="1",
    )
    assert raw.startswith("CONTEXTC_TEST_SECRET")
    assert node.source.uri.startswith("mcp://tiny-contextc-server/tools/read_secret_note/results/")
    assert node.instruction_authority is InstructionAuthority.NONE
    assert node.sensitivity is Sensitivity.SECRET
    assert obs.sentinel_flags["secret"] is True
    assert "CONTEXTC_TEST_SECRET_7F31" not in repr(obs)


def test_audit_persists_hash_not_secret(tmp_path: Path) -> None:
    event = LiveMCPAuditEvent(
        interaction_id="i",
        plan_id="p",
        server_id="tiny",
        transport="stdio",
        operation="tools/call",
        tool_or_resource="read_secret_note",
        arguments_hash="sha256:a",
        result_hash="sha256:b",
        result_sensitivity=Sensitivity.SECRET,
        trust_domain=TrustDomain.VERIFIED_TOOL,
        static_decision=LiveExecutionDecision.ALLOW,
        approval_state="not_required",
        invocation_attempted=True,
        invocation_performed=True,
        policy_id="policy",
        policy_hash="sha256:p",
        diagnostics=(),
    )
    path = tmp_path / "audit.json"
    digest = write_audit(path, (event,))
    assert digest.startswith("sha256:")
    assert "CONTEXTC_TEST_SECRET_7F31" not in path.read_text()
    assert '"result_hash": "sha256:b"' in path.read_text()


class TextItem:
    def __init__(self, text: str) -> None:
        self.text = text

    def model_dump(self, **kwargs):
        return {"text": self.text}


class TextResult:
    def __init__(self, text: str) -> None:
        self.text = text

    def model_dump(self, **kwargs):
        return {"content": [TextItem(self.text)]}


def test_runtime_observation_accepts_text_content_json_and_plain_text() -> None:
    snapshot = LiveToolSnapshot(
        "echo",
        "",
        {},
        (Capability.EXTERNAL_READ,),
        Sensitivity.INTERNAL,
        TrustDomain.UNVERIFIED_TOOL,
    )
    json_result = TextResult(
        '{"value":"hello","observed_capabilities":["external_read"],"observed_sensitivity":"internal"}'
    )
    obs, node, raw = observe_tool_result(
        server_id="tiny",
        plan_id="p",
        call_id="json",
        snapshot=snapshot,
        arguments={},
        result=json_result,
        fixture_version="1",
    )
    assert raw.startswith('{"value"')
    assert obs.observed_capabilities == (Capability.EXTERNAL_READ,)
    assert node.instruction_authority is InstructionAuthority.NONE

    plain, _, raw_plain = observe_tool_result(
        server_id="tiny",
        plan_id="p",
        call_id="plain",
        snapshot=snapshot,
        arguments={},
        result=TextResult("plain text"),
        fixture_version="1",
    )
    assert raw_plain == "plain text"
    assert plain.observed_capabilities == ()
