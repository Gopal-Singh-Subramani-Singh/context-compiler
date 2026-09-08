from __future__ import annotations

import json
from pathlib import Path

from contextc.cache.dependency_index import DependencyIndex
from contextc.cache.source_index import SourceIndex
from contextc.cache.stagekeys import stage_key
from contextc.cache.store import ContentAddressedStore
from contextc.cli.main import main


def test_cache_cli_dry_run_and_apply_are_distinct(tmp_path: Path, capsys) -> None:
    root = tmp_path / "cache"
    store = ContentAddressedStore(root)
    deps = DependencyIndex(root / "dependency-index.json")
    sources = SourceIndex(root / "source-index" / "sources.json")
    source = stage_key("source_content", {"a": 1})
    parse = stage_key("parse", {"a": 1})
    store.put(source, b"source")
    store.put(parse, b"parse")
    deps.record(source.identity, ())
    deps.record(parse.identity, (source.identity,))
    sources.record("repo:///a.txt", source.identity)

    assert (
        main(
            (
                "cache",
                "--root",
                str(root),
                "invalidate",
                "--source",
                "repo:///a.txt",
                "--dry-run",
                "--json",
            )
        )
        == 0
    )
    dry = json.loads(capsys.readouterr().out)
    assert dry["applied"] is False
    assert store._metadata_path(source).exists()

    assert (
        main(
            (
                "cache",
                "--root",
                str(root),
                "invalidate",
                "--source",
                "repo:///a.txt",
                "--apply",
                "--json",
            )
        )
        == 0
    )
    applied = json.loads(capsys.readouterr().out)
    assert applied["applied"] is True
    assert not store._metadata_path(source).exists()
    assert not store._metadata_path(parse).exists()


def test_incremental_compile_cli_reports_equivalence(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.txt").write_text("alpha beta\n")
    out = tmp_path / "out.txt"
    rc = main(
        (
            "compile",
            str(repo),
            "--task",
            "alpha beta",
            "--target",
            "generic",
            "--token-budget",
            "500",
            "--time-anchor",
            "2026-09-04T00:00:00Z",
            "--output",
            str(out),
            "--incremental",
            "--verify-incremental",
            "--cache-root",
            str(tmp_path / "cache"),
            "--json",
        )
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["incremental_equivalence"]["equivalent"] is True
    assert payload["cache"]["recomputed"]
