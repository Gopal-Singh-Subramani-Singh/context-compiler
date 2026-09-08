"""Atomic local content-addressed object store with corruption quarantine."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contextc.cache.compatibility import is_cache_schema_compatible
from contextc.cache.keys import ComputationKey
from contextc.canonical import canonical_json_bytes
from contextc.hashing import digest_bytes


class CacheEntryError(RuntimeError):
    """Raised when a cache entry is unusable or corrupt."""


@dataclass(frozen=True, slots=True)
class CacheEntry:
    key: ComputationKey
    payload: bytes
    object_identity: str
    dependencies: tuple[str, ...]
    source_uris: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CachePutResult:
    entry: CacheEntry
    deduplicated: bool


class ContentAddressedStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.objects = root / "objects"
        self.metadata = root / "metadata"
        self.quarantine = root / "quarantine"
        self.source_index_root = root / "source-index"
        for path in (self.objects, self.metadata, self.quarantine, self.source_index_root):
            path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_id(identity: str) -> str:
        return identity.removeprefix("sha256:")

    def _object_path(self, identity: str) -> Path:
        raw = self._safe_id(identity)
        return self.objects / raw[:2] / raw[2:]

    def _metadata_path(self, key: ComputationKey) -> Path:
        return self.metadata / f"{self._safe_id(key.identity)}.json"

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temp_name)

    def put(
        self,
        key: ComputationKey,
        payload: bytes,
        *,
        dependencies: tuple[str, ...] = (),
        source_uris: tuple[str, ...] = (),
    ) -> CachePutResult:
        object_identity = digest_bytes(payload)
        object_path = self._object_path(object_identity)
        deduplicated = object_path.exists()
        if not deduplicated:
            self._atomic_write(object_path, payload)
        metadata = {
            "cache_schema_version": key.cache_schema_version,
            "key": key.to_dict(),
            "key_identity": key.identity,
            "object_identity": object_identity,
            "dependencies": sorted(set(dependencies)),
            "source_uris": sorted(set(source_uris)),
        }
        self._atomic_write(self._metadata_path(key), canonical_json_bytes(metadata))
        return CachePutResult(
            entry=CacheEntry(
                key=key,
                payload=payload,
                object_identity=object_identity,
                dependencies=tuple(sorted(set(dependencies))),
                source_uris=tuple(sorted(set(source_uris))),
            ),
            deduplicated=deduplicated,
        )

    def _quarantine(self, metadata_path: Path, object_path: Path | None, reason: str) -> None:
        stem = metadata_path.stem
        qdir = self.quarantine / stem
        qdir.mkdir(parents=True, exist_ok=True)
        if metadata_path.exists():
            os.replace(metadata_path, qdir / "metadata.json")
        if object_path is not None and object_path.exists():
            os.replace(object_path, qdir / "object.bin")
        self._atomic_write(qdir / "reason.txt", reason.encode("utf-8"))

    def get(self, key: ComputationKey) -> CacheEntry | None:
        metadata_path = self._metadata_path(key)
        if not metadata_path.exists():
            return None
        object_path: Path | None = None
        try:
            raw = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise CacheEntryError("cache metadata is not an object")
            version = raw.get("cache_schema_version")
            if not isinstance(version, int) or not is_cache_schema_compatible(version):
                raise CacheEntryError("incompatible cache schema")
            if raw.get("key_identity") != key.identity:
                raise CacheEntryError("cache metadata key identity mismatch")
            object_identity = raw.get("object_identity")
            if not isinstance(object_identity, str):
                raise CacheEntryError("cache metadata object identity missing")
            object_path = self._object_path(object_identity)
            if not object_path.exists():
                raise CacheEntryError("cache object is missing")
            payload = object_path.read_bytes()
            if digest_bytes(payload) != object_identity:
                raise CacheEntryError("cache object content hash mismatch")
            deps = raw.get("dependencies", [])
            sources = raw.get("source_uris", [])
            if not isinstance(deps, list) or not all(isinstance(v, str) for v in deps):
                raise CacheEntryError("cache dependencies malformed")
            if not isinstance(sources, list) or not all(isinstance(v, str) for v in sources):
                raise CacheEntryError("cache source index metadata malformed")
            return CacheEntry(
                key=key,
                payload=payload,
                object_identity=object_identity,
                dependencies=tuple(deps),
                source_uris=tuple(sources),
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, CacheEntryError) as error:
            self._quarantine(metadata_path, object_path, str(error))
            return None

    def delete_key_identity(self, key_identity: str) -> bool:
        path = self.metadata / f"{self._safe_id(key_identity)}.json"
        if not path.exists():
            return False
        path.unlink()
        return True

    def iter_metadata(self) -> tuple[dict[str, Any], ...]:
        records: list[dict[str, Any]] = []
        for path in sorted(self.metadata.glob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                records.append(value)
        return tuple(records)

    def verify(self) -> tuple[str, ...]:
        problems: list[str] = []
        for record in self.iter_metadata():
            key_raw = record.get("key")
            if not isinstance(key_raw, dict):
                problems.append("CTX700 metadata missing key")
                continue
            try:
                key = ComputationKey(
                    namespace=str(key_raw["namespace"]),
                    stage=str(key_raw["stage"]),
                    semantic_input_identity=str(key_raw["semantic_input_identity"]),
                    cache_schema_version=int(key_raw["cache_schema_version"]),
                )
            except (KeyError, TypeError, ValueError):
                problems.append("CTX700 metadata has invalid computation key")
                continue
            if self.get(key) is None:
                problems.append(f"CTX700 invalid:{key.identity}")
        return tuple(problems)
