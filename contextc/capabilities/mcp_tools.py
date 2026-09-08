"""Static MCP-style tool/resource declaration loading. No MCP transport is used."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from contextc.capabilities.models import Capability, ResourceDeclaration, SinkKind, ToolDeclaration
from contextc.ir import Sensitivity, TrustDomain

_TOOL_REQUIRED = (
    "tool_id",
    "server_id",
    "trust_domain",
    "capabilities",
    "resources_read",
    "resources_written",
    "possible_output_sensitivity",
    "side_effecting",
    "allows_execution",
    "allows_network",
)
_RESOURCE_REQUIRED = (
    "resource_id",
    "kind",
    "sensitivity",
    "trust_domain",
    "allowed_sinks",
    "allowed_actions",
)


def _list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return value


def tool_from_mapping(raw: Mapping[str, object]) -> ToolDeclaration:
    missing = [name for name in _TOOL_REQUIRED if name not in raw or raw.get(name) is None]
    tool_id = raw.get("tool_id")
    server_id = raw.get("server_id")
    if not isinstance(tool_id, str) or not tool_id:
        raise ValueError("tool_id must be a non-empty string")
    if not isinstance(server_id, str) or not server_id:
        raise ValueError("server_id must be a non-empty string")
    caps_raw = raw.get("capabilities", [])
    reads_raw = raw.get("resources_read", [])
    writes_raw = raw.get("resources_written", [])
    if (
        not isinstance(caps_raw, list)
        or not isinstance(reads_raw, list)
        or not isinstance(writes_raw, list)
    ):
        raise ValueError("tool capabilities/resources_read/resources_written must be lists")
    sensitivity_raw = raw.get("possible_output_sensitivity")
    side_effecting_raw = raw.get("side_effecting")
    allows_execution_raw = raw.get("allows_execution")
    allows_network_raw = raw.get("allows_network")
    return ToolDeclaration(
        tool_id=tool_id,
        server_id=server_id,
        trust_domain=TrustDomain(str(raw.get("trust_domain", TrustDomain.UNVERIFIED_TOOL.value))),
        capabilities=tuple(Capability(str(v)) for v in caps_raw),
        resources_read=tuple(str(v) for v in reads_raw),
        resources_written=tuple(str(v) for v in writes_raw),
        possible_output_sensitivity=(
            Sensitivity(str(sensitivity_raw)) if sensitivity_raw is not None else None
        ),
        side_effecting=side_effecting_raw if isinstance(side_effecting_raw, bool) else None,
        allows_execution=(allows_execution_raw if isinstance(allows_execution_raw, bool) else None),
        allows_network=allows_network_raw if isinstance(allows_network_raw, bool) else None,
        missing_fields=tuple(missing),
    )


def resource_from_mapping(raw: Mapping[str, object]) -> ResourceDeclaration:
    missing = [name for name in _RESOURCE_REQUIRED if name not in raw or raw.get(name) is None]
    resource_id = raw.get("resource_id")
    kind = raw.get("kind")
    if not isinstance(resource_id, str) or not resource_id:
        raise ValueError("resource_id must be a non-empty string")
    if not isinstance(kind, str) or not kind:
        raise ValueError("resource kind must be a non-empty string")
    sinks_raw = raw.get("allowed_sinks", [])
    actions_raw = raw.get("allowed_actions", [])
    if not isinstance(sinks_raw, list) or not isinstance(actions_raw, list):
        raise ValueError("resource allowed_sinks/allowed_actions must be lists")
    return ResourceDeclaration(
        resource_id=resource_id,
        kind=kind,
        sensitivity=Sensitivity(str(raw.get("sensitivity", Sensitivity.INTERNAL.value))),
        trust_domain=TrustDomain(str(raw.get("trust_domain", TrustDomain.LOCAL_REPOSITORY.value))),
        owner=str(raw["owner"]) if isinstance(raw.get("owner"), str) else None,
        allowed_sinks=tuple(SinkKind(str(v)) for v in sinks_raw),
        allowed_actions=tuple(str(v) for v in actions_raw),
        missing_fields=tuple(missing),
    )


def _entries(raw: object) -> tuple[list[Mapping[str, object]], list[Mapping[str, object]]]:
    tools: list[Mapping[str, object]] = []
    resources: list[Mapping[str, object]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, Mapping):
                raise ValueError("declaration list entries must be objects")
            kind = item.get("type")
            if kind == "resource" or "resource_id" in item:
                resources.append(item)
            else:
                tools.append(item)
        return tools, resources
    if not isinstance(raw, Mapping):
        raise ValueError("declaration JSON must be an object or list")
    if "tools" in raw or "resources" in raw:
        raw_tools = raw.get("tools", [])
        raw_resources = raw.get("resources", [])
        if not isinstance(raw_tools, list) or not isinstance(raw_resources, list):
            raise ValueError("tools/resources declaration fields must be lists")
        for item in raw_tools:
            if not isinstance(item, Mapping):
                raise ValueError("tool declarations must be objects")
            tools.append(item)
        for item in raw_resources:
            if not isinstance(item, Mapping):
                raise ValueError("resource declarations must be objects")
            resources.append(item)
        return tools, resources
    kind = raw.get("type")
    if kind == "resource" or "resource_id" in raw:
        resources.append(raw)
    else:
        tools.append(raw)
    return tools, resources


def load_declaration_directory(
    path: Path,
) -> tuple[tuple[ToolDeclaration, ...], tuple[ResourceDeclaration, ...]]:
    if not path.is_dir():
        raise ValueError(f"tool declaration directory does not exist: {path}")
    tools: list[ToolDeclaration] = []
    resources: list[ResourceDeclaration] = []
    for file_path in sorted(path.rglob("*.json")):
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid declaration JSON {file_path}: {error.msg}") from error
        tool_entries, resource_entries = _entries(raw)
        tools.extend(tool_from_mapping(item) for item in tool_entries)
        resources.extend(resource_from_mapping(item) for item in resource_entries)
    if not tools:
        raise ValueError("tool declaration directory contains no tools")
    return (
        tuple(sorted(tools, key=lambda item: (item.server_id, item.tool_id, item.identity))),
        tuple(sorted(resources, key=lambda item: (item.resource_id, item.identity))),
    )
