"""Typed operational cache reports (not semantic compiler outputs)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CacheStageEvent:
    stage: str
    key_identity: str
    status: str
    source_uri: str | None = None


@dataclass(frozen=True, slots=True)
class CacheReport:
    events: tuple[CacheStageEvent, ...] = ()

    @property
    def reused(self) -> tuple[CacheStageEvent, ...]:
        return tuple(event for event in self.events if event.status == "reused")

    @property
    def recomputed(self) -> tuple[CacheStageEvent, ...]:
        return tuple(event for event in self.events if event.status == "recomputed")

    def to_dict(self) -> dict[str, object]:
        def event_dict(event: CacheStageEvent) -> dict[str, str | None]:
            return {
                "stage": event.stage,
                "key_identity": event.key_identity,
                "status": event.status,
                "source_uri": event.source_uri,
            }

        return {
            "reused": [event_dict(event) for event in self.reused],
            "recomputed": [event_dict(event) for event in self.recomputed],
        }
