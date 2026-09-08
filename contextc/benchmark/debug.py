"""One-task debug report for source/span mismatch diagnosis."""

from __future__ import annotations

from contextc.canonical import to_canonical_primitive

from .models import GroundTruth
from .public import PublicBenchmarkTask
from .runner import PublicCompilation
from .source import selected_span_from_source


def one_task_debug_report(
    task: PublicBenchmarkTask,
    labels: GroundTruth,
    compilations: tuple[PublicCompilation, ...],
) -> dict[str, object]:
    """Expose IDs for debugging while keeping canonical spans authoritative."""

    if not compilations:
        raise ValueError("debug report requires at least one compilation")
    first = compilations[0].result
    actual_nodes = []
    for node in first.graph.nodes:
        span = selected_span_from_source(
            source_uri=node.source.uri,
            start_line=node.source.start_line,
            end_line=node.source.end_line,
            repository_id=task.repository_id,
        )
        actual_nodes.append(
            {
                "node_id": node.node_id,
                "source_uri": span.source_uri,
                "start_line": span.start_line,
                "end_line": span.end_line,
            }
        )
    selected_by_strategy: dict[str, object] = {}
    for compilation in compilations:
        result = compilation.result
        selected_by_strategy[result.selection.requested_strategy_id] = [
            {
                "node_id": node_id,
                "source": to_canonical_primitive(
                    selected_span_from_source(
                        source_uri=result.graph.get_node(node_id).source.uri,
                        start_line=result.graph.get_node(node_id).source.start_line,
                        end_line=result.graph.get_node(node_id).source.end_line,
                        repository_id=task.repository_id,
                    )
                ),
            }
            for node_id in result.rendered.ordered_node_ids
        ]
    return {
        "task_description": task.description,
        "expected_source_uris": sorted({span.source_uri for span in labels.required_spans}),
        "expected_source_spans": to_canonical_primitive(labels.required_spans),
        "expected_node_ids_debug_only": labels.debug_expected_node_ids,
        "actual_ir_ids": tuple(node.node_id for node in first.graph.nodes),
        "actual_normalized_locations": actual_nodes,
        "selected_by_strategy": selected_by_strategy,
    }
