from __future__ import annotations

import inspect
import json
import shutil
from pathlib import Path

from contextc.cross_domain.conflicts import analyze_conflicts
from contextc.cross_domain.incident import IncidentAdapter
from contextc.cross_domain.supersession import analyze_supersession
from contextc.diagnostics import DiagnosticCode
from contextc.ir import ContextEdge, ContextNode, EdgeType, NodeKind, SourceReference
from contextc.optimization import strategies as optimizer_strategies


def demo_root() -> Path:
    return Path("contextc/resources/demos/incidents/checkout-latency-001/public")


def test_incident_adapter_is_deterministic_and_heterogeneous() -> None:
    first = IncidentAdapter().parse(demo_root())
    second = IncidentAdapter().parse(demo_root())
    assert first.index.files_considered == 21
    assert len(first.index.nodes) == 22
    assert len(first.graph.edges) == 12
    assert first.graph.semantic_identity == second.graph.semantic_identity
    kinds = {node.kind for node in first.index.nodes}
    assert {
        NodeKind.DOCUMENT_SECTION,
        NodeKind.EVENT,
        NodeKind.OBSERVATION,
        NodeKind.RECORD,
        NodeKind.PROCEDURE,
        NodeKind.CONVERSATION_MESSAGE,
        NodeKind.TOOL_RESULT,
    } <= kinds
    assert all(node.source.uri.startswith(("incident://", "mcp://")) for node in first.index.nodes)


def test_manifest_discovery_order_does_not_change_semantics(tmp_path: Path) -> None:
    copied = tmp_path / "public"
    shutil.copytree(demo_root(), copied)
    manifest_path = copied / "incident.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw["sources"] = list(reversed(raw["sources"]))
    raw["relationships"] = list(reversed(raw["relationships"]))
    manifest_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    original = IncidentAdapter().parse(demo_root())
    reversed_order = IncidentAdapter().parse(copied)
    assert original.graph.semantic_identity == reversed_order.graph.semantic_identity
    assert original.index.nodes == reversed_order.index.nodes


def test_operational_timestamps_are_timezone_aware_and_canonical() -> None:
    adapted = IncidentAdapter().parse(demo_root())
    incident_nodes = tuple(
        node for node in adapted.index.nodes if node.source.uri.startswith("incident://")
    )
    assert incident_nodes
    assert all(
        node.created_at is not None and node.created_at.endswith("Z") for node in incident_nodes
    )


def test_universal_node_and_edge_values_round_trip() -> None:
    node = ContextNode.create(
        node_id="conversation",
        kind=NodeKind.CONVERSATION_MESSAGE,
        content="operator update",
        source=SourceReference(uri="incident://example/chat"),
    )
    assert ContextNode.from_dict(node.to_dict()) == node
    edge = ContextEdge(
        source_node_id="a",
        target_node_id="b",
        edge_type=EdgeType.CORRELATES_WITH,
        evidence={"reason": "time-aligned"},
    )
    assert ContextEdge.from_dict(edge.to_dict()) == edge


def test_explicit_supersession_marks_old_runbook_and_emits_ctx210() -> None:
    adapted = IncidentAdapter().parse(demo_root())
    aliases = {
        str(node.metadata["incident_alias"]): node.node_id
        for node in adapted.graph.nodes
        if "incident_alias" in node.metadata
    }
    result = analyze_supersession(adapted.graph)
    assert result.superseded_node_ids == (aliases["old_runbook"],)
    assert result.superseding_node_by_id[aliases["old_runbook"]] == aliases["current_runbook"]
    assert [item.code for item in result.diagnostics] == [DiagnosticCode.STALE_OR_SUPERSEDED]


def test_structural_supersession_beats_timestamp_age(tmp_path: Path) -> None:
    copied = tmp_path / "public"
    shutil.copytree(demo_root(), copied)
    manifest_path = copied / "incident.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    for source in raw["sources"]:
        if source.get("alias") == "old_runbook":
            source["created_at"] = "2026-09-03T17:19:00-07:00"
        if source.get("alias") == "current_runbook":
            source["created_at"] = "2026-01-01T00:00:00Z"
    manifest_path.write_text(json.dumps(raw), encoding="utf-8")
    adapted = IncidentAdapter().parse(copied)
    aliases = {
        str(node.metadata["incident_alias"]): node.node_id
        for node in adapted.graph.nodes
        if "incident_alias" in node.metadata
    }
    result = analyze_supersession(adapted.graph)
    assert result.superseded_node_ids == (aliases["old_runbook"],)
    assert result.superseding_node_by_id[aliases["old_runbook"]] == aliases["current_runbook"]


def test_contradiction_is_diagnostic_not_hard_block() -> None:
    adapted = IncidentAdapter().parse(demo_root())
    result = analyze_conflicts(adapted.graph)
    assert result.diagnostics
    assert all(item.code is DiagnosticCode.INSTRUCTION_CONFLICT for item in result.diagnostics)
    assert all(item.severity.value == "warning" for item in result.diagnostics)


def test_optimizer_has_no_incident_specific_branch() -> None:
    source = inspect.getsource(optimizer_strategies)
    assert "incident" not in source.casefold()
