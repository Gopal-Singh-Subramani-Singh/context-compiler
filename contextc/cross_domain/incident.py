"""Offline heterogeneous incident-response adapter for the M15 proof."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from contextc.canonical import canonical_json_text, normalize_text
from contextc.cross_domain.adapters import AdaptedContext
from contextc.hashing import semantic_hash
from contextc.ir import (
    ContextEdge,
    ContextGraph,
    ContextNode,
    EdgeType,
    InstructionAuthority,
    NodeKind,
    Sensitivity,
    SourceReference,
    TrustDomain,
)
from contextc.parsers import IndexResult
from contextc.parsers.mcp import StaticMcpParser


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be an object")
    return value


def _sequence(value: object, name: str) -> tuple[object, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    return tuple(value)


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be non-empty text")
    return value


def _timestamp(value: object, name: str) -> str:
    text = _text(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{name} must be ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_content(path: Path) -> str:
    suffix = path.suffix.lower()
    text = normalize_text(path.read_text(encoding="utf-8"))
    if suffix == ".json":
        return canonical_json_text(json.loads(text))
    if suffix == ".jsonl":
        lines = [line for line in text.splitlines() if line.strip()]
        return "\n".join(canonical_json_text(json.loads(line)) for line in lines)
    return text


class IncidentAdapter:
    """Parse one retained incident fixture into the ordinary Context IR/graph."""

    adapter_id = "incident"
    adapter_version = "1.0.0"

    def parse(self, root: Path, *, revision: str | None = None) -> AdaptedContext:
        if revision is not None:
            raise ValueError("incident adapter uses retained content and does not accept revisions")
        root = root.resolve()
        manifest_path = root / "incident.json"
        if not manifest_path.is_file():
            raise ValueError(f"incident manifest is unavailable: {manifest_path}")
        raw = _mapping(json.loads(manifest_path.read_text(encoding="utf-8")), "incident")
        incident_id = _text(raw.get("incident_id"), "incident_id")
        _timestamp(raw.get("time_anchor"), "time_anchor")
        sources_root = root / "sources"
        nodes: list[ContextNode] = []
        edges: list[ContextEdge] = []
        aliases: dict[str, str] = {}
        files_considered = 0

        for raw_source in _sequence(raw.get("sources"), "sources"):
            source = _mapping(raw_source, "source")
            relative = Path(_text(source.get("path"), "source.path"))
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("incident source paths must be relative and contained")
            path = sources_root / relative
            if not path.is_file():
                raise ValueError(f"incident source is unavailable: {relative.as_posix()}")
            files_considered += 1
            kind_text = _text(source.get("kind"), "source.kind")
            if kind_text == "mcp":
                parsed = StaticMcpParser().parse_file(path)
                nodes.extend(parsed.nodes)
                edges.extend(parsed.edges)
                raw_aliases = source.get("mcp_aliases", {})
                alias_map = _mapping(raw_aliases, "mcp_aliases")
                for node_id, alias in alias_map.items():
                    if node_id not in {node.node_id for node in parsed.nodes}:
                        raise ValueError(f"MCP alias references unknown node {node_id!r}")
                    aliases[_text(alias, "mcp alias")] = node_id
                continue

            try:
                kind = NodeKind(kind_text)
                trust = TrustDomain(str(source.get("trust_domain", "local_repository")))
                sensitivity = Sensitivity(str(source.get("sensitivity", "internal")))
                authority = InstructionAuthority(str(source.get("instruction_authority", "none")))
            except ValueError as error:
                raise ValueError(f"unsupported incident source classification: {error}") from error
            alias = _text(source.get("alias"), "source.alias")
            created_at = _timestamp(source.get("created_at"), f"{alias}.created_at")
            uri = f"incident://{incident_id}/{relative.as_posix()}"
            content = _read_content(path)
            node_id = (
                "incident-"
                + semantic_hash(
                    {"incident_id": incident_id, "uri": uri, "kind": kind.value, "content": content}
                ).split(":", 1)[1][:24]
            )
            if alias in aliases:
                raise ValueError(f"duplicate incident source alias {alias!r}")
            aliases[alias] = node_id
            nodes.append(
                ContextNode.create(
                    node_id=node_id,
                    kind=kind,
                    content=content,
                    source=SourceReference(uri=uri),
                    created_at=created_at,
                    trust_domain=trust,
                    sensitivity=sensitivity,
                    instruction_authority=authority,
                    metadata={
                        "incident_alias": alias,
                        "incident_id": incident_id,
                        "relative_path": relative.as_posix(),
                    },
                )
            )

        node_ids = {node.node_id for node in nodes}
        for raw_relation in _sequence(raw.get("relationships", []), "relationships"):
            relation = _mapping(raw_relation, "relationship")
            source_alias = _text(relation.get("source"), "relationship.source")
            target_alias = _text(relation.get("target"), "relationship.target")
            if source_alias not in aliases or target_alias not in aliases:
                raise ValueError(
                    "relationship aliases must reference parsed sources: "
                    f"{source_alias!r}, {target_alias!r}"
                )
            relation_kind = EdgeType(_text(relation.get("type"), "relationship.type"))
            edge = ContextEdge(
                source_node_id=aliases[source_alias],
                target_node_id=aliases[target_alias],
                edge_type=relation_kind,
                evidence={
                    "incident_id": incident_id,
                    "source_alias": source_alias,
                    "target_alias": target_alias,
                    "statement": _text(relation.get("evidence"), "relationship.evidence"),
                },
            )
            edges.append(edge)

        graph = ContextGraph()
        for node in sorted(nodes, key=lambda item: item.node_id):
            graph.add_node(node)
        for edge in sorted(
            edges,
            key=lambda item: (
                item.source_node_id,
                item.target_node_id,
                item.edge_type.value,
                item.edge_id,
            ),
        ):
            if edge.source_node_id not in node_ids or edge.target_node_id not in node_ids:
                raise ValueError("incident edge endpoint is absent from parsed nodes")
            graph.add_edge(edge)
        index = IndexResult(
            root=str(root),
            nodes=graph.nodes,
            diagnostics=(),
            files_considered=files_considered,
        )
        return AdaptedContext(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            index=index,
            graph=graph,
        )
