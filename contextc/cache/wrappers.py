"""Serialization helpers for actual reusable M8 intermediate stages."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING

from contextc.canonical import canonical_json_bytes
from contextc.diagnostics import Diagnostic
from contextc.ir import ContextGraph
from contextc.parsers import IndexResult


def _list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return value


if TYPE_CHECKING:
    from contextc.cross_domain.supersession import SupersessionResult
    from contextc.security import SecurityResult


def encode_adapted_context(
    index: IndexResult, graph: ContextGraph, *, adapter_id: str, adapter_version: str
) -> bytes:
    return canonical_json_bytes(
        {
            "adapter_id": adapter_id,
            "adapter_version": adapter_version,
            "index": {
                "root": index.root,
                "nodes": [node.to_dict() for node in index.nodes],
                "diagnostics": [d.to_dict() for d in index.diagnostics],
                "files_considered": index.files_considered,
                "schema_version": index.schema_version,
            },
            "graph": graph.to_dict(),
        }
    )


def decode_adapted_context(payload: bytes) -> tuple[IndexResult, ContextGraph, str, str]:
    raw = json.loads(payload.decode("utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("cached adapted context must be an object")
    index_raw = raw["index"]
    if not isinstance(index_raw, Mapping):
        raise ValueError("cached index must be an object")
    from contextc.ir import ContextNode

    nodes_raw = index_raw["nodes"]
    diagnostics_raw = index_raw["diagnostics"]
    if not isinstance(nodes_raw, list) or not isinstance(diagnostics_raw, list):
        raise ValueError("cached index arrays malformed")
    index = IndexResult(
        root=str(index_raw["root"]),
        nodes=tuple(ContextNode.from_dict(v) for v in nodes_raw if isinstance(v, Mapping)),
        diagnostics=tuple(
            Diagnostic.from_dict(v) for v in diagnostics_raw if isinstance(v, Mapping)
        ),
        files_considered=int(index_raw["files_considered"]),
        schema_version=int(index_raw["schema_version"]),
    )
    graph_raw = raw["graph"]
    if not isinstance(graph_raw, Mapping):
        raise ValueError("cached graph must be an object")
    return (
        index,
        ContextGraph.from_dict(graph_raw),
        str(raw["adapter_id"]),
        str(raw["adapter_version"]),
    )


def encode_security_result(result: object) -> bytes:
    from contextc.canonical import to_canonical_primitive
    from contextc.security import SecurityResult

    if not isinstance(result, SecurityResult):
        raise TypeError("expected SecurityResult")
    value = to_canonical_primitive(result)
    return canonical_json_bytes(value)


def decode_security_result(payload: bytes) -> SecurityResult:
    from contextc.diagnostics import Diagnostic
    from contextc.ir import ContextNode
    from contextc.security import (
        PolicyAction,
        SecurityDecision,
        SecurityResult,
        TaintPath,
    )

    raw = json.loads(payload.decode("utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("cached security result must be an object")

    def path_from(value: object) -> TaintPath | None:
        if value is None:
            return None
        if not isinstance(value, Mapping):
            raise ValueError("cached taint path malformed")
        return TaintPath(
            rule_id=str(value["rule_id"]),
            node_ids=tuple(str(v) for v in _list(value.get("node_ids"), "node_ids")),
            edge_ids=tuple(str(v) for v in _list(value.get("edge_ids"), "edge_ids")),
            source_node_id=str(value["source_node_id"]),
            sink_node_id=str(value["sink_node_id"]),
        )

    def required_path_from(value: object) -> TaintPath:
        path = path_from(value)
        if path is None:
            raise ValueError("cached taint_paths entries may not be null")
        return path

    nodes_raw = raw["nodes"]
    diagnostics_raw = raw["diagnostics"]
    decisions_raw = raw["decisions"]
    paths_raw = raw["taint_paths"]
    if (
        not isinstance(nodes_raw, list)
        or not isinstance(diagnostics_raw, list)
        or not isinstance(decisions_raw, list)
        or not isinstance(paths_raw, list)
    ):
        raise ValueError("cached security arrays malformed")
    decisions = []
    for item in decisions_raw:
        if not isinstance(item, Mapping):
            raise ValueError("cached security decision malformed")
        decisions.append(
            SecurityDecision(
                node_id=str(item["node_id"]),
                rule_id=str(item["rule_id"]),
                action=PolicyAction(str(item["action"])),
                diagnostic_code=None
                if item.get("diagnostic_code") is None
                else str(item["diagnostic_code"]),
                reason=str(item["reason"]),
                taint_path=path_from(item.get("taint_path")),
            )
        )
    transformations_raw = raw.get("transformations", {})
    if not isinstance(transformations_raw, Mapping):
        raise ValueError("cached security transformations malformed")
    return SecurityResult(
        policy_id=str(raw["policy_id"]),
        policy_version=str(raw["policy_version"]),
        policy_identity=str(raw["policy_identity"]),
        analysis_version=str(raw["analysis_version"]),
        nodes=tuple(ContextNode.from_dict(v) for v in nodes_raw if isinstance(v, Mapping)),
        diagnostics=tuple(
            Diagnostic.from_dict(v) for v in diagnostics_raw if isinstance(v, Mapping)
        ),
        decisions=tuple(decisions),
        taint_paths=tuple(required_path_from(v) for v in paths_raw),
        excluded_node_ids=tuple(
            str(v) for v in _list(raw.get("excluded_node_ids", []), "excluded_node_ids")
        ),
        blocked_node_ids=tuple(
            str(v) for v in _list(raw.get("blocked_node_ids", []), "blocked_node_ids")
        ),
        transformations={
            str(k): tuple(str(x) for x in _list(v, "transformation entries"))
            for k, v in transformations_raw.items()
        },
        blocked=bool(raw.get("blocked", False)),
    )


def encode_supersession_result(result: object) -> bytes:
    from contextc.canonical import to_canonical_primitive
    from contextc.cross_domain.supersession import SupersessionResult

    if not isinstance(result, SupersessionResult):
        raise TypeError("expected SupersessionResult")
    return canonical_json_bytes(to_canonical_primitive(result))


def decode_supersession_result(payload: bytes) -> SupersessionResult:
    from contextc.cross_domain.supersession import SupersessionResult
    from contextc.diagnostics import Diagnostic

    raw = json.loads(payload.decode("utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("cached supersession result must be an object")
    diagnostics_raw = raw.get("diagnostics", [])
    mapping_raw = raw.get("superseding_node_by_id", {})
    if not isinstance(diagnostics_raw, list) or not isinstance(mapping_raw, Mapping):
        raise ValueError("cached supersession result malformed")
    return SupersessionResult(
        policy_id=str(raw["policy_id"]),
        policy_version=str(raw["policy_version"]),
        policy_identity=str(raw["policy_identity"]),
        superseded_node_ids=tuple(
            str(v) for v in _list(raw.get("superseded_node_ids", []), "superseded_node_ids")
        ),
        superseding_node_by_id={str(k): str(v) for k, v in mapping_raw.items()},
        diagnostics=tuple(
            Diagnostic.from_dict(v) for v in diagnostics_raw if isinstance(v, Mapping)
        ),
    )
