from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from contextc.application.compile import CompileRepositoryRequest
from contextc.case_study import HistoricalRepository, list_task_directories, load_public_case_task
from contextc.cross_domain.service import demo_public_root
from contextc.incremental import IncrementalCompileRequest, IncrementalService
from contextc.optimization import OptimizerConfiguration
from contextc.targets import TargetId


def _build(tmp_path: Path, req: CompileRepositoryRequest, name: str, cache: Path):
    return IncrementalService().build(
        IncrementalCompileRequest(
            compile_request=req,
            output_path=tmp_path / f"{name}.out",
            cache_root=cache,
            verify_against_clean=True,
        )
    )


def test_m11_real_repository_one_source_incremental_matches_clean_and_revert_restores(
    tmp_path: Path,
) -> None:
    task_dir = next(
        path for path in list_task_directories() if path.name == "06_empty_natural_list"
    )
    public = load_public_case_task(task_dir)
    history = HistoricalRepository()
    with history.materialize(public.pre_fix_revision) as checkout:
        req = CompileRepositoryRequest(
            repository=checkout,
            task=public.description,
            target_id=TargetId.GENERIC,
            token_budget=public.token_budget,
            time_anchor=public.time_anchor,
            source_revision=public.pre_fix_revision,
            system_instruction=public.system_instruction,
            optimizer=OptimizerConfiguration(
                requested_strategy="relevance_greedy",
                source_content_allowance=public.source_content_allowance,
            ),
        )
        cache = tmp_path / "m11-cache"
        original = _build(tmp_path, req, "m11-original", cache)
        assert original.equivalence and original.equivalence.equivalent
        target = checkout / "src/humanize/lists.py"
        before = target.read_bytes()
        target.write_bytes(before + b"\n# m8 incremental real-source mutation\n")
        changed = _build(tmp_path, req, "m11-changed", cache)
        assert changed.equivalence and changed.equivalence.equivalent
        events = [e for e in changed.cache_report.events if e.stage == "source_content"]
        assert any(
            e.status == "recomputed" and e.source_uri == "repo:///src/humanize/lists.py"
            for e in events
        )
        assert any(
            e.status == "reused" and e.source_uri != "repo:///src/humanize/lists.py" for e in events
        )
        target.write_bytes(before)
        reverted = _build(tmp_path, req, "m11-reverted", cache)
        assert reverted.equivalence and reverted.equivalence.equivalent
        assert (
            reverted.compilation.rendered.rendered_bytes
            == original.compilation.rendered.rendered_bytes
        )


def _incident_request(root: Path) -> CompileRepositoryRequest:
    manifest = json.loads((root / "incident.json").read_text())
    return CompileRepositoryRequest(
        repository=root,
        task=manifest["task"],
        target_id=TargetId.STRUCTURED_JSON,
        token_budget=1800,
        time_anchor=datetime.fromisoformat(manifest["time_anchor"]),
        source_adapter_id="incident",
        optimizer=OptimizerConfiguration(requested_strategy="relevance_greedy"),
    )


def test_m15_incident_observation_incremental_matches_clean_and_revert_restores(
    tmp_path: Path,
) -> None:
    root = tmp_path / "incident"
    shutil.copytree(demo_public_root("checkout-latency-001"), root)
    req = _incident_request(root)
    cache = tmp_path / "m15-cache"
    original = _build(tmp_path, req, "m15-original", cache)
    assert original.equivalence and original.equivalence.equivalent
    observation = root / "sources/observations/checkout_latency.json"
    before = observation.read_bytes()
    raw = json.loads(before)
    raw["after"] = 2900
    observation.write_text(json.dumps(raw, separators=(",", ":")) + "\n")
    changed = _build(tmp_path, req, "m15-changed", cache)
    assert changed.equivalence and changed.equivalence.equivalent
    assert any(
        e.stage == "source_content"
        and e.source_uri.endswith("/observations/checkout_latency.json")
        and e.status == "recomputed"
        for e in changed.cache_report.events
    )
    observation.write_bytes(before)
    reverted = _build(tmp_path, req, "m15-reverted", cache)
    assert reverted.equivalence and reverted.equivalence.equivalent
    assert (
        reverted.compilation.rendered.rendered_bytes == original.compilation.rendered.rendered_bytes
    )


def test_selection_render_order_equivalent_between_incremental_and_clean(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    for name in ("z.txt", "a.txt", "m.txt"):
        (repo / name).write_text("same relevant token\n")
    req = CompileRepositoryRequest(
        repository=repo,
        task="relevant token",
        target_id=TargetId.GENERIC,
        token_budget=400,
        time_anchor=datetime(2026, 9, 4, tzinfo=UTC),
        optimizer=OptimizerConfiguration(requested_strategy="relevance_greedy"),
    )
    result = _build(tmp_path, req, "order", tmp_path / "cache")
    assert result.equivalence and result.equivalence.equivalent
    assert result.compilation.rendered.ordered_node_ids
