from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from contextc.application.compile import CompileRepositoryRequest
from contextc.incremental import IncrementalCompileRequest, IncrementalService
from contextc.optimization import OptimizerConfiguration
from contextc.security import load_policy
from contextc.targets import TargetId


def request(
    repo: Path,
    *,
    task: str = "alpha beta",
    budget: int = 500,
    target: TargetId = TargetId.GENERIC,
    optimizer: str = "relevance_greedy",
    policy=None,
    adapter: str = "repository",
) -> CompileRepositoryRequest:
    return CompileRepositoryRequest(
        repository=repo,
        task=task,
        target_id=target,
        token_budget=budget,
        time_anchor=datetime(2026, 9, 4, tzinfo=UTC),
        source_adapter_id=adapter,
        security_policy=policy,
        optimizer=OptimizerConfiguration(requested_strategy=optimizer),
    )


def build(
    tmp_path: Path,
    req: CompileRepositoryRequest,
    name: str,
    *,
    cache_root: Path | None = None,
):
    cache = cache_root or tmp_path / "cache"
    return IncrementalService().build(
        IncrementalCompileRequest(
            compile_request=req,
            output_path=tmp_path / f"{name}.txt",
            cache_root=cache,
            verify_against_clean=True,
        )
    )


def stages(result, status: str) -> list[str]:
    events = result.cache_report.reused if status == "reused" else result.cache_report.recomputed
    return [event.stage for event in events]


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.txt").write_text("alpha beta\n")
    (repo / "b.txt").write_text("beta gamma\n")
    return repo


def test_noop_incremental_reuses_real_intermediate_stages(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    first = build(tmp_path, request(repo), "first")
    second = build(tmp_path, request(repo), "second")
    assert first.equivalence and first.equivalence.equivalent
    assert second.equivalence and second.equivalence.equivalent
    reused = stages(second, "reused")
    assert "parse" in reused
    assert "security" in reused
    assert "supersession" in reused
    assert reused.count("token_count") == 2
    assert reused.count("analysis") == 2
    assert first.compilation.rendered.rendered_bytes == second.compilation.rendered.rendered_bytes


def test_one_file_change_selectively_reuses_unrelated_source_and_analysis(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    cache = tmp_path / "cache"
    build(tmp_path, request(repo), "first", cache_root=cache)
    (repo / "a.txt").write_text("alpha beta changed\n")
    changed = build(tmp_path, request(repo), "changed", cache_root=cache)
    assert changed.equivalence and changed.equivalence.equivalent
    parse_events = [e for e in changed.cache_report.events if e.stage == "parse"]
    assert parse_events[-1].status == "recomputed"
    source_events = [e for e in changed.cache_report.events if e.stage == "source_content"]
    by_uri = {e.source_uri: e.status for e in source_events}
    assert by_uri["repo:///a.txt"] == "recomputed"
    assert by_uri["repo:///b.txt"] == "reused"
    analysis_events = [e for e in changed.cache_report.events if e.stage == "analysis"]
    assert any(e.source_uri == "repo:///b.txt" and e.status == "reused" for e in analysis_events)


def test_task_change_reuses_parse_security_and_token_counts_but_not_analysis(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    cache = tmp_path / "cache"
    build(tmp_path, request(repo, task="alpha beta"), "first", cache_root=cache)
    changed = build(tmp_path, request(repo, task="gamma"), "task", cache_root=cache)
    reused = stages(changed, "reused")
    recomputed = stages(changed, "recomputed")
    assert "parse" in reused and "security" in reused
    assert reused.count("token_count") == 2
    assert recomputed.count("analysis") == 2


def test_budget_and_optimizer_changes_preserve_task_neutral_and_analysis_cache(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    cache = tmp_path / "cache"
    build(
        tmp_path, request(repo, budget=500, optimizer="relevance_greedy"), "first", cache_root=cache
    )
    changed = build(
        tmp_path, request(repo, budget=450, optimizer="density_greedy"), "changed", cache_root=cache
    )
    reused = stages(changed, "reused")
    assert "parse" in reused and "security" in reused
    assert reused.count("token_count") == 2
    assert reused.count("analysis") == 2
    assert "selection" in stages(changed, "recomputed")


def test_target_change_invalidates_target_token_and_analysis_stages(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    cache = tmp_path / "cache"
    build(tmp_path, request(repo, target=TargetId.GENERIC), "first", cache_root=cache)
    changed = build(
        tmp_path, request(repo, target=TargetId.STRUCTURED_JSON), "target", cache_root=cache
    )
    assert "parse" in stages(changed, "reused")
    assert stages(changed, "recomputed").count("token_count") == 2
    assert stages(changed, "recomputed").count("analysis") == 2


def test_policy_formatting_only_reuses_security_semantic_change_does_not(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    cache = tmp_path / "cache"
    p1 = tmp_path / "p1.json"
    p2 = tmp_path / "p2.json"
    p3 = tmp_path / "p3.json"
    policy = {
        "policy_id": "test",
        "version": "1",
        "rules": [],
    }
    p1.write_text(json.dumps(policy, separators=(",", ":")))
    p2.write_text(json.dumps(policy, indent=4) + "\n")
    semantic = dict(policy)
    semantic["rules"] = [
        {
            "rule_id": "allow-local",
            "action": "allow",
            "source_domains": ["local_repository"],
        }
    ]
    p3.write_text(json.dumps(semantic, indent=2))
    build(tmp_path, request(repo, policy=load_policy(p1)), "first", cache_root=cache)
    formatted = build(
        tmp_path, request(repo, policy=load_policy(p2)), "formatted", cache_root=cache
    )
    assert "security" in stages(formatted, "reused")
    changed = build(tmp_path, request(repo, policy=load_policy(p3)), "semantic", cache_root=cache)
    security_events = [e for e in changed.cache_report.events if e.stage == "security"]
    assert security_events[-1].status == "recomputed"
    assert "parse" in stages(changed, "reused")


def test_cache_deleted_does_not_affect_reproduction(tmp_path: Path) -> None:
    from contextc.reproduction import verify_build

    repo = make_repo(tmp_path)
    cache = tmp_path / "cache"
    result = build(tmp_path, request(repo), "artifact", cache_root=cache)
    shutil.rmtree(cache)
    verified = verify_build(result.manifest_path, source_root=repo)
    assert verified.source_checked


def test_secret_never_persisted_anywhere_in_cache(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    secret = "M8-SECRET-CANARY-8391"
    (repo / "private.txt").write_text(secret)
    from contextc.ir import Sensitivity
    from contextc.source_rules import SourceFactRule

    req = request(repo)
    req = CompileRepositoryRequest(
        **{
            field: getattr(req, field)
            for field in req.__dataclass_fields__
            if field not in {"source_rules"}
        },
        source_rules=(SourceFactRule(glob="private.txt", sensitivity=Sensitivity.SECRET),),
    )
    cache = tmp_path / "cache"
    result = build(tmp_path, req, "secret", cache_root=cache)
    assert result.equivalence and result.equivalence.equivalent
    for path in cache.rglob("*"):
        if path.is_file():
            assert secret.encode() not in path.read_bytes()


def test_evaluator_label_is_not_a_compiler_cache_input(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    cache = tmp_path / "cache"
    first = build(tmp_path, request(repo), "first", cache_root=cache)
    evaluator = tmp_path / "evaluator-label.json"
    evaluator.write_text('{"ground_truth":"one"}')
    second = build(tmp_path, request(repo), "second", cache_root=cache)
    evaluator.write_text('{"ground_truth":"two"}')
    third = build(tmp_path, request(repo), "third", cache_root=cache)
    assert [e.key_identity for e in second.cache_report.reused if e.stage == "parse"] == [
        e.key_identity for e in third.cache_report.reused if e.stage == "parse"
    ]
    assert first.compilation.rendered.rendered_bytes == third.compilation.rendered.rendered_bytes


def test_corrupted_intermediate_recomputes_and_remains_equivalent(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    cache = tmp_path / "cache"
    first = build(tmp_path, request(repo), "first", cache_root=cache)
    from contextc.cache.store import ContentAddressedStore

    store = ContentAddressedStore(cache)
    parse_event = next(e for e in first.cache_report.events if e.stage == "parse")
    record = next(
        v for v in store.iter_metadata() if v.get("key_identity") == parse_event.key_identity
    )
    object_identity = record["object_identity"]
    store._object_path(object_identity).write_bytes(b"corrupt")
    recovered = build(tmp_path, request(repo), "recovered", cache_root=cache)
    assert recovered.equivalence and recovered.equivalence.equivalent
    parse_events = [e for e in recovered.cache_report.events if e.stage == "parse"]
    assert parse_events[-1].status == "recomputed"
    assert tuple((cache / "quarantine").rglob("reason.txt"))


def test_policy_comment_only_change_reuses_security(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    cache = tmp_path / "cache"
    p1 = tmp_path / "p1.yaml"
    p2 = tmp_path / "p2.yaml"
    body = '{"policy_id":"comments","version":"1","rules":[]}\n'
    p1.write_text(body)
    p2.write_text("# comment only change\n// another comment\n" + body)
    build(tmp_path, request(repo, policy=load_policy(p1)), "first-comments", cache_root=cache)
    second = build(
        tmp_path, request(repo, policy=load_policy(p2)), "second-comments", cache_root=cache
    )
    assert "security" in stages(second, "reused")


def test_incremental_service_cache_methods(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    cache = tmp_path / "cache"
    result = build(tmp_path, request(repo), "service", cache_root=cache)
    service = IncrementalService()
    inspected = service.inspect_cache(cache)
    assert inspected
    plan = service.plan_invalidation(cache, "repo:///a.txt")
    assert plan.affected_key_identities
    dry = service.invalidate_source(cache, "repo:///a.txt", apply=False)
    assert dry == plan
    eq = service.verify_equivalence(request(repo), result)
    assert eq.equivalent
