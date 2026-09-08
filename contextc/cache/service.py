"""Application-facing M8 cache inspection and invalidation service."""

from __future__ import annotations

from pathlib import Path

from contextc.cache.dependency_index import DependencyIndex
from contextc.cache.invalidation import InvalidationPlan, InvalidationPlanner
from contextc.cache.source_index import SourceIndex
from contextc.cache.store import ContentAddressedStore


class CacheService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.store = ContentAddressedStore(root)
        self.dependencies = DependencyIndex(root / "dependency-index.json")
        self.sources = SourceIndex(root / "source-index" / "sources.json")
        self.planner = InvalidationPlanner(self.sources, self.dependencies)

    def stats(self) -> dict[str, int]:
        metadata = self.store.iter_metadata()
        return {
            "entries": len(metadata),
            "objects": sum(1 for path in self.store.objects.rglob("*") if path.is_file()),
            "quarantined": sum(1 for path in self.store.quarantine.iterdir())
            if self.store.quarantine.exists()
            else 0,
        }

    def inspect(self, key_identity: str | None = None) -> tuple[dict[str, object], ...]:
        values = self.store.iter_metadata()
        if key_identity is None:
            return tuple(values)
        return tuple(v for v in values if v.get("key_identity") == key_identity)

    def verify(self) -> tuple[str, ...]:
        return self.store.verify()

    def plan_invalidation(self, source_uri: str) -> InvalidationPlan:
        return self.planner.for_source(source_uri)

    def invalidate_source(self, source_uri: str, *, apply: bool = False) -> InvalidationPlan:
        plan = self.plan_invalidation(source_uri)
        if not apply:
            return plan
        for key_identity in plan.affected_key_identities:
            self.store.delete_key_identity(key_identity)
            self.dependencies.remove(key_identity)
            self.sources.remove_key(key_identity)
        return plan
