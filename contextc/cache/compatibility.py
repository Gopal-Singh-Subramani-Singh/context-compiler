"""Explicit cache compatibility rules."""

from contextc.cache.keys import CACHE_SCHEMA_VERSION

SUPPORTED_CACHE_SCHEMA_VERSIONS = frozenset({CACHE_SCHEMA_VERSION})


def is_cache_schema_compatible(version: int) -> bool:
    return version in SUPPORTED_CACHE_SCHEMA_VERSIONS
