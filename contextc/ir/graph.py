"""Deterministic typed multigraph semantics for Context IR."""

from __future__ import annotations

import heapq
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from contextc.decoding import require_mapping, require_sequence, require_string
from contextc.diagnostics import Diagnostic, DiagnosticCode, get_definition
from contextc.errors import DependencyCycleError, GraphInvariantError, SourceValidationError
from contextc.hashing import semantic_hash
from contextc.ir.edges import ContextEdge, EdgeType
from contextc.ir.nodes import ContextNode
from contextc.schema import GRAPH_SCHEMA, SchemaVersion, require_schema_version

DEFAULT_DEPENDENCY_EDGE_TYPES = frozenset({EdgeType.IMPORTS, EdgeType.CALLS, EdgeType.REQUIRES})


@dataclass(frozen=True, slots=True)
class DependencyClosure:
    """Stored deterministic dependency-closure evidence."""

    node_ids: tuple[str, ...]
    dependency_forced_node_ids: tuple[str, ...]
    missing_node_ids: tuple[str, ...]
    diagnostics: tuple[Diagnostic, ...]
    schema_version: SchemaVersion = GRAPH_SCHEMA


class ContextGraph:
    """A deterministic multigraph whose public order never depends on insertion."""

    def __init__(
        self,
        *,
        dependency_edge_types: Iterable[EdgeType] = DEFAULT_DEPENDENCY_EDGE_TYPES,
        schema_version: SchemaVersion = GRAPH_SCHEMA,
    ) -> None:
        require_schema_version(
            schema_version,
            expected=GRAPH_SCHEMA,
            artifact="ContextGraph",
        )
        parsed_types = frozenset(dependency_edge_types)
        if not all(isinstance(kind, EdgeType) for kind in parsed_types):
            raise SourceValidationError("dependency edge types must be EdgeType values")
        self.schema_version = schema_version
        self.dependency_edge_types = parsed_types
        self._nodes: dict[str, ContextNode] = {}
        self._edges: dict[str, ContextEdge] = {}

    @property
    def node_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._nodes))

    @property
    def nodes(self) -> tuple[ContextNode, ...]:
        return tuple(self._nodes[node_id] for node_id in self.node_ids)

    @property
    def edges(self) -> tuple[ContextEdge, ...]:
        return tuple(sorted(self._edges.values(), key=self._edge_sort_key))

    @property
    def semantic_identity(self) -> str:
        return semantic_hash(self.to_dict())

    @staticmethod
    def _edge_sort_key(edge: ContextEdge) -> tuple[str, str, str, str]:
        return (
            edge.source_node_id,
            edge.target_node_id,
            edge.edge_type.value,
            edge.edge_id,
        )

    def add_node(self, node: ContextNode) -> None:
        existing = self._nodes.get(node.node_id)
        if existing is not None and existing != node:
            raise GraphInvariantError(f"node identity collision: {node.node_id}")
        self._nodes[node.node_id] = node

    def get_node(self, node_id: str) -> ContextNode:
        try:
            return self._nodes[node_id]
        except KeyError as error:
            raise GraphInvariantError(f"unknown graph node: {node_id}") from error

    def remove_node(self, node_id: str) -> ContextNode:
        node = self.get_node(node_id)
        incident = [
            edge_id
            for edge_id, edge in self._edges.items()
            if node_id in {edge.source_node_id, edge.target_node_id}
        ]
        for edge_id in incident:
            del self._edges[edge_id]
        del self._nodes[node_id]
        return node

    def add_edge(self, edge: ContextEdge) -> None:
        missing = sorted(
            endpoint
            for endpoint in {edge.source_node_id, edge.target_node_id}
            if endpoint not in self._nodes
        )
        if missing:
            raise GraphInvariantError(f"edge endpoints are absent from graph: {missing}")
        existing = self._edges.get(edge.edge_id)
        if existing is not None and existing != edge:
            raise GraphInvariantError(f"edge identity collision: {edge.edge_id}")
        # Identical edges are idempotent. Semantically distinct parallel edges
        # have distinct identities and are retained.
        self._edges[edge.edge_id] = edge

    def get_edge(self, edge_id: str) -> ContextEdge:
        try:
            return self._edges[edge_id]
        except KeyError as error:
            raise GraphInvariantError(f"unknown graph edge: {edge_id}") from error

    def remove_edge(self, edge_id: str) -> ContextEdge:
        edge = self.get_edge(edge_id)
        del self._edges[edge_id]
        return edge

    @staticmethod
    def _kind_filter(kinds: Iterable[EdgeType] | None) -> frozenset[EdgeType] | None:
        return None if kinds is None else frozenset(kinds)

    def incoming_edges(
        self, node_id: str, *, kinds: Iterable[EdgeType] | None = None
    ) -> tuple[ContextEdge, ...]:
        self.get_node(node_id)
        selected = self._kind_filter(kinds)
        return tuple(
            edge
            for edge in self.edges
            if edge.target_node_id == node_id and (selected is None or edge.edge_type in selected)
        )

    def outgoing_edges(
        self, node_id: str, *, kinds: Iterable[EdgeType] | None = None
    ) -> tuple[ContextEdge, ...]:
        self.get_node(node_id)
        selected = self._kind_filter(kinds)
        return tuple(
            edge
            for edge in self.edges
            if edge.source_node_id == node_id and (selected is None or edge.edge_type in selected)
        )

    def subgraph(self, node_ids: Iterable[str]) -> ContextGraph:
        requested = frozenset(node_ids)
        missing = sorted(requested - self._nodes.keys())
        if missing:
            raise GraphInvariantError(f"subgraph nodes are absent: {missing}")
        result = ContextGraph(
            dependency_edge_types=self.dependency_edge_types,
            schema_version=self.schema_version,
        )
        for node_id in sorted(requested):
            result.add_node(self._nodes[node_id])
        for edge in self.edges:
            if edge.source_node_id in requested and edge.target_node_id in requested:
                result.add_edge(edge)
        return result

    def _dependency_neighbors(self, node_id: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    edge.target_node_id
                    for edge in self.outgoing_edges(node_id, kinds=self.dependency_edge_types)
                }
            )
        )

    def dependency_closure(self, seed_node_ids: Iterable[str]) -> DependencyClosure:
        seeds = frozenset(seed_node_ids)
        missing = tuple(sorted(seeds - self._nodes.keys()))
        present_seeds = sorted(seeds & self._nodes.keys())
        included = set(present_seeds)
        pending = list(present_seeds)
        while pending:
            current = heapq.heappop(pending)
            for dependency in self._dependency_neighbors(current):
                if dependency not in included:
                    included.add(dependency)
                    heapq.heappush(pending, dependency)
        forced = tuple(sorted(included - seeds))
        diagnostics: list[Diagnostic] = []
        for node_id in missing:
            diagnostics.append(
                self._diagnostic(
                    DiagnosticCode.MISSING_DEPENDENCY,
                    (node_id,),
                    {"missing_node_id": node_id},
                )
            )
        for node_id in forced:
            diagnostics.append(
                self._diagnostic(
                    DiagnosticCode.DEPENDENCY_FORCED_INCLUSION,
                    (node_id,),
                    {"forced_node_id": node_id},
                )
            )
        cycles = self.dependency_cycles(included)
        for cycle in cycles:
            diagnostics.append(
                self._diagnostic(
                    DiagnosticCode.DEPENDENCY_CYCLE,
                    cycle,
                    {"cycle_node_ids": cycle},
                )
            )
        return DependencyClosure(
            node_ids=tuple(sorted(included)),
            dependency_forced_node_ids=forced,
            missing_node_ids=missing,
            diagnostics=tuple(diagnostics),
        )

    @staticmethod
    def _diagnostic(
        code: DiagnosticCode,
        node_ids: tuple[str, ...],
        evidence: Mapping[str, object],
    ) -> Diagnostic:
        definition = get_definition(code)
        return Diagnostic(
            code=code,
            severity=definition.default_severity,
            message=definition.title,
            node_ids=node_ids,
            evidence=evidence,
            owning_pass="context_graph",
        )

    def dependency_cycles(
        self, node_ids: Iterable[str] | None = None
    ) -> tuple[tuple[str, ...], ...]:
        selected = set(self.node_ids if node_ids is None else node_ids)
        unknown = sorted(selected - self._nodes.keys())
        if unknown:
            raise GraphInvariantError(f"cycle inspection nodes are absent: {unknown}")
        index = 0
        indices: dict[str, int] = {}
        lowlinks: dict[str, int] = {}
        stack: list[str] = []
        on_stack: set[str] = set()
        components: list[tuple[str, ...]] = []

        def visit(node_id: str) -> None:
            nonlocal index
            indices[node_id] = index
            lowlinks[node_id] = index
            index += 1
            stack.append(node_id)
            on_stack.add(node_id)
            for target in self._dependency_neighbors(node_id):
                if target not in selected:
                    continue
                if target not in indices:
                    visit(target)
                    lowlinks[node_id] = min(lowlinks[node_id], lowlinks[target])
                elif target in on_stack:
                    lowlinks[node_id] = min(lowlinks[node_id], indices[target])
            if lowlinks[node_id] == indices[node_id]:
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.remove(member)
                    component.append(member)
                    if member == node_id:
                        break
                if len(component) > 1:
                    components.append(tuple(sorted(component)))

        for node_id in sorted(selected):
            if node_id not in indices:
                visit(node_id)
        return tuple(sorted(components))

    def topological_dependency_order(
        self, node_ids: Iterable[str] | None = None
    ) -> tuple[str, ...]:
        selected = set(self.node_ids if node_ids is None else node_ids)
        unknown = sorted(selected - self._nodes.keys())
        if unknown:
            raise GraphInvariantError(f"topological nodes are absent: {unknown}")
        cycles = self.dependency_cycles(selected)
        if cycles:
            raise DependencyCycleError(cycles)
        dependency_count = {node_id: 0 for node_id in selected}
        dependents = {node_id: set[str]() for node_id in selected}
        for source_id in sorted(selected):
            dependencies = {
                target for target in self._dependency_neighbors(source_id) if target in selected
            }
            dependency_count[source_id] = len(dependencies)
            for dependency in dependencies:
                dependents[dependency].add(source_id)
        ready = [node_id for node_id, count in dependency_count.items() if count == 0]
        heapq.heapify(ready)
        result: list[str] = []
        while ready:
            node_id = heapq.heappop(ready)
            result.append(node_id)
            for dependent in sorted(dependents[node_id]):
                dependency_count[dependent] -= 1
                if dependency_count[dependent] == 0:
                    heapq.heappush(ready, dependent)
        return tuple(result)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": {
                "major": self.schema_version.major,
                "minor": self.schema_version.minor,
            },
            "dependency_edge_types": sorted(kind.value for kind in self.dependency_edge_types),
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ContextGraph:
        version = require_schema_version(
            value.get("schema_version"), expected=GRAPH_SCHEMA, artifact="ContextGraph"
        )
        raw_types = require_sequence(
            value.get("dependency_edge_types"), "graph.dependency_edge_types"
        )
        dependency_types: list[EdgeType] = []
        for raw_type in raw_types:
            name = require_string(raw_type, "graph.dependency_edge_type")
            try:
                dependency_types.append(EdgeType(name))
            except ValueError as error:
                raise SourceValidationError(f"unknown dependency edge type: {name}") from error
        raw_nodes = require_sequence(value.get("nodes"), "graph.nodes")
        raw_edges = require_sequence(value.get("edges"), "graph.edges")
        result = cls(dependency_edge_types=dependency_types, schema_version=version)
        for raw_node in raw_nodes:
            result.add_node(ContextNode.from_dict(require_mapping(raw_node, "graph.node")))
        for raw_edge in raw_edges:
            result.add_edge(ContextEdge.from_dict(require_mapping(raw_edge, "graph.edge")))
        return result
