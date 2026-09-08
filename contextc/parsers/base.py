"""Source parser contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from contextc.diagnostics.models import Diagnostic
from contextc.ir.nodes import ContextNode


@dataclass(frozen=True, slots=True)
class IndexPolicy:
    max_file_bytes: int = 1_000_000
    include_hidden: bool = False

    def __post_init__(self) -> None:
        if self.max_file_bytes < 1:
            raise ValueError("max_file_bytes must be positive")


@dataclass(frozen=True, slots=True)
class IndexResult:
    root: str
    nodes: tuple[ContextNode, ...]
    diagnostics: tuple[Diagnostic, ...]
    files_considered: int
    schema_version: int = 1


class SourceParser(Protocol):
    def parse(self, root: Path) -> IndexResult:
        """Parse sources under root without executing them."""
