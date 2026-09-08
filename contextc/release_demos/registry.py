"""Package-resource loading and deterministic integrity verification for M16 demos."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from importlib.resources import files
from importlib.resources.abc import Traversable

from contextc.release_demos.models import (
    DemoFileRecord,
    DemoKind,
    DemoRegistry,
    ReleaseDemo,
)

PACKAGE = "contextc.resources.release_demos"
_FORBIDDEN_RESOURCE_PATH_PARTS = (
    "benchmarks/",
    "tests/fixtures/",
    ".contextc/cache/",
    "quarantine/",
)
_FORBIDDEN_CONTENT_MARKERS = (
    "EVAL" + "_ONLY_",
    "/" + "Users/",
    "/" + "home/",
    "AK" + "IA",
    "BEGIN " + "PRIVATE KEY",
)


def _root() -> Traversable:
    return files(PACKAGE)


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


def load_registry() -> DemoRegistry:
    raw = json.loads(_root().joinpath("registry.json").read_text(encoding="utf-8"))
    top = _mapping(raw, "registry")
    schema = _mapping(top.get("schema_version"), "registry.schema_version")
    demos_raw = top.get("demos")
    if not isinstance(demos_raw, list):
        raise ValueError("registry.demos must be a list")
    demos: list[ReleaseDemo] = []
    seen: set[str] = set()
    for item in demos_raw:
        value = _mapping(item, "registry demo")
        demo_id = _string(value.get("demo_id"), "demo_id")
        if demo_id in seen:
            raise ValueError(f"duplicate release demo ID {demo_id}")
        seen.add(demo_id)
        file_values = value.get("files")
        if not isinstance(file_values, list):
            raise ValueError(f"release demo {demo_id} files must be a list")
        records: list[DemoFileRecord] = []
        for raw_file in file_values:
            file_value = _mapping(raw_file, f"release demo {demo_id} file")
            records.append(
                DemoFileRecord(
                    path=_string(file_value.get("path"), "file.path"),
                    sha256=_string(file_value.get("sha256"), "file.sha256"),
                    bytes=_integer(file_value.get("bytes"), "file.bytes"),
                )
            )
        demos.append(
            ReleaseDemo(
                demo_id=demo_id,
                title=_string(value.get("title"), "title"),
                kind=DemoKind(_string(value.get("kind"), "kind")),
                profile_version=_string(value.get("profile_version"), "profile_version"),
                description=_string(value.get("description"), "description"),
                offline=_bool(value.get("offline"), "offline"),
                tool_execution=_bool(value.get("tool_execution"), "tool_execution"),
                default_target=_string(value.get("default_target"), "default_target"),
                default_strategy=_string(value.get("default_strategy"), "default_strategy"),
                default_budget=_integer(value.get("default_budget"), "default_budget"),
                expected=_mapping(value.get("expected", {}), "expected"),
                files=tuple(records),
            )
        )
    return DemoRegistry(
        registry_id=_string(top.get("registry_id"), "registry_id"),
        profile_version=_string(top.get("profile_version"), "profile_version"),
        schema_major=_integer(schema.get("major"), "schema_version.major"),
        schema_minor=_integer(schema.get("minor"), "schema_version.minor"),
        demos=tuple(demos),
    )


def resource_for(demo_id: str, relative: str) -> Traversable:
    return _root().joinpath(demo_id, *relative.split("/"))


def read_resource_bytes(demo_id: str, relative: str) -> bytes:
    return resource_for(demo_id, relative).read_bytes()


def verify_file_record(demo_id: str, record: DemoFileRecord) -> tuple[str, ...]:
    problems: list[str] = []
    if record.path.startswith("/") or ".." in record.path.split("/"):
        return (f"unsafe resource path {record.path}",)
    if any(marker in record.path for marker in _FORBIDDEN_RESOURCE_PATH_PARTS):
        problems.append(f"forbidden resource path dependency {record.path}")
    try:
        payload = read_resource_bytes(demo_id, record.path)
    except FileNotFoundError:
        return (f"missing resource {record.path}",)
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    if digest != record.sha256:
        problems.append(f"resource digest mismatch {record.path}")
    if len(payload) != record.bytes:
        problems.append(f"resource byte-count mismatch {record.path}")
    if b"\x00" not in payload:
        text = payload.decode("utf-8", errors="ignore")
        for marker in _FORBIDDEN_CONTENT_MARKERS:
            if marker in text:
                problems.append(f"forbidden release marker {marker!r} in {record.path}")
    return tuple(problems)
