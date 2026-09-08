from __future__ import annotations

import json
from pathlib import Path

from contextc.cli.main import main


def write_case(root: Path) -> tuple[Path, Path]:
    tools = root / "declarations"
    tools.mkdir()
    (tools / "all.json").write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "tool_id": "read_secret",
                        "server_id": "local",
                        "trust_domain": "verified_tool",
                        "capabilities": ["local_file_read"],
                        "resources_read": ["secret"],
                        "resources_written": [],
                        "possible_output_sensitivity": "secret",
                        "side_effecting": False,
                        "allows_execution": False,
                        "allows_network": False,
                    },
                    {
                        "tool_id": "send",
                        "server_id": "external",
                        "trust_domain": "verified_tool",
                        "capabilities": ["external_write"],
                        "resources_read": [],
                        "resources_written": [],
                        "possible_output_sensitivity": "internal",
                        "side_effecting": True,
                        "allows_execution": False,
                        "allows_network": True,
                    },
                ],
                "resources": [
                    {
                        "resource_id": "secret",
                        "kind": "local_file",
                        "sensitivity": "secret",
                        "trust_domain": "local_repository",
                        "allowed_sinks": ["local"],
                        "allowed_actions": ["read"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    plan = root / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "schema_version": {"major": 1, "minor": 0},
                "plan_id": "cli-danger",
                "calls": [
                    {"call_id": "read", "tool_id": "read_secret"},
                    {
                        "call_id": "send",
                        "tool_id": "send",
                        "input_bindings": {"body": "call:read.output"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return plan, tools


def test_cli_validate_analyze_and_explain_are_static(tmp_path: Path, capsys) -> None:
    plan, tools = write_case(tmp_path)
    assert main(["mcp", "plan", "validate", str(plan), "--tools", str(tools), "--json"]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["valid"] is True
    assert validated["tool_execution_performed"] is False

    analysis = tmp_path / "analysis.json"
    cache = tmp_path / "cache"
    code = main(
        [
            "mcp",
            "plan",
            "analyze",
            str(plan),
            "--tools",
            str(tools),
            "--cache-root",
            str(cache),
            "--output",
            str(analysis),
            "--json",
        ]
    )
    assert code == 3
    value = json.loads(capsys.readouterr().out)
    assert value["analysis_mode"] == "static"
    assert value["tool_execution_performed"] is False
    assert value["blocked"] is True
    assert analysis.exists()
    flow = value["flows"][0]["flow_identity"]

    assert main(["mcp", "plan", "explain", str(analysis), "--flow", flow, "--json"]) == 0
    explained = json.loads(capsys.readouterr().out)
    assert explained["analysis_mode"] == "static"
    assert explained["tool_execution_performed"] is False
    assert explained["ordered_path"][0]["kind"] == "source"
    assert explained["ordered_path"][-1]["kind"] == "sink"


def test_cli_warm_analysis_reuses_capability_cache(tmp_path: Path, capsys) -> None:
    plan, tools = write_case(tmp_path)
    cache = tmp_path / "cache"
    args = [
        "mcp",
        "plan",
        "analyze",
        str(plan),
        "--tools",
        str(tools),
        "--cache-root",
        str(cache),
        "--json",
    ]
    assert main(args) == 3
    first = json.loads(capsys.readouterr().out)
    assert first["cache_status"] == "recomputed"
    assert main(args) == 3
    second = json.loads(capsys.readouterr().out)
    assert second["cache_status"] == "reused"
    assert first["cache_key_identity"] == second["cache_key_identity"]
