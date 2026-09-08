"""Deterministic static capability graph construction."""

from __future__ import annotations

from dataclasses import dataclass

from contextc.capabilities.models import (
    BindingKind,
    CapabilityPlan,
    ResourceDeclaration,
    ToolDeclaration,
)
from contextc.hashing import semantic_hash


@dataclass(frozen=True, slots=True)
class CapabilityGraphNode:
    node_id: str
    kind: str
    label: str


@dataclass(frozen=True, slots=True)
class CapabilityGraphEdge:
    source_id: str
    target_id: str
    kind: str

    @property
    def identity(self) -> str:
        return semantic_hash(
            {"source_id": self.source_id, "target_id": self.target_id, "kind": self.kind}
        )


@dataclass(frozen=True, slots=True)
class CapabilityGraph:
    nodes: tuple[CapabilityGraphNode, ...]
    edges: tuple[CapabilityGraphEdge, ...]

    @property
    def identity(self) -> str:
        return semantic_hash(
            {
                "nodes": [
                    {"node_id": n.node_id, "kind": n.kind, "label": n.label} for n in self.nodes
                ],
                "edges": [
                    {"source_id": e.source_id, "target_id": e.target_id, "kind": e.kind}
                    for e in self.edges
                ],
            }
        )


def build_capability_graph(
    plan: CapabilityPlan,
    tools: tuple[ToolDeclaration, ...],
    resources: tuple[ResourceDeclaration, ...],
) -> CapabilityGraph:
    tool_by_id = {tool.tool_id: tool for tool in tools}
    nodes: dict[str, CapabilityGraphNode] = {}
    edges: dict[str, CapabilityGraphEdge] = {}

    def add_node(node: CapabilityGraphNode) -> None:
        nodes[node.node_id] = node

    def add_edge(edge: CapabilityGraphEdge) -> None:
        edges[edge.identity] = edge

    for resource in sorted(resources, key=lambda item: item.resource_id):
        add_node(
            CapabilityGraphNode(
                f"resource:{resource.resource_id}", "resource", resource.resource_id
            )
        )
    for tool in sorted(tools, key=lambda item: (item.server_id, item.tool_id)):
        add_node(
            CapabilityGraphNode(f"tool:{tool.tool_id}", "tool", f"{tool.server_id}/{tool.tool_id}")
        )

    for call in plan.calls:
        call_node = f"call:{call.call_id}"
        output_node = f"output:{call.call_id}"
        add_node(CapabilityGraphNode(call_node, "call", call.call_id))
        add_node(CapabilityGraphNode(output_node, "output", f"{call.call_id}.output"))
        if call.tool_id in tool_by_id:
            add_edge(CapabilityGraphEdge(f"tool:{call.tool_id}", call_node, "invoked_as"))
            tool = tool_by_id[call.tool_id]
            for capability in tool.capabilities:
                cap_node = f"capability:{call.call_id}:{capability.value}"
                add_node(CapabilityGraphNode(cap_node, "capability", capability.value))
                add_edge(CapabilityGraphEdge(call_node, cap_node, "declares"))
                add_edge(CapabilityGraphEdge(cap_node, output_node, "enables"))
            for resource_id in tool.resources_read:
                if f"resource:{resource_id}" in nodes:
                    add_edge(
                        CapabilityGraphEdge(f"resource:{resource_id}", call_node, "declared_read")
                    )
            for resource_id in tool.resources_written:
                if f"resource:{resource_id}" in nodes:
                    add_edge(
                        CapabilityGraphEdge(call_node, f"resource:{resource_id}", "declared_write")
                    )
        for binding in call.input_bindings:
            if binding.kind is BindingKind.RESOURCE and binding.resource_id is not None:
                source = f"resource:{binding.resource_id}"
            else:
                source = f"output:{binding.call_id}"
            add_edge(CapabilityGraphEdge(source, call_node, f"binding:{binding.input_name}"))
        add_edge(CapabilityGraphEdge(call_node, output_node, "produces"))

    return CapabilityGraph(
        nodes=tuple(sorted(nodes.values(), key=lambda item: item.node_id)),
        edges=tuple(
            sorted(
                edges.values(),
                key=lambda item: (item.source_id, item.target_id, item.kind, item.identity),
            )
        ),
    )
