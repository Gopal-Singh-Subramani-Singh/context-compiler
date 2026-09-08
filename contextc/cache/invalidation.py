"""Dependency-aware invalidation planning."""

from __future__ import annotations

from dataclasses import dataclass

from contextc.cache.dependency_index import DependencyIndex
from contextc.cache.source_index import SourceIndex


@dataclass(frozen=True, slots=True)
class InvalidationPlan:
    source_uri: str
    root_key_identities: tuple[str, ...]
    affected_key_identities: tuple[str, ...]


class InvalidationPlanner:
    def __init__(self, source_index: SourceIndex, dependency_index: DependencyIndex) -> None:
        self.source_index = source_index
        self.dependency_index = dependency_index

    def for_source(self, source_uri: str) -> InvalidationPlan:
        roots = self.source_index.keys_for(source_uri)
        affected = self.dependency_index.transitive_dependents(roots)
        return InvalidationPlan(source_uri, roots, affected)
