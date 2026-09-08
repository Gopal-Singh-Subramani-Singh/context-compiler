"""Source-neutral adapter boundary introduced by M15."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from contextc.ir import ContextGraph
from contextc.parsers import IndexResult, RepositoryParser
from contextc.source_rules import SourceFactRule


@dataclass(frozen=True, slots=True)
class AdaptedContext:
    adapter_id: str
    adapter_version: str
    index: IndexResult
    graph: ContextGraph


class SourceAdapter(Protocol):
    adapter_id: str
    adapter_version: str

    def parse(
        self,
        root: Path,
        *,
        revision: str | None = None,
        source_rules: tuple[SourceFactRule, ...] = (),
    ) -> AdaptedContext: ...


class RepositoryAdapter:
    adapter_id = "repository"
    adapter_version = "1.0.0"

    def parse(
        self,
        root: Path,
        *,
        revision: str | None = None,
        source_rules: tuple[SourceFactRule, ...] = (),
    ) -> AdaptedContext:
        from contextc.application.graphing import graph_repository_index

        index = RepositoryParser(revision=revision, source_rules=source_rules).parse(root)
        return AdaptedContext(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            index=index,
            graph=graph_repository_index(index),
        )


def load_source_context(
    adapter_id: str,
    root: Path,
    *,
    revision: str | None = None,
    source_rules: tuple[SourceFactRule, ...] = (),
) -> AdaptedContext:
    """Load one source domain without exposing domain logic to the compiler."""

    if adapter_id == "repository":
        return RepositoryAdapter().parse(root, revision=revision, source_rules=source_rules)
    if adapter_id == "incident":
        from contextc.cross_domain.incident import IncidentAdapter

        return IncidentAdapter().parse(root, revision=revision)
    raise ValueError(f"unknown source adapter {adapter_id!r}")
