"""Explain persisted M10b evidence without rerunning MCP tools."""

from __future__ import annotations

from collections.abc import Mapping


def _items(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def explain_live_result(value: Mapping[str, object]) -> dict[str, object]:
    """Return a bounded explanation from stored live/static evidence only."""

    static_raw = value.get("static_manifest", {})
    static = static_raw if isinstance(static_raw, Mapping) else {}
    flows = _items(static.get("flows", ()))
    diagnostics = _items(static.get("diagnostics", ()))
    correspondence = _items(value.get("correspondence_results", ()))
    audit = _items(value.get("audit_events", ()))
    blocked = _strings(value.get("blocked_call_ids", ()))
    invoked = _strings(value.get("invoked_call_ids", ()))

    dangerous: list[dict[str, object]] = []
    for flow in flows:
        dangerous.append(
            {
                "flow_identity": flow.get("flow_identity"),
                "risk_kind": flow.get("risk_kind"),
                "source_id": flow.get("source_id"),
                "source_sensitivity": flow.get("source_sensitivity"),
                "source_trust_domain": flow.get("source_trust_domain"),
                "capabilities": flow.get("capabilities", ()),
                "sink_kind": flow.get("sink_kind"),
                "sink_call_id": flow.get("sink_call_id"),
                "sink_tool_id": flow.get("sink_tool_id"),
                "sink_invoked": flow.get("sink_call_id") in invoked,
            }
        )

    return {
        "evidence_mode": "stored_only",
        "mcp_rerun_performed": False,
        "plan_id": value.get("plan_id", static.get("plan_id")),
        "decision": value.get("decision"),
        "static_diagnostic_codes": [item.get("code") for item in diagnostics],
        "dangerous_flows": dangerous,
        "invoked_call_ids": list(invoked),
        "blocked_call_ids": list(blocked),
        "correspondence": [
            {
                "tool_name": item.get("tool_name"),
                "state": item.get("state"),
                "matched": item.get("matched"),
                "diagnostic_codes": [d.get("code") for d in _items(item.get("diagnostics", ()))],
            }
            for item in correspondence
        ],
        "audit": [
            {
                "interaction_id": item.get("interaction_id"),
                "operation": item.get("operation"),
                "tool_or_resource": item.get("tool_or_resource"),
                "static_decision": item.get("static_decision"),
                "approval_state": item.get("approval_state"),
                "invocation_attempted": item.get("invocation_attempted"),
                "invocation_performed": item.get("invocation_performed"),
                "diagnostics": item.get("diagnostics", ()),
            }
            for item in audit
        ],
        "synthetic_secret_reached_sink": value.get("synthetic_secret_reached_sink"),
    }
