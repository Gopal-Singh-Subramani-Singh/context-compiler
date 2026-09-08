"""Canonical evaluator-side repository locations and inclusive span algebra."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit

from contextc.errors import SourceValidationError

_REPOSITORY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def canonical_repository_uri(value: str, *, repository_id: str | None = None) -> str:
    """Return an unambiguous canonical ``repo://`` URI.

    Compiler-local ``repo:///path`` locations can be assigned an evaluator repository
    namespace. Dot segments are normalized, while traversal and encoded paths are rejected.
    """

    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or "%" in value
        or any(character.isspace() for character in value)
    ):
        raise SourceValidationError("repository URI must be non-empty and unencoded")
    parsed = urlsplit(value)
    if parsed.scheme != "repo" or parsed.query or parsed.fragment or parsed.username:
        raise SourceValidationError("repository URI must use plain repo:// syntax")
    authority = parsed.netloc
    if repository_id is not None:
        if not _REPOSITORY_ID.fullmatch(repository_id):
            raise SourceValidationError("repository_id is invalid")
        if authority and authority != repository_id:
            raise SourceValidationError("repository URI authority conflicts with repository_id")
        authority = repository_id
    if authority and not _REPOSITORY_ID.fullmatch(authority):
        raise SourceValidationError("repository URI authority is invalid")
    parts: list[str] = []
    for part in parsed.path.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise SourceValidationError("repository URI traversal is forbidden")
        parts.append(part)
    if not parts:
        raise SourceValidationError("repository URI must identify a source path")
    path = "/".join(parts)
    return f"repo://{authority}/{path}" if authority else f"repo:///{path}"


@dataclass(frozen=True, slots=True, order=True)
class SourceSpan:
    """A canonical 1-based inclusive source span."""

    source_uri: str
    start_line: int
    end_line: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_uri", canonical_repository_uri(self.source_uri))
        if (
            not isinstance(self.start_line, int)
            or isinstance(self.start_line, bool)
            or not isinstance(self.end_line, int)
            or isinstance(self.end_line, bool)
            or self.start_line < 1
            or self.end_line < self.start_line
        ):
            raise SourceValidationError("source spans must be 1-based inclusive ranges")

    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1

    def overlaps(self, other: SourceSpan) -> bool:
        return self.source_uri == other.source_uri and not (
            self.end_line < other.start_line or other.end_line < self.start_line
        )

    def intersection_lines(self, other: SourceSpan) -> int:
        if self.source_uri != other.source_uri:
            return 0
        return max(
            0, min(self.end_line, other.end_line) - max(self.start_line, other.start_line) + 1
        )


def union_line_units(spans: Iterable[SourceSpan]) -> frozenset[tuple[str, int]]:
    """Expand tiny evaluator spans into a union that cannot double-count overlap."""

    return frozenset(
        (span.source_uri, line)
        for span in spans
        for line in range(span.start_line, span.end_line + 1)
    )


def selected_span_from_source(
    *, source_uri: str, start_line: int | None, end_line: int | None, repository_id: str
) -> SourceSpan:
    """Namespace a compiler source reference for evaluator-side comparison."""

    canonical = canonical_repository_uri(source_uri, repository_id=repository_id)
    start = 1 if start_line is None else start_line
    end = start if end_line is None else end_line
    return SourceSpan(canonical, start, end)
