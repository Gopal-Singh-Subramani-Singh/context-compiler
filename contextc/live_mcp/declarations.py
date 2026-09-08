"""Live declaration snapshot and mapping into M10a typed declarations."""

from __future__ import annotations

from contextc.capabilities.models import ResourceDeclaration, ToolDeclaration
from contextc.hashing import semantic_hash
from contextc.live_mcp.models import LiveMCPInspectionResult
from contextc.live_mcp.normalize import (
    normalize_resource,
    normalize_tool,
    to_resource_declaration,
    to_tool_declaration,
)


def inspection_from_sdk(
    *, server_id: str, tools: tuple[object, ...], resources: tuple[object, ...]
) -> LiveMCPInspectionResult:
    tool_values = tuple(
        sorted((normalize_tool(v, server_id=server_id) for v in tools), key=lambda v: v.tool_name)
    )
    resource_values = tuple(
        sorted(
            (normalize_resource(v, server_id=server_id) for v in resources),
            key=lambda v: v.resource_uri,
        )
    )
    identity = semantic_hash(
        {
            "server_id": server_id,
            "tools": [v.declaration_hash for v in tool_values],
            "resources": [v.declaration_hash for v in resource_values],
        }
    )
    return LiveMCPInspectionResult(
        server_id=server_id,
        initialized=True,
        transport="stdio",
        server_declaration_hash=identity,
        tools=tool_values,
        resources=resource_values,
    )


def capability_declarations(
    inspection: LiveMCPInspectionResult,
) -> tuple[tuple[ToolDeclaration, ...], tuple[ResourceDeclaration, ...]]:
    tools = tuple(to_tool_declaration(v, server_id=inspection.server_id) for v in inspection.tools)
    resources = tuple(to_resource_declaration(v) for v in inspection.resources)
    return tools, resources
