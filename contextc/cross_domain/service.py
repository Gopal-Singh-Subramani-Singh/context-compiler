"""Typed application service for the offline M15 incident-response demo."""

from __future__ import annotations

import json
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING

from contextc.application.compile import (
    CompileRepositoryRequest,
    TargetCompilation,
    compile_prepared_target,
    compile_source_target,
    compile_source_to_path,
    prepare_source_target,
)
from contextc.benchmark.fingerprint import equal_footing_fingerprint
from contextc.canonical import to_canonical_primitive
from contextc.cross_domain.adapters import load_source_context
from contextc.hashing import semantic_hash
from contextc.optimization import OptimizerConfiguration
from contextc.reproduction import rebuild_build, verify_build
from contextc.targets import TargetId

if TYPE_CHECKING:
    from contextc.cross_domain.evaluator import IncidentEvaluation

DEFAULT_DEMO_ID = "checkout-latency-001"
DEFAULT_BUDGET = 4000
DEFAULT_STRATEGIES = (
    "naive",
    "recency",
    "top_k",
    "relevance_greedy",
    "density_greedy",
    "graph_closure_greedy",
    "brute_force",
    "dynamic_programming",
    "ilp",
    "auto",
)


@dataclass(frozen=True, slots=True)
class DemoDescriptor:
    demo_id: str
    title: str
    source_adapter_id: str
    default_target: str
    source_count: int


@dataclass(frozen=True, slots=True)
class DemoCompileResult:
    demo_id: str
    output_path: str | None
    manifest_path: str | None
    compilation: TargetCompilation


@dataclass(frozen=True, slots=True)
class StrategyComparison:
    strategy_id: str
    optimizer_status: str
    selected_node_ids: tuple[str, ...]
    final_token_count: int
    input_fingerprint: str
    evaluation: IncidentEvaluation


def _resources_root() -> Path:
    return Path(str(files("contextc").joinpath("resources", "demos", "incidents")))


def demo_public_root(demo_id: str) -> Path:
    root = _resources_root() / demo_id / "public"
    if not (root / "incident.json").is_file():
        raise ValueError(f"unknown incident demo {demo_id!r}")
    return root


def _metadata(demo_id: str) -> dict[str, object]:
    raw = json.loads((demo_public_root(demo_id) / "incident.json").read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("demo metadata must be an object")
    return raw


def list_demos() -> tuple[DemoDescriptor, ...]:
    descriptors: list[DemoDescriptor] = []
    for path in sorted(_resources_root().iterdir(), key=lambda item: item.name):
        if not path.is_dir() or not (path / "public" / "incident.json").is_file():
            continue
        raw = json.loads((path / "public" / "incident.json").read_text(encoding="utf-8"))
        descriptors.append(
            DemoDescriptor(
                demo_id=str(raw["incident_id"]),
                title=str(raw["title"]),
                source_adapter_id="incident",
                default_target=TargetId.STRUCTURED_JSON.value,
                source_count=len(raw["sources"]),
            )
        )
    return tuple(descriptors)


def _request(
    demo_id: str,
    *,
    strategy: str,
    budget: int,
    target: TargetId = TargetId.STRUCTURED_JSON,
) -> CompileRepositoryRequest:
    raw = _metadata(demo_id)
    from datetime import datetime

    anchor = datetime.fromisoformat(str(raw["time_anchor"]).replace("Z", "+00:00"))
    return CompileRepositoryRequest(
        repository=demo_public_root(demo_id),
        task=str(raw["task"]),
        target_id=target,
        token_budget=budget,
        time_anchor=anchor,
        source_adapter_id="incident",
        optimizer=OptimizerConfiguration(requested_strategy=strategy),
    )


def validate_demo(demo_id: str) -> dict[str, object]:
    public_root = demo_public_root(demo_id)
    adapted = load_source_context("incident", public_root)
    labels_path = public_root.parent / "evaluator" / "labels.json"
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    sentinel = str(labels.get("sentinel", ""))
    compiler_visible = json.dumps([node.to_dict() for node in adapted.index.nodes], sort_keys=True)
    return {
        "demo_id": demo_id,
        "valid": True,
        "source_files": adapted.index.files_considered,
        "nodes": len(adapted.index.nodes),
        "edges": len(adapted.graph.edges),
        "graph_identity": adapted.graph.semantic_identity,
        "evaluator_sentinel_absent": bool(sentinel) and sentinel not in compiler_visible,
    }


def compile_demo(
    demo_id: str,
    *,
    strategy: str = "auto",
    budget: int = DEFAULT_BUDGET,
    target: TargetId = TargetId.STRUCTURED_JSON,
    output_path: Path | None = None,
) -> DemoCompileResult:
    request = _request(demo_id, strategy=strategy, budget=budget, target=target)
    if output_path is None:
        result = compile_source_target(request)
        return DemoCompileResult(demo_id, None, None, result)
    result = compile_source_to_path(request, output_path)
    manifest = output_path.with_name(output_path.name + ".manifest.json")
    return DemoCompileResult(demo_id, str(output_path.resolve()), str(manifest.resolve()), result)


def compare_strategies(
    demo_id: str,
    *,
    strategies: tuple[str, ...] = DEFAULT_STRATEGIES,
    budget: int = DEFAULT_BUDGET,
) -> tuple[StrategyComparison, ...]:
    from contextc.cross_domain.evaluator import evaluate_incident

    base = _request(demo_id, strategy="auto", budget=budget)
    prepared = prepare_source_target(base)
    comparisons: list[StrategyComparison] = []
    fingerprints: set[str] = set()
    for strategy in strategies:
        request = replace(
            base,
            optimizer=replace(base.optimizer, requested_strategy=strategy),
        )
        started = time.perf_counter()
        result = compile_prepared_target(request, prepared)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        fingerprint = equal_footing_fingerprint(request, result)
        fingerprints.add(fingerprint)
        comparisons.append(
            StrategyComparison(
                strategy_id=strategy,
                optimizer_status=result.selection.optimizer_status.value,
                selected_node_ids=result.rendered.ordered_node_ids,
                final_token_count=result.rendered.exact_token_count,
                input_fingerprint=fingerprint,
                evaluation=evaluate_incident(
                    public_root=demo_public_root(demo_id),
                    result=result,
                    compilation_latency_ms=elapsed_ms,
                ),
            )
        )
    if len(fingerprints) != 1:
        raise ValueError(f"M15 strategies are not equal-footing: {sorted(fingerprints)}")
    return tuple(comparisons)


def graph_demo(
    demo_id: str,
    *,
    selected_only: bool = False,
    strategy: str = "auto",
    budget: int = DEFAULT_BUDGET,
) -> dict[str, object]:
    compiled = compile_demo(demo_id, strategy=strategy, budget=budget).compilation
    graph = compiled.source_graph
    selected = set(compiled.rendered.ordered_node_ids)
    nodes = tuple(
        node.to_dict() for node in graph.nodes if not selected_only or node.node_id in selected
    )
    retained = {str(item["node_id"]) for item in nodes}
    edges = tuple(
        edge.to_dict()
        for edge in graph.edges
        if not selected_only
        or (edge.source_node_id in retained and edge.target_node_id in retained)
    )
    return {
        "demo_id": demo_id,
        "graph_identity": graph.semantic_identity,
        "selected_only": selected_only,
        "nodes": nodes,
        "edges": edges,
    }


def explain_demo(
    demo_id: str,
    source_uri: str,
    *,
    strategy: str = "auto",
    budget: int = DEFAULT_BUDGET,
) -> dict[str, object]:
    """Explain from stored manifest evidence, never by inventing fresh reasons."""

    from contextc.reproduction import read_build_manifest

    with tempfile.TemporaryDirectory(prefix="contextc-m15-explain-") as temporary:
        artifact = Path(temporary) / "incident.json"
        compiled = compile_demo(demo_id, strategy=strategy, budget=budget, output_path=artifact)
        if compiled.manifest_path is None:
            raise AssertionError("demo explanation compile did not store a manifest")
        manifest = read_build_manifest(Path(compiled.manifest_path))
        security = manifest.security_evidence
        node_facts = security["node_facts"]
        if not isinstance(node_facts, dict | Mapping):
            raise AssertionError("stored node facts are not a mapping")
        matching_ids = tuple(
            sorted(
                node_id
                for node_id, facts in node_facts.items()
                if isinstance(facts, Mapping) and facts.get("source_uri") == source_uri
            )
        )
        if not matching_ids:
            raise ValueError(f"source URI is absent from demo: {source_uri}")
        decisions = security["decisions"]
        if not isinstance(decisions, tuple | list):
            raise AssertionError("stored security decisions are not a sequence")
        payload_nodes = []
        for node_id in matching_ids:
            relation_diags = tuple(
                item.to_dict()
                for item in manifest.diagnostics
                if node_id in item.node_ids and item.code.value in {"CTX200", "CTX210"}
            )
            successor_id = None
            successor_uri = None
            for item in manifest.diagnostics:
                if item.code.value != "CTX210" or not item.node_ids or item.node_ids[0] != node_id:
                    continue
                raw_successor = item.evidence.get("superseding_node_id")
                if isinstance(raw_successor, str):
                    successor_id = raw_successor
                    successor_facts = node_facts.get(raw_successor)
                    if isinstance(successor_facts, Mapping):
                        raw_uri = successor_facts.get("source_uri")
                        if isinstance(raw_uri, str):
                            successor_uri = raw_uri
            payload_nodes.append(
                {
                    "node_id": node_id,
                    "source_facts": node_facts[node_id],
                    "selected": node_id in manifest.ordered_selected_node_ids,
                    "excluded": node_id in manifest.excluded_node_ids,
                    "superseded": successor_id is not None,
                    "superseding_node_id": successor_id,
                    "superseding_source_uri": successor_uri,
                    "relationship_diagnostics": relation_diags,
                    "security_decisions": tuple(
                        item
                        for item in decisions
                        if isinstance(item, Mapping) and item.get("node_id") == node_id
                    ),
                    "security_transformations": security["transformations"].get(node_id, ())
                    if isinstance(security["transformations"], Mapping)
                    else (),
                }
            )
        return {
            "demo_id": demo_id,
            "source_uri": source_uri,
            "evidence_source": "stored_build_manifest",
            "nodes": tuple(payload_nodes),
        }


def reproduce_demo(
    demo_id: str,
    *,
    strategy: str = "auto",
    budget: int = DEFAULT_BUDGET,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="contextc-m15-") as temporary:
        root = Path(temporary)
        original = root / "incident.json"
        compiled = compile_demo(
            demo_id,
            strategy=strategy,
            budget=budget,
            output_path=original,
        )
        if compiled.manifest_path is None:
            raise AssertionError("demo transaction did not produce a manifest")
        manifest = Path(compiled.manifest_path)
        verified = verify_build(manifest)
        rebuilt_path = root / "rebuilt.json"
        rebuilt = rebuild_build(manifest, output_path=rebuilt_path)
        byte_identical = original.read_bytes() == rebuilt_path.read_bytes()
        return {
            "demo_id": demo_id,
            "verified": verified.status == "verified",
            "rebuilt": True,
            "byte_identical": byte_identical,
            "artifact_identity": verified.artifact_identity,
            "rebuilt_artifact_identity": rebuilt.artifact_identity,
            "final_token_count": rebuilt.final_token_count,
        }


def comparison_payload(comparisons: tuple[StrategyComparison, ...]) -> dict[str, object]:
    return {
        "strategies": to_canonical_primitive(comparisons),
        "equal_footing_fingerprint": comparisons[0].input_fingerprint if comparisons else None,
        "comparison_identity": semantic_hash(
            [
                {
                    "strategy_id": item.strategy_id,
                    "optimizer_status": item.optimizer_status,
                    "selected_node_ids": item.selected_node_ids,
                    "final_token_count": item.final_token_count,
                    "input_fingerprint": item.input_fingerprint,
                    "raw_metrics": {
                        key: value
                        for key, value in item.evaluation.raw_metrics.semantic_form().items()
                        if key not in {"compilation_latency_ms", "optimizer_runtime_ms"}
                    },
                    "domain_metrics": item.evaluation.domain_metrics,
                }
                for item in comparisons
            ]
        ),
    }
