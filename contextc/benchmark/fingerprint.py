"""Equal-footing semantic fingerprints for cross-strategy comparisons."""

from __future__ import annotations

from contextc.application.compile import CompileRepositoryRequest, TargetCompilation
from contextc.errors import SourceValidationError
from contextc.hashing import semantic_hash
from contextc.security import policy_identity as security_policy_identity

from .models import BenchmarkRun


def analysis_identity(result: TargetCompilation) -> str:
    return semantic_hash(result.analyses)


def equal_footing_fingerprint(
    request: CompileRepositoryRequest,
    result: TargetCompilation,
) -> str:
    """Hash semantic compiler inputs while intentionally excluding strategy identity."""

    optimizer = request.optimizer
    return semantic_hash(
        {
            "task_identity": semantic_hash({"task": request.task}),
            "public_task_input": request.task,
            "source_revision": request.source_revision,
            "graph_identity": result.graph.semantic_identity,
            "analysis_identity": analysis_identity(result),
            "target_id": result.rendered.target_id,
            "tokenizer_identity": result.rendered.tokenizer_identity,
            "configured_budget": result.rendered.budget_evidence.configured_budget,
            "fixed_overhead_tokens": result.rendered.budget_evidence.fixed_overhead_tokens,
            "source_allowance_tokens": result.selection.available_tokens,
            "objective_configuration": optimizer.objective_weights,
            "optimizer_limits": optimizer.limits,
            "dependency_policy": tuple(
                sorted(item.value for item in result.graph.dependency_edge_types)
            ),
            "mandatory_node_ids": optimizer.mandatory_node_ids,
            "blocked_node_ids": optimizer.blocked_node_ids,
            "policy_eligible_node_ids": optimizer.policy_eligible_node_ids,
            "policy_id": request.policy_id,
            "policy_version": request.policy_version,
            "security_policy_identity": security_policy_identity(request.security_policy)
            if request.security_policy is not None
            else result.security.policy_identity,
            "source_adapter_id": request.source_adapter_id,
            "supersession_policy_identity": request.supersession_policy.identity,
            "random_seed": request.random_seed,
        }
    )


def assert_equal_footing(runs: tuple[BenchmarkRun, ...]) -> None:
    if not runs:
        raise SourceValidationError("equal-footing comparison requires at least one run")
    fingerprints = {run.input_fingerprint for run in runs}
    labels = {run.evaluator_label_identity for run in runs}
    tasks = {run.task_id for run in runs}
    if len(fingerprints) != 1 or len(labels) != 1 or len(tasks) != 1:
        raise SourceValidationError(
            "benchmark runs are not equal-footing compatible: "
            f"tasks={sorted(tasks)}, fingerprints={sorted(fingerprints)}, labels={sorted(labels)}"
        )
