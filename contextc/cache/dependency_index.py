"""Persistent deterministic dependency index for cache computation keys."""

from __future__ import annotations

import json
from pathlib import Path

from contextc.canonical import canonical_json_bytes


class DependencyIndex:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._deps: dict[str, set[str]] = {}
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._deps = {
                    str(key): {str(v) for v in values}
                    for key, values in raw.items()
                    if isinstance(values, list)
                }

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_bytes(
            canonical_json_bytes(
                {key: sorted(values) for key, values in sorted(self._deps.items())}
            )
        )
        temp.replace(self.path)

    def record(self, key_identity: str, dependencies: tuple[str, ...]) -> None:
        self._deps[key_identity] = set(dependencies)
        self._save()

    def dependencies_of(self, key_identity: str) -> tuple[str, ...]:
        return tuple(sorted(self._deps.get(key_identity, set())))

    def dependents_of(self, key_identity: str) -> tuple[str, ...]:
        return tuple(sorted(key for key, deps in self._deps.items() if key_identity in deps))

    def transitive_dependents(self, roots: tuple[str, ...]) -> tuple[str, ...]:
        seen = set(roots)
        pending = list(sorted(roots))
        while pending:
            current = pending.pop(0)
            for dependent in self.dependents_of(current):
                if dependent not in seen:
                    seen.add(dependent)
                    pending.append(dependent)
        return tuple(sorted(seen))

    def remove(self, key_identity: str) -> None:
        self._deps.pop(key_identity, None)
        for deps in self._deps.values():
            deps.discard(key_identity)
        self._save()
