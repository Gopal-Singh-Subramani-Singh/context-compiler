"""Narrow semantic pass-version registry used by incremental cache keys."""

from __future__ import annotations

from types import MappingProxyType

PASS_VERSIONS = MappingProxyType(
    {
        "source_content": "1.0.0",
        "parse": "1.0.0",
        "static_graph": "1.0.0",
        "analysis": "1.0.0",
        "security": "1.0.0",
        "supersession": "1.0.0",
        "token_count": "1.0.0",
        "selection": "1.0.0",
        "lowering": "1.0.0",
        "artifact": "1.0.0",
        "capability_analysis": "1.0.0",
    }
)


def pass_version(stage: str) -> str:
    """Return one stable semantic pass version."""

    try:
        return PASS_VERSIONS[stage]
    except KeyError as error:
        raise ValueError(f"unknown pass stage {stage!r}") from error
