"""Strict tokenizer and chat-template contracts for exact target lowering."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from contextc.canonical import freeze_value
from contextc.errors import SourceValidationError
from contextc.hashing import semantic_hash
from contextc.schema import (
    TOKENIZER_IDENTITY_SCHEMA,
    SchemaVersion,
    require_schema_version,
)


class ChatRole(StrEnum):
    SYSTEM = "system"
    DEVELOPER = "developer"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: ChatRole
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, ChatRole):
            raise SourceValidationError("chat message role must be a ChatRole")
        if not isinstance(self.content, str):
            raise SourceValidationError("chat message content must be text")


@dataclass(frozen=True, slots=True)
class TokenizerIdentity:
    target_id: str
    tokenizer_id: str
    tokenizer_version: str
    tokenizer_revision: str | None
    configuration: Mapping[str, object] = field(default_factory=dict)
    approximation: str | None = None
    schema_version: SchemaVersion = TOKENIZER_IDENTITY_SCHEMA

    def __post_init__(self) -> None:
        if not self.target_id or not self.tokenizer_id:
            raise SourceValidationError("tokenizer target and identity must not be empty")
        if not self.tokenizer_version:
            raise SourceValidationError("tokenizer version must not be empty")
        if self.tokenizer_revision is not None and not self.tokenizer_revision:
            raise SourceValidationError("tokenizer revision must be non-empty or null")
        if self.approximation is not None and not self.approximation:
            raise SourceValidationError("tokenizer approximation statement must not be empty")
        frozen = freeze_value(self.configuration)
        if not isinstance(frozen, Mapping):
            raise SourceValidationError("tokenizer configuration must be a mapping")
        require_schema_version(
            self.schema_version,
            expected=TOKENIZER_IDENTITY_SCHEMA,
            artifact="TokenizerIdentity",
        )
        object.__setattr__(self, "configuration", frozen)

    @property
    def configuration_identity(self) -> str:
        return semantic_hash(self.configuration)


class TargetTokenizer(Protocol):
    @property
    def identity(self) -> TokenizerIdentity: ...

    def count(self, text: str) -> int: ...

    def encode(self, text: str) -> tuple[int, ...]: ...


class ChatTemplateTokenizer(TargetTokenizer, Protocol):
    def apply_chat_template(
        self,
        messages: Sequence[ChatMessage],
        *,
        add_generation_prompt: bool,
    ) -> str: ...


def messages_as_dicts(messages: Sequence[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": message.role.value, "content": message.content} for message in messages]
