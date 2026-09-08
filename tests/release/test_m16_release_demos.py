from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from contextc.cli.main import main
from contextc.release_demos.models import DemoKind
from contextc.release_demos.service import DemoService
from tools.build_release_registry import render_registry


def test_release_registry_has_exact_four_bounded_demos() -> None:
    service = DemoService()
    demos = service.list_demos()
    assert {item.demo_id for item in demos} == {
        "repository-bug",
        "incident-response",
        "incremental-rebuild",
        "capability-composition",
    }
    assert {item.kind for item in demos} == set(DemoKind)
    assert all(item.offline and not item.tool_execution for item in demos)
    assert service.verify_registry().valid


def test_all_release_demos_verify_semantically() -> None:
    result = DemoService().verify_all()
    assert result.valid
    assert result.demos_checked == 4
    assert all(item.valid for item in result.demo_results)


def test_repository_demo_exposes_equal_footing_m6_metrics_and_reproduction() -> None:
    result = DemoService().run_demo("repository-bug")
    rows = result.comparison["rows"]
    assert isinstance(rows, tuple) and len(rows) == 3
    fingerprints = {str(row["input_fingerprint"]) for row in rows if isinstance(row, Mapping)}
    assert len(fingerprints) == 1
    assert result.reproduction["verification_status"] == "verified"
    assert result.reproduction["byte_identical"] is True
    assert "repo:///src/humanize/lists.py" in result.summary["selected_source_uris"]


def test_incident_demo_preserves_security_and_supersession() -> None:
    result = DemoService().run_demo("incident-response")
    codes = result.compile["diagnostic_codes"]
    assert isinstance(codes, tuple)
    assert {"CTX210", "CTX400", "CTX425"}.issubset(codes)
    superseded = result.summary["superseded_source_uris"]
    assert isinstance(superseded, tuple)
    assert any(str(value).endswith("rollback_v1.md") for value in superseded)
    assert result.reproduction["byte_identical"] is True


def test_incremental_demo_proves_clean_equivalence_and_selective_cache_behavior() -> None:
    result = DemoService().run_demo("incremental-rebuild")
    evidence = result.incremental_capabilities
    assert evidence["equivalent_to_clean"] is True
    changed = evidence["changed_cache_report"]
    assert isinstance(changed, dict)
    assert changed["reused"]
    assert changed["recomputed"]
    assert evidence["tool_execution_performed"] is False


def test_capability_demo_is_static_and_requires_approval() -> None:
    result = DemoService().run_demo("capability-composition")
    evidence = result.incremental_capabilities
    assert evidence["tool_execution_performed"] is False
    assert "sensitive_to_external" in evidence["risk_kinds"]
    decisions = evidence["decisions"]
    assert isinstance(decisions, tuple)
    assert any(item["action"] == "require_explicit_approval" for item in decisions)
    assert evidence["approval_requirements"]


def test_release_demos_work_from_unrelated_cwd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    service = DemoService()
    assert service.verify_registry().valid
    result = service.run_demo("capability-composition")
    assert result.compile["tool_execution_performed"] is False


def test_release_cli_registry_verify_and_run(capsys) -> None:
    assert main(("demo", "registry", "list")) == 0
    listed = json.loads(capsys.readouterr().out)
    assert len(listed["demos"]) == 4
    assert main(("demo", "registry", "verify")) == 0
    verified = json.loads(capsys.readouterr().out)
    assert verified["valid"] is True
    assert main(("demo", "run", "capability-composition")) == 0
    run = json.loads(capsys.readouterr().out)
    assert run["compile"]["tool_execution_performed"] is False


def test_core_import_does_not_import_streamlit() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import contextc; "
            "assert 'streamlit' not in sys.modules; print(contextc.__version__)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip()


def test_all_release_demos_run_with_network_denied(monkeypatch) -> None:
    import socket

    def denied(*args, **kwargs):
        raise AssertionError("release demo attempted network access")

    monkeypatch.setattr(socket.socket, "connect", denied)
    service = DemoService()
    for demo in service.list_demos():
        result = service.run_demo(demo.demo_id)
        assert result.demo_id == demo.demo_id


def test_registry_generation_ignores_generated_bytecode(tmp_path: Path) -> None:
    demos = tmp_path / "demos"
    demo = demos / "example"
    cache = demo / "files" / "__pycache__"
    cache.mkdir(parents=True)
    (demo / "demo.json").write_text(
        json.dumps(
            {
                "demo_id": "example",
                "title": "Example",
                "kind": "repository_bug",
                "profile_version": "1.0.0",
                "description": "fixture",
                "offline": True,
                "tool_execution": False,
                "default_target": "generic",
                "default_strategy": "auto",
                "default_budget": 64,
                "expected": {},
            }
        ),
        encoding="utf-8",
    )
    (demo / "files" / "source.py").write_text("value = 1\n", encoding="utf-8")
    (cache / "source.cpython-311.pyc").write_bytes(b"generated")

    rendered = json.loads(render_registry(demos))
    paths = {item["path"] for item in rendered["demos"][0]["files"]}
    assert paths == {"demo.json", "files/source.py"}
