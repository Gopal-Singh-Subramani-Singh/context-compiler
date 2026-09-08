"""Deterministic source-neutral supersession analysis for M15."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from contextc.canonical import to_canonical_primitive
from contextc.diagnostics import Diagnostic, DiagnosticCode, Severity
from contextc.hashing import semantic_hash
from contextc.ir import ContextGraph, EdgeType


@dataclass(frozen=True, slots=True)
class SupersessionPolicy:
    policy_id: str = "supersession-default"
    version: str = "1.0.0"
    exclude_superseded: bool = True

    def __post_init__(self) -> None:
        if not self.policy_id or not self.version:
            raise ValueError("supersession policy identity must not be empty")

    @property
    def identity(self) -> str:
        return semantic_hash(self)

    def to_dict(self) -> dict[str, object]:
        value = to_canonical_primitive(self)
        if not isinstance(value, dict):
            raise AssertionError("supersession policy did not canonicalize to object")
        return value


@dataclass(frozen=True, slots=True)
class SupersessionResult:
    policy_id: str
    policy_version: str
    policy_identity: str
    superseded_node_ids: tuple[str, ...]
    superseding_node_by_id: Mapping[str, str]
    diagnostics: tuple[Diagnostic, ...]


def analyze_supersession(
    graph: ContextGraph,
    policy: SupersessionPolicy | None = None,
) -> SupersessionResult:
    """Treat explicit old->new SUPERSEDES edges as authoritative evidence."""

    policy = SupersessionPolicy() if policy is None else policy
    pairs: dict[str, str] = {}
    diagnostics: list[Diagnostic] = []
    edges = tuple(edge for edge in graph.edges if edge.edge_type is EdgeType.SUPERSEDES)
    for edge in edges:
        old_id = edge.source_node_id
        new_id = edge.target_node_id
        existing = pairs.get(old_id)
        if existing is not None and existing != new_id:
            raise ValueError(
                f"superseded node {old_id!r} has multiple superseding nodes: "
                f"{existing!r}, {new_id!r}"
            )
        pairs[old_id] = new_id
        diagnostics.append(
            Diagnostic(
                code=DiagnosticCode.STALE_OR_SUPERSEDED,
                severity=Severity.INFO,
                message="A newer source explicitly supersedes this node.",
                node_ids=(old_id, new_id),
                evidence={
                    "edge_id": edge.edge_id,
                    "superseded_node_id": old_id,
                    "superseding_node_id": new_id,
                    "policy_id": policy.policy_id,
                },
                owning_pass="supersession_analysis",
            )
        )
    ordered = dict(sorted(pairs.items()))
    return SupersessionResult(
        policy_id=policy.policy_id,
        policy_version=policy.version,
        policy_identity=policy.identity,
        superseded_node_ids=tuple(ordered) if policy.exclude_superseded else (),
        superseding_node_by_id=ordered,
        diagnostics=tuple(sorted(diagnostics, key=lambda item: item.node_ids)),
    )
