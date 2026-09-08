"""Deterministic M1 project configuration."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from contextc.errors import ConfigurationError
from contextc.hashing import semantic_hash
from contextc.source_rules import SourceFactRule, source_rules_from_sequence


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Validated compiler configuration owned by the M1 foundation."""

    max_file_bytes: int = 1_000_000
    include_hidden: bool = False
    build_root: str = ".contextc/build"
    cache_root: str = ".contextc/cache"
    schema_version: int = 1
    source_rules: tuple[SourceFactRule, ...] = ()

    def __post_init__(self) -> None:
        if self.max_file_bytes < 1:
            raise ConfigurationError("max_file_bytes must be a positive integer")
        if not self.build_root or not self.cache_root:
            raise ConfigurationError("build_root and cache_root must not be empty")
        if self.schema_version != 1:
            raise ConfigurationError("unsupported M1 configuration schema version")

    @property
    def identity(self) -> str:
        """Return the identity of all M1 semantics-affecting configuration."""

        return semantic_hash(self)


def _parse_mapping(raw: Mapping[str, object]) -> ProjectConfig:
    allowed = {
        "max_file_bytes",
        "include_hidden",
        "build_root",
        "cache_root",
        "schema_version",
        "source_rules",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ConfigurationError(f"unknown configuration keys: {', '.join(unknown)}")
    parsed = dict(raw)
    parsed["source_rules"] = source_rules_from_sequence(raw.get("source_rules"))
    try:
        return ProjectConfig(**parsed)  # type: ignore[arg-type]
    except TypeError as error:
        raise ConfigurationError(str(error)) from error


def load_project_config(path: Path | None = None) -> ProjectConfig:
    """Load `contextc.toml` or `[tool.contextc]` from a pyproject file."""

    if path is None:
        return ProjectConfig()
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigurationError(f"cannot read configuration {path}: {error}") from error
    raw: object
    if path.name == "pyproject.toml":
        tool = payload.get("tool", {})
        if not isinstance(tool, dict):
            raise ConfigurationError("[tool] must be a TOML table")
        raw = tool.get("contextc", {})
    else:
        raw = payload.get("contextc", payload)
    if not isinstance(raw, dict):
        raise ConfigurationError("Context Compiler configuration must be a TOML table")
    return _parse_mapping(raw)


def apply_cli_overrides(config: ProjectConfig, overrides: Mapping[str, object]) -> ProjectConfig:
    """Apply explicit CLI values after project configuration."""

    clean = {key: value for key, value in overrides.items() if value is not None}
    cli_fields = {"max_file_bytes", "include_hidden", "build_root", "cache_root", "schema_version"}
    unknown = sorted(set(clean) - cli_fields)
    if unknown:
        raise ConfigurationError(f"unknown CLI configuration keys: {', '.join(unknown)}")
    updated = config
    for key, value in clean.items():
        if key == "max_file_bytes":
            if not isinstance(value, int) or isinstance(value, bool):
                raise ConfigurationError(f"{key} must be an integer")
            updated = replace(updated, max_file_bytes=value)
        elif key == "schema_version":
            if not isinstance(value, int) or isinstance(value, bool):
                raise ConfigurationError(f"{key} must be an integer")
            updated = replace(updated, schema_version=value)
        elif key == "include_hidden":
            if not isinstance(value, bool):
                raise ConfigurationError("include_hidden must be a boolean")
            updated = replace(updated, include_hidden=value)
        elif key == "build_root":
            if not isinstance(value, str):
                raise ConfigurationError(f"{key} must be a string")
            updated = replace(updated, build_root=value)
        elif key == "cache_root":
            if not isinstance(value, str):
                raise ConfigurationError(f"{key} must be a string")
            updated = replace(updated, cache_root=value)
    return updated
