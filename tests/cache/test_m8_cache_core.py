from __future__ import annotations

import json
from pathlib import Path

from contextc.cache.dependency_index import DependencyIndex
from contextc.cache.service import CacheService
from contextc.cache.source_index import SourceIndex
from contextc.cache.stagekeys import stage_key
from contextc.cache.store import ContentAddressedStore


def test_computation_key_mutation_sensitivity(monkeypatch) -> None:
    first = stage_key("analysis", {"task": "a", "node": "x"})
    second = stage_key("analysis", {"task": "b", "node": "x"})
    assert first.identity != second.identity

    import contextc.cache.stagekeys as stagekeys

    original = stagekeys.pass_version
    monkeypatch.setattr(
        stagekeys,
        "pass_version",
        lambda stage: "9.9.9" if stage == "analysis" else original(stage),
    )
    third = stagekeys.stage_key("analysis", {"task": "a", "node": "x"})
    assert third.identity != first.identity


def test_content_addressed_dedup_and_atomic_store(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path / "cache")
    first = stage_key("source_content", {"source": "a"})
    second = stage_key("source_content", {"source": "b"})
    payload = b"same canonical payload"
    assert not store.put(first, payload).deduplicated
    assert store.put(second, payload).deduplicated
    assert store.get(first).payload == payload  # type: ignore[union-attr]
    assert store.get(second).object_identity == store.get(first).object_identity  # type: ignore[union-attr]
    assert not tuple((tmp_path / "cache").rglob("*.tmp"))


def test_corrupt_object_is_quarantined_and_rejected(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path / "cache")
    key = stage_key("source_content", {"source": "a"})
    result = store.put(key, b"good")
    object_path = store._object_path(result.entry.object_identity)
    object_path.write_bytes(b"tampered")
    assert store.get(key) is None
    quarantine = tmp_path / "cache" / "quarantine"
    assert any(path.name == "reason.txt" for path in quarantine.rglob("reason.txt"))


def test_malformed_metadata_is_quarantined(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path / "cache")
    key = stage_key("source_content", {"source": "a"})
    store.put(key, b"good")
    store._metadata_path(key).write_text("{broken", encoding="utf-8")
    assert store.get(key) is None
    assert tuple((tmp_path / "cache" / "quarantine").rglob("metadata.json"))


def test_dependency_and_source_index_plan_transitive_invalidation(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    store = ContentAddressedStore(root)
    deps = DependencyIndex(root / "dependency-index.json")
    sources = SourceIndex(root / "source-index" / "sources.json")

    source = stage_key("source_content", {"a": 1})
    parse = stage_key("parse", {"a": 1})
    selection = stage_key("selection", {"a": 1})
    for key in (source, parse, selection):
        store.put(key, key.identity.encode())
    deps.record(source.identity, ())
    deps.record(parse.identity, (source.identity,))
    deps.record(selection.identity, (parse.identity,))
    sources.record("repo:///a.txt", source.identity)

    service = CacheService(root)
    plan = service.plan_invalidation("repo:///a.txt")
    assert plan.root_key_identities == (source.identity,)
    assert plan.affected_key_identities == tuple(
        sorted((source.identity, parse.identity, selection.identity))
    )

    dry = service.invalidate_source("repo:///a.txt", apply=False)
    assert dry == plan
    assert store._metadata_path(source).exists()

    applied = service.invalidate_source("repo:///a.txt", apply=True)
    assert applied == plan
    assert not store._metadata_path(source).exists()
    assert not store._metadata_path(parse).exists()
    assert not store._metadata_path(selection).exists()


def test_incompatible_cache_schema_is_rejected(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path / "cache")
    key = stage_key("source_content", {"source": "a"})
    store.put(key, b"good")
    metadata_path = store._metadata_path(key)
    raw = json.loads(metadata_path.read_text())
    raw["cache_schema_version"] = 999
    metadata_path.write_text(json.dumps(raw), encoding="utf-8")
    assert store.get(key) is None


def test_key_validation_and_canonical_bytes() -> None:
    import pytest

    from contextc.cache.keys import ComputationKey

    with pytest.raises(ValueError):
        ComputationKey("", "stage", "sha256:x")
    key = ComputationKey("contextc", "stage", "semantic")
    assert b'"namespace":"contextc"' in key.canonical_bytes()


def test_missing_object_is_rejected_and_quarantines_metadata(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path / "cache")
    key = stage_key("source_content", {"source": "missing"})
    result = store.put(key, b"payload")
    store._object_path(result.entry.object_identity).unlink()
    assert store.get(key) is None
    assert tuple((tmp_path / "cache" / "quarantine").rglob("reason.txt"))


def test_cache_service_stats_inspect_and_verify(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    store = ContentAddressedStore(root)
    key = stage_key("source_content", {"source": "a"})
    store.put(key, b"payload")
    service = CacheService(root)
    stats = service.stats()
    assert stats["entries"] == 1
    assert stats["objects"] == 1
    assert service.inspect(key.identity)[0]["key_identity"] == key.identity
    assert service.inspect("sha256:" + "0" * 64) == ()
    assert service.verify() == ()


def test_dependency_index_remove_cleans_reverse_edges(tmp_path: Path) -> None:
    deps = DependencyIndex(tmp_path / "deps.json")
    deps.record("a", ())
    deps.record("b", ("a",))
    assert deps.dependencies_of("b") == ("a",)
    assert deps.dependents_of("a") == ("b",)
    deps.remove("a")
    assert deps.dependencies_of("b") == ()
    assert deps.dependents_of("a") == ()


def test_store_verify_reports_bad_metadata_without_crashing(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path / "cache")
    bad = store.metadata / "bad.json"
    bad.write_text('{"not":"a computation key"}')
    problems = store.verify()
    assert any(problem.startswith("CTX700") for problem in problems)
