"""Compiler-visible public benchmark task input; no evaluator imports are allowed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from contextc.decoding import optional_string, require_int, require_sequence, require_string
from contextc.errors import SourceValidationError

from ._records import read_json_yaml
from .source import canonical_repository_uri


@dataclass(frozen=True, slots=True)
class PublicBenchmarkTask:
    task_id: str
    repository_id: str
    repository: Path
    description: str
    token_budget: int
    time_anchor: datetime
    source_revision: str | None = None
    source_content_allowance: int | None = None
    system_instruction: str = ""
    mandatory_symbols: tuple[str, ...] = ()
    blocked_symbols: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.task_id or not self.repository_id or not self.description:
            raise SourceValidationError("public benchmark task identity/description is empty")
        canonical_repository_uri(f"repo://{self.repository_id}/sentinel")
        if self.token_budget < 1:
            raise SourceValidationError("benchmark token budget must be positive")
        if self.source_content_allowance is not None and self.source_content_allowance < 1:
            raise SourceValidationError("benchmark source allowance must be positive")
        if self.time_anchor.tzinfo is None or self.time_anchor.utcoffset() is None:
            raise SourceValidationError("benchmark time anchor must be timezone-aware")
        if any(not item for item in (*self.mandatory_symbols, *self.blocked_symbols)):
            raise SourceValidationError("benchmark symbol requirements must not be empty")


def load_public_task(task_directory: Path) -> PublicBenchmarkTask:
    """Load only compiler-visible input; this function never opens evaluator files."""

    value = read_json_yaml(task_directory / "public" / "task.yaml")
    raw_anchor = require_string(value.get("time_anchor"), "task.time_anchor")
    try:
        anchor = datetime.fromisoformat(raw_anchor.replace("Z", "+00:00"))
    except ValueError as error:
        raise SourceValidationError("benchmark time_anchor is not ISO-8601") from error
    allowance_value = value.get("source_content_allowance")
    allowance = (
        None
        if allowance_value is None
        else require_int(allowance_value, "task.source_content_allowance")
    )
    repository = task_directory / require_string(value.get("repository"), "task.repository")
    if not repository.resolve().is_relative_to(task_directory.resolve()):
        raise SourceValidationError("benchmark repository escapes its task directory")
    return PublicBenchmarkTask(
        task_id=require_string(value.get("task_id"), "task.task_id"),
        repository_id=require_string(value.get("repository_id"), "task.repository_id"),
        repository=repository,
        description=require_string(value.get("description"), "task.description"),
        token_budget=require_int(value.get("token_budget"), "task.token_budget"),
        time_anchor=anchor,
        source_revision=optional_string(value.get("source_revision"), "task.source_revision"),
        source_content_allowance=allowance,
        system_instruction=optional_string(
            value.get("system_instruction"), "task.system_instruction"
        )
        or "",
        mandatory_symbols=tuple(
            require_string(item, "task.mandatory_symbol")
            for item in require_sequence(
                value.get("mandatory_symbols", ()), "task.mandatory_symbols"
            )
        ),
        blocked_symbols=tuple(
            require_string(item, "task.blocked_symbol")
            for item in require_sequence(value.get("blocked_symbols", ()), "task.blocked_symbols")
        ),
    )
