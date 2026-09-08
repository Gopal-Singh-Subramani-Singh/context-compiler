"""Typed M8 incremental compilation request/result models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from contextc.application.compile import CompileRepositoryRequest, TargetCompilation
from contextc.cache.equivalence import EquivalenceResult
from contextc.cache.reports import CacheReport


@dataclass(frozen=True, slots=True)
class IncrementalCompileRequest:
    compile_request: CompileRepositoryRequest
    output_path: Path
    cache_root: Path | None = None
    manifest_path: Path | None = None
    verify_against_clean: bool = False


@dataclass(frozen=True, slots=True)
class IncrementalCompileResult:
    compilation: TargetCompilation
    cache_report: CacheReport
    equivalence: EquivalenceResult | None
    output_path: Path
    manifest_path: Path
