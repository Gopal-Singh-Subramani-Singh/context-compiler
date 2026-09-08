"""Static MCP-shaped source parser. No transport, auth, discovery, or execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from contextc.ir import (
    ContextEdge,
    ContextNode,
    EdgeType,
    InstructionAuthority,
    NodeKind,
    Sensitivity,
    SourceReference,
    TrustDomain,
)


@dataclass(frozen=True, slots=True)
class StaticMcpResult:
    nodes: tuple[ContextNode, ...]
    edges: tuple[ContextEdge, ...]


class StaticMcpParser:
    """Parse retained MCP-shaped result documents into normal Context IR."""

    def parse_file(self, path: Path) -> StaticMcpResult:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid static MCP JSON: {error.msg}") from error
        return self.parse_mapping(raw)

    def parse_mapping(self, raw: object) -> StaticMcpResult:
        if not isinstance(raw, dict):
            raise ValueError("static MCP source must be an object")
        server = raw.get("server")
        tool = raw.get("tool")
        result_id = raw.get("result_id")
        if not all(isinstance(value, str) and value for value in (server, tool, result_id)):
            raise ValueError("server, tool, and result_id must be non-empty strings")
        default_trust = TrustDomain(str(raw.get("trust_domain", "unverified_tool")))
        default_sensitivity = Sensitivity(str(raw.get("sensitivity", "internal")))
        content = raw.get("content")
        if not isinstance(content, list) or not content:
            raise ValueError("content must be a non-empty list")

        nodes: list[ContextNode] = []
        for index, item in enumerate(content):
            if not isinstance(item, dict):
                raise ValueError("MCP content entries must be objects")
            text = item.get("text")
            if not isinstance(text, str):
                raise ValueError("MCP content text must be a string")
            node_id = str(item.get("node_id", f"mcp-{result_id}-{index:04d}"))
            source_uri = f"mcp://{server}/tools/{tool}/results/{result_id}"
            sink = item.get("security_sink")
            metadata: dict[str, object] = {
                "mcp_server": server,
                "mcp_tool": tool,
                "mcp_result_id": result_id,
                "mcp_content_index": index,
            }
            if isinstance(sink, str) and sink:
                metadata["security_sink"] = sink
            nodes.append(
                ContextNode.create(
                    node_id=node_id,
                    kind=NodeKind.TOOL_RESULT,
                    content=text,
                    source=SourceReference(uri=source_uri),
                    trust_domain=TrustDomain(str(item.get("trust_domain", default_trust.value))),
                    sensitivity=Sensitivity(
                        str(item.get("sensitivity", default_sensitivity.value))
                    ),
                    instruction_authority=InstructionAuthority.NONE,
                    metadata=metadata,
                )
            )

        node_ids = {node.node_id for node in nodes}
        edges: list[ContextEdge] = []
        raw_edges = raw.get("edges", [])
        if not isinstance(raw_edges, list):
            raise ValueError("edges must be a list")
        for item in raw_edges:
            if not isinstance(item, dict):
                raise ValueError("MCP edges must be objects")
            source = item.get("source")
            target = item.get("target")
            if not isinstance(source, str) or not isinstance(target, str):
                raise ValueError("MCP edge endpoints must be strings")
            if source not in node_ids or target not in node_ids:
                raise ValueError("MCP edge endpoint does not reference parsed content")
            kind = EdgeType(str(item.get("type", "taints")))
            if kind not in {EdgeType.TAINTS, EdgeType.ENABLES}:
                raise ValueError("static MCP M9 edges may only be TAINTS or ENABLES")
            edges.append(
                ContextEdge(
                    source_node_id=source,
                    target_node_id=target,
                    edge_type=kind,
                    evidence={"static_mcp": True},
                )
            )
        return StaticMcpResult(
            tuple(sorted(nodes, key=lambda node: node.node_id)),
            tuple(
                sorted(
                    edges,
                    key=lambda edge: (
                        edge.source_node_id,
                        edge.target_node_id,
                        edge.edge_type.value,
                        edge.edge_id,
                    ),
                )
            ),
        )
