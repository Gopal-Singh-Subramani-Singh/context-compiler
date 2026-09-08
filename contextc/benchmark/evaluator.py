"""Evaluator-side scoring; this module is never imported by public compilation."""

from __future__ import annotations

from contextc.hashing import semantic_hash

from .fingerprint import analysis_identity, equal_footing_fingerprint
from .metrics import calculate_raw_metrics
from .models import BenchmarkRun, GroundTruth, SelectedLocation, TopKTrace
from .public import PublicBenchmarkTask
from .runner import PublicCompilation
from .source import selected_span_from_source


def _selected_locations(
    compilation: PublicCompilation, repository_id: str
) -> tuple[SelectedLocation, ...]:
    result = compilation.result
    analyses = {item.node_id: item for item in result.analyses}
    locations = []
    for rank, node_id in enumerate(result.rendered.ordered_node_ids, start=1):
        node = result.graph.get_node(node_id)
        locations.append(
            SelectedLocation(
                node_id=node_id,
                span=selected_span_from_source(
                    source_uri=node.source.uri,
                    start_line=node.source.start_line,
                    end_line=node.source.end_line,
                    repository_id=repository_id,
                ),
                source_tokens=analyses[node_id].token_counts[
                    result.rendered.tokenizer_identity.tokenizer_id
                ],
                rank=rank,
            )
        )
    return tuple(locations)


def evaluate_public_compilation(
    task: PublicBenchmarkTask,
    compilation: PublicCompilation,
    labels: GroundTruth,
) -> BenchmarkRun:
    """Attach evaluator labels only after compilation has completed."""

    result = compilation.result
    selected = _selected_locations(compilation, task.repository_id)
    metrics = calculate_raw_metrics(
        labels=labels,
        selected=selected,
        final_rendered_tokens=result.rendered.exact_token_count,
        configured_budget=result.rendered.budget_evidence.configured_budget,
        compilation_latency_ms=compilation.compilation_latency_ms,
        optimizer_runtime_ms=result.selection.solver_runtime_ms,
    )
    trace = None
    if result.selection.requested_strategy_id == "top_k":
        trace = TopKTrace(
            query_text=task.description,
            status="fallback" if result.selection.strategy_id != "top_k" else "unsupported",
            selected_node_ids=result.selection.selected_node_ids,
            removed_node_ids=tuple(
                node_id
                for node_id in result.selection.selected_node_ids
                if node_id not in result.rendered.ordered_node_ids
            ),
        )
    return BenchmarkRun(
        task_id=task.task_id,
        strategy_id=result.selection.strategy_id,
        strategy_version=result.selection.strategy_version,
        input_fingerprint=equal_footing_fingerprint(compilation.request, result),
        evaluator_label_identity=labels.label_identity,
        source_revision=task.source_revision,
        graph_identity=result.graph.semantic_identity,
        task_identity=semantic_hash({"task": task.description}),
        analysis_identity=analysis_identity(result),
        target_id=result.rendered.target_id.value,
        tokenizer_identity=result.rendered.tokenizer_identity.configuration_identity,
        configured_budget=result.rendered.budget_evidence.configured_budget,
        fixed_overhead_tokens=result.rendered.budget_evidence.fixed_overhead_tokens,
        source_allowance_tokens=result.selection.available_tokens,
        optimizer_status=result.selection.optimizer_status.value,
        selected_locations=selected,
        rendered_token_count=result.rendered.exact_token_count,
        metrics=metrics,
        top_k_trace=trace,
        metadata={
            "requested_strategy": result.selection.requested_strategy_id,
            "fallback_reason": result.selection.fallback_reason,
        },
    )
