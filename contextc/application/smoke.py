"""M1 end-to-end application service."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from contextc.hashing import semantic_hash
from contextc.ir.analysis import NodeAnalysis
from contextc.ir.compilation import CompiledContext, SelectionResult
from contextc.ir.nodes import ContextNode
from contextc.parsers.base import IndexPolicy, IndexResult
from contextc.parsers.repository import RepositoryParser
from contextc.targets.generic import render_generic

_TERM = re.compile(r"[A-Za-z0-9_]+")


@dataclass(frozen=True, slots=True)
class SmokeCompilation:
    index: IndexResult
    analyses: tuple[NodeAnalysis, ...]
    compiled: CompiledContext


def _analyze(node: ContextNode, task: str) -> NodeAnalysis:
    terms = tuple(term.lower() for term in _TERM.findall(task))
    lowered = node.content.lower()
    matches = sum(term in lowered for term in terms)
    relevance = matches / max(1, len(terms))
    return NodeAnalysis(
        node_id=node.node_id,
        relevance=relevance,
        trust_score=1.0,
        freshness=0.0,
        security_risk=0.0,
        redundancy_score=0.0,
        metadata={"analysis": "m1_lexical_smoke", "task_term_count": len(terms)},
    )


def compile_repository(
    root: Path, *, task: str, policy: IndexPolicy | None = None
) -> SmokeCompilation:
    """Prove parser -> source IR -> analysis -> selection -> Generic lowering."""

    index = RepositoryParser(policy).parse(root)
    analyses = tuple(_analyze(node, task) for node in index.nodes)
    selected = tuple(node.node_id for node in index.nodes)
    selection = SelectionResult(selected_node_ids=selected)
    rendered = render_generic(index.nodes)
    compiled = CompiledContext(
        rendered_text=rendered,
        selection=selection,
        semantic_hash=semantic_hash(
            {
                "target": "generic-m1-smoke",
                "selected_node_ids": selected,
                "rendered_text": rendered,
            }
        ),
    )
    return SmokeCompilation(index=index, analyses=analyses, compiled=compiled)
