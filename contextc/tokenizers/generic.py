"""Deterministic, dependency-free Generic token approximation."""

from __future__ import annotations

import hashlib
import re

from contextc.tokenizers.types import TokenizerIdentity

_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


class GenericTokenizer:
    """A stable approximation, explicitly not a model tokenizer."""

    def __init__(self) -> None:
        self._identity = TokenizerIdentity(
            target_id="generic",
            tokenizer_id="generic:regex-v1",
            tokenizer_version="1.0.0",
            tokenizer_revision=None,
            configuration={"pattern": _TOKEN.pattern, "unicode": True},
            approximation=(
                "Deterministic regex word/punctuation units; these counts are exact for the "
                "Generic target contract but are not estimates for a particular model."
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
