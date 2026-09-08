"""Audit M16 distributions for forbidden release artifacts and sensitive markers."""

from __future__ import annotations

import argparse
import re
import tarfile
import zipfile
from collections.abc import Iterable
from pathlib import Path

FORBIDDEN_PATH_PARTS = (
    "/tests/",
    "/contextc/resources/benchmarks/",
    "/evaluator/",
    "/.venv/",
    "/.pytest_cache/",
    "/.mypy_cache/",
    "/.ruff_cache/",
    "/.contextc/",
    "/quarantine/",
    "/__pycache__/",
    "humanize.bundle",
)
FORBIDDEN_TEXT = (
    "EVAL_ONLY_",
    "EVALUATOR_ONLY_",
    "/Users/",
    "/home/",
    "BEGIN PRIVATE KEY",
)
AWS_KEY = re.compile(r"AKIA[0-9A-Z]{16}")


def _audit_member(name: str, payload: bytes) -> tuple[str, ...]:
    normalized = "/" + name.replace("\\", "/")
    problems: list[str] = []
    for marker in FORBIDDEN_PATH_PARTS:
        if marker in normalized:
            problems.append(f"forbidden distribution path: {name}")
            break
    if b"\x00" in payload:
        return tuple(problems)
    text = payload.decode("utf-8", errors="ignore")
    for marker in FORBIDDEN_TEXT:
        if marker in text:
            problems.append(f"forbidden text marker {marker!r} in {name}")
    if AWS_KEY.search(text):
        problems.append(f"credential-like AWS key in {name}")
    return tuple(problems)


def _zip_members(path: Path) -> Iterable[tuple[str, bytes]]:
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            yield info.filename, archive.read(info)


def _tar_members(path: Path) -> Iterable[tuple[str, bytes]]:
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            handle = archive.extractfile(member)
            if handle is not None:
                yield member.name, handle.read()


def audit(path: Path) -> tuple[str, ...]:
    if path.suffix == ".whl" or path.suffix == ".zip":
        members = _zip_members(path)
    elif path.name.endswith(".tar.gz"):
        members = _tar_members(path)
    else:
        raise ValueError(f"unsupported distribution type: {path}")
    problems: list[str] = []
    for name, payload in members:
        problems.extend(_audit_member(name, payload))
    return tuple(problems)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    problems: list[str] = []
    for path in args.paths:
        current = audit(path)
        problems.extend(f"{path}: {item}" for item in current)
        print(f"{path}: {'PASS' if not current else 'FAIL'}")
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
