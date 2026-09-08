"""Lazy exact Hugging Face chat-tokenizer adapters."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from importlib import import_module
from typing import Protocol, cast

from contextc.errors import TargetLoweringError, TokenizerUnavailableError
from contextc.tokenizers.types import ChatMessage, TokenizerIdentity, messages_as_dicts


class _HuggingFaceTokenizer(Protocol):
    name_or_path: str
    chat_template: str | None
    vocab_size: int
    special_tokens_map: dict[str, object]

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]: ...

    def apply_chat_template(
        self,
        conversation: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class TransformersTokenizerConfig:
    model_id: str
    revision: str | None = None
    local_files_only: bool = True
    trust_remote_code: bool = False
    use_fast: bool = True


class TransformersChatTokenizer:
    """Configured exact tokenizer; importing this module does not import transformers."""

    target_id = ""
    extra_name = ""

    def __init__(
        self,
        *,
        model_id: str,
        revision: str | None = None,
        local_files_only: bool = True,
        trust_remote_code: bool = False,
        use_fast: bool = True,
    ) -> None:
        config = TransformersTokenizerConfig(
            model_id=model_id,
            revision=revision,
            local_files_only=local_files_only,
            trust_remote_code=trust_remote_code,
            use_fast=use_fast,
        )
        guidance = f"Install with `pip install 'context-compiler[{self.extra_name}]'`"
        try:
            module = import_module("transformers")
            auto_tokenizer = module.AutoTokenizer
            loaded = auto_tokenizer.from_pretrained(
                model_id,
                revision=revision,
                local_files_only=local_files_only,
                trust_remote_code=trust_remote_code,
                use_fast=use_fast,
            )
            tokenizer = cast(_HuggingFaceTokenizer, loaded)
            if not tokenizer.chat_template:
                raise ValueError("configured tokenizer has no chat_template")
            version = str(getattr(module, "__version__", "0.0.0"))
        except Exception as error:
            raise TokenizerUnavailableError(
                target_id=self.target_id,
                tokenizer_id=model_id,
                installation_guidance=guidance,
                original_cause=error,
            ) from error
        self._tokenizer = tokenizer
        self._installation_guidance = guidance
        self._identity = TokenizerIdentity(
            target_id=self.target_id,
            tokenizer_id=model_id,
            tokenizer_version=version,
            tokenizer_revision=revision,
            configuration={
                "adapter": type(tokenizer).__name__,
                "chat_template": tokenizer.chat_template,
                "local_files_only": local_files_only,
                "model_id": model_id,
                "name_or_path": tokenizer.name_or_path,
                "special_tokens_map": tokenizer.special_tokens_map,
                "trust_remote_code": trust_remote_code,
                "use_fast": use_fast,
                "vocab_size": tokenizer.vocab_size,
            },
        )
        self.config = config

    @property
    def identity(self) -> TokenizerIdentity:
        return self._identity

    def encode(self, text: str) -> tuple[int, ...]:
        return tuple(self._tokenizer.encode(text, add_special_tokens=False))

    def count(self, text: str) -> int:
        return len(self.encode(text))

    def apply_chat_template(
        self,
        messages: Sequence[ChatMessage],
        *,
        add_generation_prompt: bool,
    ) -> str:
        try:
            return self._tokenizer.apply_chat_template(
                messages_as_dicts(messages),
                tokenize=False,
                add_generation_prompt=add_generation_prompt,
            )
        except Exception as error:
            if isinstance(error, (ImportError, ModuleNotFoundError)):
                raise TokenizerUnavailableError(
                    target_id=self.target_id,
                    tokenizer_id=self.identity.tokenizer_id,
                    installation_guidance=self._installation_guidance,
                    original_cause=error,
                ) from error
            raise TargetLoweringError(
                f"{self.target_id} chat template failed for {self.identity.tokenizer_id!r}: {error}"
            ) from error


class QwenTokenizerAdapter(TransformersChatTokenizer):
    target_id = "qwen"
    extra_name = "qwen"


class LlamaTokenizerAdapter(TransformersChatTokenizer):
    target_id = "llama"
    extra_name = "llama"
