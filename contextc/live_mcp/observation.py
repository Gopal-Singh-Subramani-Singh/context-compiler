"""Normalize runtime tool results into secret-safe observations and M9 source facts."""

from __future__ import annotations

import json
from collections.abc import Mapping

from contextc.capabilities.models import Capability
from contextc.hashing import digest_bytes, semantic_hash
from contextc.ir import ContextNode, InstructionAuthority, NodeKind, Sensitivity, SourceReference
from contextc.live_mcp.models import LiveToolSnapshot, MCPRuntimeObservation

SENTINELS = {
    "secret": "CONTEXTC_TEST_SECRET_7F31",
    "credential": "CONTEXTC_TEST_CREDENTIAL_A91C",
    "internal_record": "CONTEXTC_TEST_INTERNAL_RECORD_C442",
}


def _mapping(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        result = dump(by_alias=True, exclude_none=True)
        return result if isinstance(result, Mapping) else None
    return None


def tool_result_payload(result: object) -> tuple[str, Mapping[str, object]]:
    value = _mapping(result) or {}
    structured = value.get("structuredContent", value.get("structured_content"))
    if isinstance(structured, Mapping):
        text = str(structured.get("value", ""))
        return text, structured
    content = value.get("content", [])
    if isinstance(content, list):
        for item in content:
            item_map = _mapping(item)
            if item_map is not None and isinstance(item_map.get("text"), str):
                text = str(item_map["text"])
                try:
                    decoded = json.loads(text)
                except json.JSONDecodeError:
                    decoded = None
                return text, decoded if isinstance(decoded, Mapping) else {}
    return "", {}


def observe_tool_result(
    *,
    server_id: str,
    plan_id: str,
    call_id: str,
    snapshot: LiveToolSnapshot,
    arguments: Mapping[str, object],
    result: object,
    fixture_version: str,
) -> tuple[MCPRuntimeObservation, ContextNode, str]:
    text, structured = tool_result_payload(result)
    interaction_semantics = {
        "server_declaration": snapshot.declaration_hash,
        "tool": snapshot.tool_name,
        "arguments": arguments,
        "plan_id": plan_id,
        "call_id": call_id,
        "fixture_version": fixture_version,
    }
    semantic_id = semantic_hash(interaction_semantics)
    short = semantic_id.split(":", 1)[1][:24]
    interaction_id = f"m10b-{short}"
    uri = f"mcp://{server_id}/tools/{snapshot.tool_name}/results/{interaction_id}"
    observed_caps_raw = structured.get("observed_capabilities", [])
    observed_caps = (
        tuple(Capability(str(v)) for v in observed_caps_raw)
        if isinstance(observed_caps_raw, list)
        else ()
    )
    sensitivity_raw = structured.get("observed_sensitivity")
    sensitivity = (
        snapshot.possible_output_sensitivity
        if sensitivity_raw is None
        else Sensitivity(str(sensitivity_raw))
    )
    raw = text.encode("utf-8")
    flags = {label: sentinel in text for label, sentinel in SENTINELS.items()}
    observation = MCPRuntimeObservation(
        interaction_id=interaction_id,
        semantic_interaction_identity=semantic_id,
        server_id=server_id,
        operation_kind="tool_call",
        tool_name=snapshot.tool_name,
        resource_uri=None,
        declared_capabilities=snapshot.declared_capabilities,
        observed_capabilities=observed_caps,
        observed_sensitivity=sensitivity,
        trust_domain=snapshot.trust_domain,
        source_uri=uri,
        content_hash=digest_bytes(raw),
        content_bytes=len(raw),
        success=True,
        sentinel_flags=flags,
    )
    node = ContextNode.create(
        node_id=f"live-mcp-{short}",
        kind=NodeKind.TOOL_RESULT,
        content=text,
        source=SourceReference(uri=uri),
        trust_domain=snapshot.trust_domain,
        sensitivity=sensitivity or Sensitivity.INTERNAL,
        instruction_authority=InstructionAuthority.NONE,
        metadata={
            "mcp_server": server_id,
            "mcp_tool": snapshot.tool_name,
            "mcp_interaction_id": interaction_id,
            "live_mcp": True,
        },
    )
    return observation, node, text
