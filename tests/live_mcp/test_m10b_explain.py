from contextc.live_mcp.explain import explain_live_result


def test_live_explain_uses_stored_evidence_only() -> None:
    value = {
        "plan_id": "secret-to-message",
        "decision": "require_approval",
        "invoked_call_ids": ["source"],
        "blocked_call_ids": ["sink"],
        "synthetic_secret_reached_sink": False,
        "static_manifest": {
            "diagnostics": [{"code": "CTX440"}, {"code": "CTX443"}],
            "flows": [
                {
                    "flow_identity": "sha256:f",
                    "risk_kind": "sensitive_to_external",
                    "source_id": "secret",
                    "source_sensitivity": "secret",
                    "source_trust_domain": "verified_tool",
                    "capabilities": ["local_file_read", "external_write"],
                    "sink_kind": "external",
                    "sink_call_id": "sink",
                    "sink_tool_id": "post_external_message",
                }
            ],
        },
        "correspondence_results": [
            {
                "tool_name": "read_secret_note",
                "state": "observed_match",
                "matched": True,
                "diagnostics": [],
            }
        ],
        "audit_events": [
            {
                "interaction_id": "x",
                "operation": "tools/call",
                "tool_or_resource": "sink",
                "static_decision": "require_approval",
                "approval_state": "missing",
                "invocation_attempted": True,
                "invocation_performed": False,
                "diagnostics": ["CTX440", "CTX443"],
            }
        ],
    }
    result = explain_live_result(value)
    assert result["evidence_mode"] == "stored_only"
    assert result["mcp_rerun_performed"] is False
    assert result["static_diagnostic_codes"] == ["CTX440", "CTX443"]
    assert result["dangerous_flows"][0]["sink_invoked"] is False
    assert result["synthetic_secret_reached_sink"] is False
