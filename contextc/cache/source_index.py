"""Persistent canonical source URI to computation-key index."""

from __future__ import annotations

import json
from pathlib import Path

from contextc.canonical import canonical_json_bytes


class SourceIndex:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._values: dict[str, set[str]] = {}
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._values = {
                    str(key): {str(v) for v in values}
                    for key, values in raw.items()
                    if isinstance(values, list)
                }

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_bytes(
            canonical_json_bytes(
                {key: sorted(values) for key, values in sorted(self._values.items())}
            )
        )
        temp.replace(self.path)

    def record(self, source_uri: str, key_identity: str) -> None:
        self._values.setdefault(source_uri, set()).add(key_identity)
        self._save()

    def keys_for(self, source_uri: str) -> tuple[str, ...]:
        return tuple(sorted(self._values.get(source_uri, set())))

    def remove_key(self, key_identity: str) -> None:
        empty: list[str] = []
        for source, keys in self._values.items():
            keys.discard(key_identity)
            if not keys:
                empty.append(source)
        for source in empty:
            del self._values[source]
        self._save()
