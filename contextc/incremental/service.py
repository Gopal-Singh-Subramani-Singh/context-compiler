"""Typed application service for M8 incremental compilation and cache control."""

from __future__ import annotations

from pathlib import Path

from contextc.application.compile import CompileRepositoryRequest, compile_source_target
from contextc.cache.equivalence import EquivalenceResult, compare_compilations
from contextc.cache.invalidation import InvalidationPlan
from contextc.cache.service import CacheService
from contextc.incremental.models import IncrementalCompileRequest, IncrementalCompileResult
from contextc.incremental.pipeline import IncrementalPipeline


class IncrementalService:
    def build(self, request: IncrementalCompileRequest) -> IncrementalCompileResult:
        cache_root = (
            request.cache_root or request.compile_request.repository / ".contextc" / "cache"
        )
        return IncrementalPipeline(cache_root).compile(request)

    def plan_invalidation(self, cache_root: Path, source_uri: str) -> InvalidationPlan:
        return CacheService(cache_root).plan_invalidation(source_uri)

    def invalidate_source(
        self, cache_root: Path, source_uri: str, *, apply: bool = False
    ) -> InvalidationPlan:
        return CacheService(cache_root).invalidate_source(source_uri, apply=apply)

    def inspect_cache(
        self, cache_root: Path, key_identity: str | None = None
    ) -> tuple[dict[str, object], ...]:
        return CacheService(cache_root).inspect(key_identity)

    def verify_equivalence(
        self,
        request: CompileRepositoryRequest,
        incremental: IncrementalCompileResult,
    ) -> EquivalenceResult:
        clean = compile_source_target(request)
        return compare_compilations(incremental.compilation, clean)
