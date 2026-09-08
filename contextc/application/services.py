"""M16 application-facing service boundaries used by CLI and Observatory."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from contextc.application.compile import (
    CompileRepositoryRequest,
    TargetCompilation,
    compile_source_target,
    compile_source_to_path,
)
from contextc.reproduction import (
    RebuildResult,
    VerificationResult,
    rebuild_build,
    verify_build,
)


class CompileService:
    """Compile typed source contexts without exposing lower-level compiler functions to UI code."""

    def compile(self, request: CompileRepositoryRequest) -> TargetCompilation:
        return compile_source_target(request)

    def compile_to_path(
        self, request: CompileRepositoryRequest, output_path: Path
    ) -> TargetCompilation:
        return compile_source_to_path(request, output_path)


class VerificationService:
    """Verify and rebuild stored M4 evidence."""

    def verify(
        self,
        manifest_path: Path,
        *,
        source_root: Path | None = None,
        source_revision: str | None = None,
    ) -> VerificationResult:
        return verify_build(
            manifest_path,
            source_root=source_root,
            source_revision=source_revision,
        )

    def rebuild(
        self,
        manifest_path: Path,
        *,
        output_path: Path,
        source_root: Path | None = None,
        source_revision: str | None = None,
    ) -> RebuildResult:
        return rebuild_build(
            manifest_path,
            output_path=output_path,
            source_root=source_root,
            source_revision=source_revision,
        )


class ComparisonService:
    """Read-only release comparison service backed by bounded M16 demo evidence."""

    def compare_release_demo(self, demo_id: str = "repository-bug") -> Mapping[str, object]:
        from contextc.release_demos.service import DemoService

        return DemoService().run_demo(demo_id).comparison
