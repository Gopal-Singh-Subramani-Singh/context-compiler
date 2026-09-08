"""Evaluator-only M15 labels and metrics. Never imported by compilation paths."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from contextc.benchmark.metrics import calculate_raw_metrics
from contextc.benchmark.models import GroundTruth, RawMetrics, SelectedLocation
from contextc.benchmark.source import SourceSpan
from contextc.hashing import semantic_hash
from contextc.ir import ContextGraph


@dataclass(frozen=True, slots=True)
class IncidentDomainMetrics:
    required_relation_coverage: float
    superseded_content_exclusion_ratio: float
    security_policy_correctness: float


@dataclass(frozen=True, slots=True)
class IncidentEvaluation:
    label_identity: str
    raw_metrics: RawMetrics
    domain_metrics: IncidentDomainMetrics
    evaluator_sentinel: str


def load_incident_labels(public_root: Path) -> Mapping[str, object]:
    labels_path = public_root.parent / "evaluator" / "labels.json"
    raw = json.loads(labels_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping) or not all(isinstance(key, str) for key in raw):
        raise ValueError("incident evaluator labels must be an object")
    return raw


def alias_node_map(public_root: Path, graph: ContextGraph) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in graph.nodes:
        alias = node.metadata.get("incident_alias")
        if isinstance(alias, str) and alias:
            aliases[alias] = node.node_id
    manifest = json.loads((public_root / "incident.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping):
        raise ValueError("incident manifest must be an object")
    sources = manifest.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("incident manifest sources must be a list")
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        raw_aliases = source.get("mcp_aliases", {})
        if isinstance(raw_aliases, Mapping):
            for node_id, alias in raw_aliases.items():
                if isinstance(node_id, str) and isinstance(alias, str):
                    aliases[alias] = node_id
    return aliases


def _sequence(value: object) -> tuple[object, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(value)


def _span(incident_id: str, alias: str) -> SourceSpan:
    return SourceSpan(f"repo://m15-{incident_id}/{alias}", 1, 1)


def evaluate_incident(
    *,
    public_root: Path,
    result: object,
    compilation_latency_ms: float,
) -> IncidentEvaluation:
    """Evaluate only after compilation; labels never enter compiler inputs."""

    from contextc.application.compile import TargetCompilation

    if not isinstance(result, TargetCompilation):
        raise TypeError("incident evaluation requires TargetCompilation")
    labels = load_incident_labels(public_root)
    incident_id = str(labels["incident_id"])
    required = tuple(str(item) for item in _sequence(labels.get("required_aliases", ())))
    accepted = tuple(str(item) for item in _sequence(labels.get("accepted_support_aliases", ())))
    superseded = tuple(str(item) for item in _sequence(labels.get("superseded_aliases", ())))
    aliases = alias_node_map(public_root, result.source_graph)
    reverse = {node_id: alias for alias, node_id in aliases.items()}
    truth = GroundTruth(
        required_spans=tuple(_span(incident_id, alias) for alias in required),
        accepted_spans=tuple(_span(incident_id, alias) for alias in accepted),
        evaluator_sentinel=str(labels.get("sentinel", "")),
    )
    analysis_map = {item.node_id: item for item in result.analyses}
    tokenizer_id = result.rendered.tokenizer_identity.tokenizer_id
    selected_locations: list[SelectedLocation] = []
    for rank, node_id in enumerate(result.rendered.ordered_node_ids, start=1):
        alias = reverse.get(node_id, node_id)
        analysis = analysis_map[node_id]
        selected_locations.append(
            SelectedLocation(
                node_id=node_id,
                span=_span(incident_id, alias),
                source_tokens=analysis.token_counts[tokenizer_id],
                rank=rank,
            )
        )
    raw_metrics = calculate_raw_metrics(
        labels=truth,
        selected=selected_locations,
        final_rendered_tokens=result.rendered.exact_token_count,
        configured_budget=result.rendered.budget_evidence.configured_budget,
        compilation_latency_ms=compilation_latency_ms,
        optimizer_runtime_ms=result.selection.solver_runtime_ms,
    )

    required_relationships = labels.get("required_relationships", [])
    relation_hits = 0
    relation_total = 0
    if isinstance(required_relationships, list):
        edge_facts = {
            (edge.source_node_id, edge.target_node_id, edge.edge_type.value)
            for edge in result.source_graph.edges
        }
        for raw_relation in required_relationships:
            if not isinstance(raw_relation, list) or len(raw_relation) != 3:
                continue
            source_alias, target_alias, kind = map(str, raw_relation)
            relation_total += 1
            if (
                aliases.get(source_alias),
                aliases.get(target_alias),
                kind,
            ) in edge_facts:
                relation_hits += 1
    required_relation_coverage = 1.0 if relation_total == 0 else relation_hits / relation_total

    selected = set(result.rendered.ordered_node_ids)
    superseded_ids = [aliases[item] for item in superseded if item in aliases]
    superseded_excluded = sum(node_id not in selected for node_id in superseded_ids)
    superseded_ratio = 1.0 if not superseded_ids else superseded_excluded / len(superseded_ids)

    expected_actions = labels.get("expected_security_actions", {})
    action_checks: list[bool] = []
    if isinstance(expected_actions, Mapping):
        decision_map = {
            decision.node_id: decision.action.value for decision in result.security.decisions
        }
        for alias, expected in expected_actions.items():
            if isinstance(alias, str) and isinstance(expected, str) and alias in aliases:
                action_checks.append(decision_map.get(aliases[alias]) == expected)
    expected_codes = {str(item) for item in _sequence(labels.get("expected_diagnostics", ()))}
    actual_codes = {
        diagnostic.code.value
        for diagnostic in (*result.supersession.diagnostics, *result.security.diagnostics)
    }
    action_checks.extend(code in actual_codes for code in sorted(expected_codes))
    security_correctness = 1.0 if not action_checks else sum(action_checks) / len(action_checks)
    label_form = {key: value for key, value in labels.items() if key != "sentinel"}
    return IncidentEvaluation(
        label_identity=semantic_hash(label_form),
        raw_metrics=raw_metrics,
        domain_metrics=IncidentDomainMetrics(
            required_relation_coverage=required_relation_coverage,
            superseded_content_exclusion_ratio=superseded_ratio,
            security_policy_correctness=security_correctness,
        ),
        evaluator_sentinel=str(labels.get("sentinel", "")),
    )
