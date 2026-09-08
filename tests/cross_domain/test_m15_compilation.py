from __future__ import annotations

import json
from datetime import UTC, datetime

from contextc.application.compile import CompileRepositoryRequest, compile_source_target
from contextc.cross_domain.evaluator import evaluate_incident
from contextc.cross_domain.service import compare_strategies, compile_demo, demo_public_root
from contextc.diagnostics import DiagnosticCode
from contextc.optimization import OptimizerConfiguration
from contextc.targets import TargetId


def request(*, budget: int = 1800, strategy: str = "relevance_greedy") -> CompileRepositoryRequest:
    return CompileRepositoryRequest(
        repository=demo_public_root("checkout-latency-001"),
        task="checkout latency deployment cache rollback ownership current procedure",
        target_id=TargetId.STRUCTURED_JSON,
        token_budget=budget,
        time_anchor=datetime(2026, 9, 4, tzinfo=UTC),
        source_adapter_id="incident",
        optimizer=OptimizerConfiguration(requested_strategy=strategy),
    )


def alias_map(result: object) -> dict[str, str]:
    from contextc.application.compile import TargetCompilation

    assert isinstance(result, TargetCompilation)
    return {
        str(node.metadata["incident_alias"]): node.node_id
        for node in result.source_graph.nodes
        if "incident_alias" in node.metadata
    }


def test_same_compiler_path_compiles_incident_to_structured_json() -> None:
    result = compile_source_target(request())
    payload = json.loads(result.rendered.rendered_text)
    assert payload["target"] == "structured-json"
    assert payload["schema_version"] == 1
    assert result.rendered.exact_token_count <= result.rendered.budget_evidence.configured_budget
    assert [item["node_id"] for item in payload["records"]] == list(
        result.rendered.ordered_node_ids
    )


def test_superseded_old_runbook_is_optimizer_ineligible_and_uses_no_final_budget() -> None:
    result = compile_source_target(request(budget=5000, strategy="naive"))
    aliases = alias_map(result)
    assert aliases["old_runbook"] in result.supersession.superseded_node_ids
    assert aliases["old_runbook"] not in result.selection.selected_node_ids
    assert aliases["old_runbook"] not in result.rendered.ordered_node_ids
    assert aliases["old_runbook"] in result.selection.excluded_node_ids


def test_m9_engine_is_reused_for_malicious_mcp_and_no_ctx440() -> None:
    result = compile_source_target(request())
    codes = {item.code for item in result.security.diagnostics}
    assert DiagnosticCode.UNTRUSTED_INSTRUCTION_SCOPE in codes
    assert DiagnosticCode.TRUST_AUTHORITY_OVERRIDE in codes
    assert DiagnosticCode.DANGEROUS_CAPABILITY_COMPOSITION not in codes
    decision = next(
        item for item in result.security.decisions if item.node_id == "mcp-malicious-source"
    )
    assert decision.action.value == "quote_as_data"
    transformed = result.graph.get_node("mcp-malicious-source")
    assert transformed.instruction_authority.value == "none"
    assert transformed.content.startswith("[BEGIN QUOTED SOURCE DATA]")


def test_conflict_evidence_does_not_block_compilation() -> None:
    result = compile_source_target(request())
    assert result.conflicts.diagnostics
    assert result.selection.optimizer_status.value in {
        "heuristic",
        "optimal",
        "fallback",
        "feasible",
    }


def test_structured_json_enforces_exact_final_budget() -> None:
    result = compile_source_target(request(budget=900, strategy="naive"))
    from contextc.tokenizers import StructuredJsonTokenizer

    assert result.rendered.exact_token_count <= 900
    assert result.rendered.exact_token_count == StructuredJsonTokenizer().count(
        result.rendered.rendered_text
    )


def test_cross_domain_evaluator_reuses_m6_raw_metrics_and_adds_domain_metrics() -> None:
    result = compile_source_target(request())
    evaluation = evaluate_incident(
        public_root=demo_public_root("checkout-latency-001"),
        result=result,
        compilation_latency_ms=1.0,
    )
    assert 0.0 <= evaluation.raw_metrics.required_file_recall <= 1.0
    assert evaluation.domain_metrics.required_relation_coverage == 1.0
    assert evaluation.domain_metrics.superseded_content_exclusion_ratio == 1.0
    assert evaluation.domain_metrics.security_policy_correctness == 1.0


def test_equal_footing_comparison_uses_one_fingerprint() -> None:
    comparisons = compare_strategies(
        "checkout-latency-001",
        strategies=(
            "naive",
            "recency",
            "top_k",
            "relevance_greedy",
            "density_greedy",
            "graph_closure_greedy",
            "dynamic_programming",
            "auto",
        ),
        budget=1800,
    )
    assert len(comparisons) == 8
    assert len({item.input_fingerprint for item in comparisons}) == 1
    top_k = next(item for item in comparisons if item.strategy_id == "top_k")
    assert top_k.optimizer_status == "fallback"


def test_m15_compile_does_not_import_evaluator_labels_into_compiler(monkeypatch) -> None:
    import sys

    sys.modules.pop("contextc.cross_domain.evaluator", None)
    compiled = compile_demo("checkout-latency-001", strategy="relevance_greedy", budget=1800)
    assert compiled.compilation.rendered.ordered_node_ids
    assert "contextc.cross_domain.evaluator" not in sys.modules
    serialized = json.dumps(
        [node.to_dict() for node in compiled.compilation.source_graph.nodes],
        sort_keys=True,
    )
    assert "EVALUATOR_ONLY_M15_SENTINEL" not in serialized


def test_comparison_identity_excludes_volatile_runtime_metrics() -> None:
    from contextc.cross_domain.service import comparison_payload

    first = compare_strategies(
        "checkout-latency-001",
        strategies=("naive", "relevance_greedy"),
        budget=1800,
    )
    second = compare_strategies(
        "checkout-latency-001",
        strategies=("naive", "relevance_greedy"),
        budget=1800,
    )
    assert (
        comparison_payload(first)["comparison_identity"]
        == comparison_payload(second)["comparison_identity"]
    )
