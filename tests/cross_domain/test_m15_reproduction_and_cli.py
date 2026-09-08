from __future__ import annotations

import json
from pathlib import Path

from contextc.cli.main import main
from contextc.cross_domain.service import compile_demo, explain_demo, reproduce_demo
from contextc.reproduction import read_build_manifest, rebuild_build, verify_build


def test_manifest_records_source_adapter_and_cross_domain_diagnostics(tmp_path: Path) -> None:
    output = tmp_path / "incident.json"
    compiled = compile_demo(
        "checkout-latency-001",
        strategy="relevance_greedy",
        budget=1800,
        output_path=output,
    )
    assert compiled.manifest_path is not None
    manifest = read_build_manifest(Path(compiled.manifest_path))
    assert manifest.schema_version.minor == 4
    assert manifest.build_inputs["source_adapter_id"] == "incident"
    codes = {item.code.value for item in manifest.diagnostics}
    assert {"CTX200", "CTX210", "CTX400", "CTX420", "CTX425"} <= codes
    old = next(
        node.node_id
        for node in compiled.compilation.source_graph.nodes
        if node.metadata.get("incident_alias") == "old_runbook"
    )
    assert old in manifest.excluded_node_ids


def test_incident_reproduction_is_byte_identical(tmp_path: Path) -> None:
    output = tmp_path / "incident.json"
    compiled = compile_demo(
        "checkout-latency-001",
        strategy="relevance_greedy",
        budget=1800,
        output_path=output,
    )
    manifest_path = Path(compiled.manifest_path or "")
    verified = verify_build(manifest_path)
    assert verified.status == "verified"
    rebuilt_path = tmp_path / "rebuilt.json"
    rebuilt = rebuild_build(manifest_path, output_path=rebuilt_path)
    assert rebuilt.artifact_identity == verified.artifact_identity
    assert rebuilt_path.read_bytes() == output.read_bytes()


def test_demo_reproduction_service_repeats_artifact() -> None:
    result = reproduce_demo("checkout-latency-001", strategy="relevance_greedy", budget=1800)
    assert result["verified"] is True
    assert result["rebuilt"] is True
    assert result["byte_identical"] is True
    assert result["artifact_identity"] == result["rebuilt_artifact_identity"]


def test_old_runbook_explanation_reads_stored_evidence_and_points_to_successor() -> None:
    explanation = explain_demo(
        "checkout-latency-001",
        "incident://checkout-latency-001/runbooks/rollback_v1.md",
        strategy="relevance_greedy",
        budget=1800,
    )
    assert explanation["evidence_source"] == "stored_build_manifest"
    node = explanation["nodes"][0]
    assert node["superseded"] is True
    assert node["selected"] is False
    assert node["excluded"] is True
    assert node["superseding_source_uri"].endswith("runbooks/rollback_v2.md")
    assert node["relationship_diagnostics"][0]["code"] == "CTX210"


def test_malicious_mcp_explanation_uses_stored_security_evidence() -> None:
    explanation = explain_demo(
        "checkout-latency-001",
        "mcp://ops-unverified/tools/incident_lookup/results/checkout-malicious-001",
        strategy="relevance_greedy",
        budget=1800,
    )
    malicious = next(
        item for item in explanation["nodes"] if item["node_id"] == "mcp-malicious-source"
    )
    assert malicious["security_decisions"][0]["action"] == "quote_as_data"
    assert (
        "security:untrusted-instruction-flow:quote_as_data" in malicious["security_transformations"]
    )


def test_demo_cli_list_validate_compile_compare_graph_explain_reproduce(
    tmp_path: Path, capsys
) -> None:
    assert main(["demo", "list"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["demos"][0]["demo_id"] == "checkout-latency-001"

    assert main(["demo", "validate", "checkout-latency-001"]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["valid"] is True
    assert validated["evaluator_sentinel_absent"] is True

    output = tmp_path / "cli.json"
    assert (
        main(
            [
                "demo",
                "compile",
                "checkout-latency-001",
                "--strategy",
                "relevance_greedy",
                "--budget",
                "1800",
                "--target",
                "structured-json",
                "--output",
                str(output),
                "--json",
            ]
        )
        == 0
    )
    compiled = json.loads(capsys.readouterr().out)
    assert compiled["target"] == "structured-json"
    assert output.is_file()

    assert (
        main(
            [
                "demo",
                "compare",
                "checkout-latency-001",
                "--strategy",
                "naive",
                "--strategy",
                "relevance_greedy",
                "--budget",
                "1800",
                "--json",
            ]
        )
        == 0
    )
    compared = json.loads(capsys.readouterr().out)
    assert len(compared["strategies"]) == 2
    assert compared["equal_footing_fingerprint"]

    assert (
        main(
            [
                "demo",
                "graph",
                "checkout-latency-001",
                "--selected-only",
                "--strategy",
                "relevance_greedy",
                "--json",
            ]
        )
        == 0
    )
    graphed = json.loads(capsys.readouterr().out)
    assert graphed["selected_only"] is True
    assert graphed["nodes"]

    assert (
        main(
            [
                "demo",
                "explain",
                "checkout-latency-001",
                "--source",
                "incident://checkout-latency-001/runbooks/rollback_v1.md",
                "--strategy",
                "relevance_greedy",
                "--json",
            ]
        )
        == 0
    )
    explained = json.loads(capsys.readouterr().out)
    assert explained["evidence_source"] == "stored_build_manifest"

    assert (
        main(
            [
                "demo",
                "reproduce",
                "checkout-latency-001",
                "--strategy",
                "relevance_greedy",
                "--json",
            ]
        )
        == 0
    )
    reproduced = json.loads(capsys.readouterr().out)
    assert reproduced["byte_identical"] is True
