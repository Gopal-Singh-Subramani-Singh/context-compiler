"""Top-K retrieval tracing with post-compilation evaluator annotation."""

from __future__ import annotations

from dataclasses import replace

from .models import GroundTruth, TopKCandidate, TopKTrace
from .source import union_line_units


def record_top_k_trace(
    *,
    query_text: str,
    embedding_model_id: str,
    embedding_model_version: str,
    embedding_revision: str,
    candidates: tuple[tuple[str, object, float, bool], ...],
    selected_node_ids: tuple[str, ...],
    removed_node_ids: tuple[str, ...] = (),
) -> TopKTrace:
    """Record retriever-visible evidence without accepting evaluator labels."""

    from .source import SourceSpan

    typed = []
    for rank, (node_id, span, similarity, selected) in enumerate(candidates, start=1):
        if not isinstance(span, SourceSpan):
            raise TypeError("Top-K candidate span must be SourceSpan")
        typed.append(
            TopKCandidate(
                node_id=node_id,
                span=span,
                similarity=similarity,
                rank=rank,
                selected=selected,
            )
        )
    return TopKTrace(
        query_text=query_text,
        status="retrieved",
        embedding_model_id=embedding_model_id,
        embedding_model_version=embedding_model_version,
        embedding_revision=embedding_revision,
        candidates=tuple(typed),
        selected_node_ids=selected_node_ids,
        removed_node_ids=removed_node_ids,
    )


def attach_evaluator_overlap(trace: TopKTrace, labels: GroundTruth) -> TopKTrace:
    """Add label overlap only after retrieval/compilation has finished."""

    useful = union_line_units(labels.useful_spans)
    candidates = tuple(
        replace(
            item,
            evaluator_overlap_lines=sum(
                (item.span.source_uri, line) in useful
                for line in range(item.span.start_line, item.span.end_line + 1)
            ),
        )
        for item in trace.candidates
    )
    return replace(trace, candidates=candidates)
