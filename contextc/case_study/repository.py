"""Immutable offline Git-bundle validation and pre-fix materialization."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from contextc.errors import SourceValidationError


def packaged_case_study_root() -> Path:
    return Path(__file__).resolve().parent.parent / "resources" / "case_study" / "humanize"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _metadata(root: Path) -> Mapping[str, object]:
    try:
        value = json.loads((root / "SOURCE.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SourceValidationError(f"invalid case-study source metadata: {error}") from error
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise SourceValidationError("case-study source metadata must be an object")
    return value


def _git(*arguments: str, cwd: Path | None = None) -> str:
    if shutil.which("git") is None:
        raise SourceValidationError("M11 historical materialization requires the git executable")
    try:
        completed = subprocess.run(
            ("git", *arguments),
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip() or "git command failed"
        raise SourceValidationError(f"historical repository operation failed: {detail}") from error
    return completed.stdout.strip()


@dataclass(frozen=True, slots=True)
class HistoricalRepository:
    root: Path = field(default_factory=packaged_case_study_root)

    @property
    def bundle(self) -> Path:
        return self.root / "humanize.bundle"

    @property
    def source_metadata(self) -> Mapping[str, object]:
        return _metadata(self.root)

    @property
    def repository_id(self) -> str:
        value = self.source_metadata.get("repository_id")
        if not isinstance(value, str) or not value:
            raise SourceValidationError("case-study repository_id is missing")
        return value

    @property
    def bundle_identity(self) -> str:
        return _sha256(self.bundle)

    def validate_reference(self) -> None:
        expected = self.source_metadata.get("bundle_sha256")
        if expected != self.bundle_identity:
            raise SourceValidationError(
                f"historical bundle identity differs: current={self.bundle_identity}, "
                f"expected={expected!r}"
            )
        if (
            self.source_metadata.get("license") != "MIT"
            or not (self.root / "LICENSE.txt").is_file()
        ):
            raise SourceValidationError("python-humanize MIT license evidence is incomplete")
        # ``git bundle verify`` inspects prerequisites against the current
        # repository.  Give it an isolated empty repository so validation never
        # depends on the caller's working directory being a Git checkout.
        with tempfile.TemporaryDirectory(prefix="contextc-m11-verify-") as temporary:
            verification_repository = Path(temporary) / "repository.git"
            _git("init", "--quiet", "--bare", str(verification_repository))
            _git("bundle", "verify", str(self.bundle), cwd=verification_repository)

    @contextmanager
    def materialize(self, revision: str, *, reverse_creation_order: bool = False) -> Iterator[Path]:
        """Yield an isolated exact revision; the canonical bundle is never written."""

        self.validate_reference()
        identity_before = self.bundle_identity
        with tempfile.TemporaryDirectory(prefix="contextc-m11-") as temporary:
            checkout = Path(temporary) / "checkout"
            _git("clone", "--quiet", "--no-checkout", str(self.bundle), str(checkout))
            _git("checkout", "--quiet", "--detach", revision, cwd=checkout)
            resolved = _git("rev-parse", "HEAD", cwd=checkout)
            if resolved != revision:
                raise SourceValidationError(
                    f"materialized revision differs: current={resolved}, expected={revision}"
                )
            if reverse_creation_order:
                reordered = Path(temporary) / "reordered"
                reordered.mkdir()
                files = sorted(
                    (
                        path
                        for path in checkout.rglob("*")
                        if path.is_file() and ".git" not in path.relative_to(checkout).parts
                    ),
                    key=lambda path: path.relative_to(checkout).as_posix(),
                    reverse=True,
                )
                for source in files:
                    destination = reordered / source.relative_to(checkout)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
                yield reordered
            else:
                yield checkout
        if self.bundle_identity != identity_before:
            raise SourceValidationError(
                "historical reference bundle was mutated during materialization"
            )

    def commit_parent(self, fix_revision: str) -> str:
        with self.materialize(fix_revision) as checkout:
            parents = _git("rev-list", "--parents", "-n", "1", fix_revision, cwd=checkout).split()
        if len(parents) != 2:
            raise SourceValidationError("case-study fixes must have exactly one parent")
        return parents[1]

    def changed_files(self, pre_fix_revision: str, fix_revision: str) -> tuple[str, ...]:
        with self.materialize(pre_fix_revision) as checkout:
            output = _git(
                "diff",
                "--name-only",
                pre_fix_revision,
                fix_revision,
                cwd=checkout,
            )
        return tuple(sorted(line for line in output.splitlines() if line))

    def patch(self, pre_fix_revision: str, fix_revision: str) -> str:
        with self.materialize(pre_fix_revision) as checkout:
            return _git(
                "diff",
                "--no-ext-diff",
                "--unified=3",
                pre_fix_revision,
                fix_revision,
                cwd=checkout,
            )
