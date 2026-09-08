"""Normalize live SDK declarations into stable Context Compiler M10a models."""

from __future__ import annotations

import json
from collections.abc import Mapping

from contextc.capabilities.models import Capability, ResourceDeclaration, SinkKind, ToolDeclaration
from contextc.hashing import semantic_hash
from contextc.ir import Sensitivity, TrustDomain
from contextc.live_mcp.models import LiveResourceSnapshot, LiveToolSnapshot

_META_PREFIX = "CONTEXTC_META:"


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        result = dump(by_alias=True, exclude_none=True)
        if isinstance(result, Mapping):
            return result
    old_dump = getattr(value, "dict", None)
    if callable(old_dump):
        result = old_dump(by_alias=True, exclude_none=True)
        if isinstance(result, Mapping):
            return result
    raise ValueError("MCP SDK declaration is not mapping-like")


def _sequence(value: object) -> tuple[object, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(value)


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _meta(description: str | None) -> dict[str, object]:
    if not description:
        return {}
    marker_index = description.find(_META_PREFIX)
    if marker_index < 0:
        return {}
    payload = description[marker_index + len(_META_PREFIX) :].strip()
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("CONTEXTC_META must be a JSON object")
    return value


def normalize_tool(raw: object, *, server_id: str) -> LiveToolSnapshot:
    value = _mapping(raw)
    name = str(value.get("name", ""))
    if not name:
        raise ValueError("live MCP tool has no name")
    description = str(value.get("description", "") or "")
    meta = _meta(description)
    schema = value.get("inputSchema", value.get("input_schema", {}))
    if not isinstance(schema, Mapping):
        schema = {}
    caps = tuple(Capability(str(v)) for v in _sequence(meta.get("capabilities", ())))
    sensitivity_raw = meta.get("possible_output_sensitivity")
    resources_read = tuple(str(v) for v in _sequence(meta.get("resources_read", ())))
    resources_written = tuple(str(v) for v in _sequence(meta.get("resources_written", ())))
    side_effecting = _optional_bool(meta.get("side_effecting"))
    allows_execution = _optional_bool(meta.get("allows_execution"))
    allows_network = _optional_bool(meta.get("allows_network"))
    trust = TrustDomain(str(meta.get("trust_domain", TrustDomain.UNVERIFIED_TOOL.value)))
    stable = {
        "server_id": server_id,
        "name": name,
        "description": description,
        "input_schema": dict(schema),
        "meta": meta,
    }
    return LiveToolSnapshot(
        tool_name=name,
        description=description,
        input_schema=dict(schema),
        declared_capabilities=caps,
        possible_output_sensitivity=None
        if sensitivity_raw is None
        else Sensitivity(str(sensitivity_raw)),
        trust_domain=trust,
        resources_read=resources_read,
        resources_written=resources_written,
        side_effecting=side_effecting,
        allows_execution=allows_execution,
        allows_network=allows_network,
        declaration_hash=semantic_hash(stable),
    )


def normalize_resource(raw: object, *, server_id: str) -> LiveResourceSnapshot:
    value = _mapping(raw)
    uri = str(value.get("uri", ""))
    if not uri:
        raise ValueError("live MCP resource has no URI")
    description = str(value.get("description", "") or "")
    meta = _meta(description)
    stable = {
        "server_id": server_id,
        "uri": uri,
        "name": value.get("name"),
        "description": description,
        "meta": meta,
    }
    return LiveResourceSnapshot(
        resource_uri=uri,
        name=str(value.get("name", uri)),
        description=description,
        kind=str(meta.get("kind", "mcp_resource")),
        sensitivity=Sensitivity(str(meta.get("sensitivity", Sensitivity.INTERNAL.value))),
        trust_domain=TrustDomain(str(meta.get("trust_domain", TrustDomain.UNVERIFIED_TOOL.value))),
        allowed_sinks=tuple(str(v) for v in _sequence(meta.get("allowed_sinks", ()))),
        allowed_actions=tuple(str(v) for v in _sequence(meta.get("allowed_actions", ("read",)))),
        declaration_hash=semantic_hash(stable),
    )


def to_tool_declaration(value: LiveToolSnapshot, *, server_id: str) -> ToolDeclaration:
    return ToolDeclaration(
        tool_id=value.tool_name,
        server_id=server_id,
        trust_domain=value.trust_domain,
        capabilities=value.declared_capabilities,
        resources_read=value.resources_read,
        resources_written=value.resources_written,
        possible_output_sensitivity=value.possible_output_sensitivity,
        side_effecting=value.side_effecting,
        allows_execution=value.allows_execution,
        allows_network=value.allows_network,
    )


def to_resource_declaration(value: LiveResourceSnapshot) -> ResourceDeclaration:
    sinks = tuple(SinkKind(v) for v in value.allowed_sinks)
    return ResourceDeclaration(
        resource_id=value.resource_uri,
        kind=value.kind,
        sensitivity=value.sensitivity,
        trust_domain=value.trust_domain,
        allowed_sinks=sinks,
        allowed_actions=value.allowed_actions,
    )
