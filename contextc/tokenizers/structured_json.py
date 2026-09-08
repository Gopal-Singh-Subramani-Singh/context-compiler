"""Exact deterministic tokenizer contract for the M15 structured-JSON target."""

from __future__ import annotations

import hashlib
import re

from contextc.tokenizers.types import TokenizerIdentity

_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


class StructuredJsonTokenizer:
    """Exact regex-unit tokenizer for the structured_json target contract."""

    def __init__(self) -> None:
        self._identity = TokenizerIdentity(
            target_id="structured-json",
            tokenizer_id="structured-json:regex-v1",
            tokenizer_version="1.0.0",
            tokenizer_revision=None,
            configuration={"pattern": _TOKEN.pattern, "unicode": True, "json": "canonical"},
            approximation=(
                "Deterministic regex word/punctuation units; counts are exact for the "
                "structured-json target contract, not for a model tokenizer."
            ),
        )

    @property
    def identity(self) -> TokenizerIdentity:
        return self._identity

    def encode(self, text: str) -> tuple[int, ...]:
        return tuple(
            int.from_bytes(hashlib.sha256(token.encode("utf-8")).digest()[:8], "big")
            for token in _TOKEN.findall(text)
        )

    def count(self, text: str) -> int:
        return len(_TOKEN.findall(text))
