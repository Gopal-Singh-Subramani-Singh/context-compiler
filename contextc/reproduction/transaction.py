"""Two-file artifact transaction with manifest-as-commit-marker semantics."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from contextc.canonical import canonical_json_bytes, to_canonical_primitive
from contextc.errors import ArtifactTransactionError, SourceValidationError
from contextc.reproduction.manifest import BuildManifest

FAULT_POINTS = frozenset(
    {
        "artifact_staging",
        "manifest_serialization",
        "manifest_staging",
        "commit_boundary",
    }
)


def canonical_manifest_bytes(manifest: BuildManifest) -> bytes:
    """Return the compact canonical form used for semantic identity checks."""

    return canonical_json_bytes(manifest)


def pretty_manifest_bytes(manifest: BuildManifest) -> bytes:
    """Return stable human-readable JSON, distinct from canonical semantics."""

    return (
        json.dumps(
            to_canonical_primitive(manifest),
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def default_manifest_path(artifact_path: Path) -> Path:
    artifact = artifact_path.resolve()
    return artifact.with_name(f"{artifact.name}.manifest.json")


def _stage_bytes(path: Path, payload: bytes) -> Path:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        return temporary
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _restore(path: Path, previous: bytes | None) -> None:
    if previous is None:
        path.unlink(missing_ok=True)
        return
    staged = _stage_bytes(path, previous)
    try:
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_artifact_transaction(
    *,
    artifact_path: Path,
    manifest_path: Path,
    artifact_bytes: bytes,
    manifest: BuildManifest,
    fault_at: str | None = None,
) -> tuple[Path, Path]:
    """Commit artifact first and manifest last, rolling back controlled failures.

    The manifest is the commit marker: a pair is valid only when the manifest
    exists and its artifact identity verifies. Both files must share a directory
    so staging, replacement, recovery, and directory fsync have one boundary.
    """

    artifact = artifact_path.resolve()
    manifest_file = manifest_path.resolve()
    if artifact == manifest_file:
        raise SourceValidationError("artifact and manifest paths must differ")
    if artifact.parent != manifest_file.parent:
        raise SourceValidationError("artifact and manifest must share a directory")
    if fault_at is not None and fault_at not in FAULT_POINTS:
        raise SourceValidationError(f"unknown transaction fault point: {fault_at}")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    expected_relative = artifact.relative_to(manifest_file.parent).as_posix()
    if manifest.artifact_path != expected_relative:
        raise SourceValidationError(
            "manifest artifact path does not identify the transaction artifact"
        )

    staged_artifact: Path | None = None
    staged_manifest: Path | None = None
    artifact_replaced = False
    previous_artifact = artifact.read_bytes() if artifact.is_file() else None
    previous_manifest = manifest_file.read_bytes() if manifest_file.is_file() else None
    stage = "artifact_staging"
    try:
        staged_artifact = _stage_bytes(artifact, artifact_bytes)
        if fault_at == stage:
            raise RuntimeError("injected artifact staging failure")

        stage = "manifest_serialization"
        manifest_bytes = pretty_manifest_bytes(manifest)
        if fault_at == stage:
            raise RuntimeError("injected manifest serialization failure")

        stage = "manifest_staging"
        staged_manifest = _stage_bytes(manifest_file, manifest_bytes)
        if fault_at == stage:
            raise RuntimeError("injected manifest staging failure")

        stage = "commit_boundary"
        os.replace(staged_artifact, artifact)
        staged_artifact = None
        artifact_replaced = True
        if fault_at == stage:
            raise RuntimeError("injected failure between artifact and manifest commit")
        os.replace(staged_manifest, manifest_file)
        staged_manifest = None
        _fsync_directory(artifact.parent)
        return artifact, manifest_file
    except BaseException as error:
        if artifact_replaced:
            try:
                _restore(artifact, previous_artifact)
                _restore(manifest_file, previous_manifest)
                _fsync_directory(artifact.parent)
            except BaseException as recovery_error:
                raise ArtifactTransactionError(
                    "rollback",
                    RuntimeError(f"{error}; rollback failed: {recovery_error}"),
                ) from recovery_error
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        raise ArtifactTransactionError(stage, error) from error
    finally:
        if staged_artifact is not None:
            staged_artifact.unlink(missing_ok=True)
        if staged_manifest is not None:
            staged_manifest.unlink(missing_ok=True)
