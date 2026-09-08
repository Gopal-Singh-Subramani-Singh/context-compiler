"""Typed M16 release-demo registry, verification, and run evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class DemoKind(str, Enum):  # noqa: UP042
    REPOSITORY_BUG = "repository_bug"
    INCIDENT_RESPONSE = "incident_response"
    INCREMENTAL_REBUILD = "incremental_rebuild"
    CAPABILITY_COMPOSITION = "capability_composition"


@dataclass(frozen=True, slots=True)
class DemoFileRecord:
    path: str
    sha256: str
    bytes: int


@dataclass(frozen=True, slots=True)
class ReleaseDemo:
    demo_id: str
    title: str
    kind: DemoKind
    profile_version: str
    description: str
    offline: bool
    tool_execution: bool
    default_target: str
    default_strategy: str
    default_budget: int
    expected: Mapping[str, object]
    files: tuple[DemoFileRecord, ...]


@dataclass(frozen=True, slots=True)
class DemoRegistry:
    registry_id: str
    profile_version: str
    schema_major: int
    schema_minor: int
    demos: tuple[ReleaseDemo, ...]


@dataclass(frozen=True, slots=True)
class DemoVerification:
    demo_id: str
    valid: bool
    files_checked: int
    semantic_checks: tuple[str, ...]
    problems: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RegistryVerification:
    valid: bool
    registry_id: str
    demos_checked: int
    demo_results: tuple[DemoVerification, ...]
    problems: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DemoRunResult:
    demo_id: str
    kind: DemoKind
    title: str
    summary: Mapping[str, object]
    compile: Mapping[str, object]
    graph: Mapping[str, object]
    comparison: Mapping[str, object]
    reproduction: Mapping[str, object]
    security: Mapping[str, object]
    incremental_capabilities: Mapping[str, object]
