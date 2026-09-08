"""Stable cryptographic identities for semantic content."""

from __future__ import annotations

from hashlib import sha256

from contextc.canonical import canonical_json_bytes, normalize_text


def digest_bytes(value: bytes) -> str:
    """Return a version-explicit SHA-256 digest string."""

    return f"sha256:{sha256(value).hexdigest()}"


def semantic_hash(value: object) -> str:
    """Hash the canonical semantic representation of a value."""

    return digest_bytes(canonical_json_bytes(value))


def normalized_content_hash(content: str) -> str:
    """Hash normalized textual content as UTF-8."""

    return digest_bytes(normalize_text(content).encode("utf-8"))
