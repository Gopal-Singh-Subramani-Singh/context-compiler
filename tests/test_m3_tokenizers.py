import sys
from types import SimpleNamespace
from typing import ClassVar

import pytest

from contextc.errors import TargetLoweringError, TokenizerUnavailableError
from contextc.tokenizers import (
    ChatMessage,
    ChatRole,
    GenericTokenizer,
    LlamaTokenizerAdapter,
    QwenTokenizerAdapter,
)


class FakeHuggingFaceTokenizer:
    name_or_path = "fake/model"
    chat_template = "fake-template-v1"
    vocab_size = 256
    special_tokens_map: ClassVar[dict[str, object]] = {"bos_token": "<s>"}

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
        assert not add_special_tokens
        return list(text.encode())

    def apply_chat_template(
        self,
        conversation: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
    ) -> str:
        assert not tokenize
        result = "".join(
            f"<{message['role']}>{message['content']}</{message['role']}>"
            for message in conversation
        )
        return result + ("<assistant>" if add_generation_prompt else "")


class FakeAutoTokenizer:
    @staticmethod
    def from_pretrained(model_id: str, **kwargs: object) -> FakeHuggingFaceTokenizer:
        assert model_id == "fake/model"
        assert kwargs["revision"] == "revision-1"
        return FakeHuggingFaceTokenizer()


def test_generic_tokenizer_identity_and_counts_are_deterministic() -> None:
    tokenizer = GenericTokenizer()
    assert tokenizer.count("hello, world") == 3
    assert tokenizer.encode("hello, world") == tokenizer.encode("hello, world")
    assert tokenizer.identity.target_id == "generic"
    assert tokenizer.identity.tokenizer_revision is None
    assert tokenizer.identity.configuration_identity.startswith("sha256:")
    assert "not estimates for a particular model" in (tokenizer.identity.approximation or "")


def test_qwen_and_llama_adapters_use_lazy_configured_chat_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import contextc.tokenizers.transformers as adapters

    fake_module = SimpleNamespace(AutoTokenizer=FakeAutoTokenizer, __version__="4.99.0")
    monkeypatch.setattr(adapters, "import_module", lambda name: fake_module)
    messages = (ChatMessage(ChatRole.USER, "hello"),)
    for adapter_type, target in (
        (QwenTokenizerAdapter, "qwen"),
        (LlamaTokenizerAdapter, "llama"),
    ):
        adapter = adapter_type(model_id="fake/model", revision="revision-1")
        rendered = adapter.apply_chat_template(messages, add_generation_prompt=True)
        assert rendered == "<user>hello</user><assistant>"
        assert adapter.count(rendered) == len(rendered.encode())
        assert adapter.identity.target_id == target
        assert adapter.identity.tokenizer_id == "fake/model"
        assert adapter.identity.tokenizer_revision == "revision-1"


@pytest.mark.parametrize(
    ("adapter_type", "target", "extra"),
    [
        (QwenTokenizerAdapter, "qwen", "qwen"),
        (LlamaTokenizerAdapter, "llama", "llama"),
    ],
)
def test_missing_model_tokenizer_is_typed_and_never_falls_back(
    monkeypatch: pytest.MonkeyPatch,
    adapter_type: type[QwenTokenizerAdapter] | type[LlamaTokenizerAdapter],
    target: str,
    extra: str,
) -> None:
    import contextc.tokenizers.transformers as adapters

    cause = ModuleNotFoundError("no transformers")

    def fail_import(name: str) -> object:
        raise cause

    monkeypatch.setattr(adapters, "import_module", fail_import)
    with pytest.raises(TokenizerUnavailableError) as captured:
        adapter_type(model_id="configured/model")
    error = captured.value
    assert error.diagnostic_code == "CTX710"
    assert error.target_id == target
    assert error.tokenizer_id == "configured/model"
    assert f"context-compiler[{extra}]" in error.installation_guidance
    assert error.original_cause is cause
    assert error.__cause__ is cause


def test_bad_chat_template_failure_is_typed(monkeypatch: pytest.MonkeyPatch) -> None:
    import contextc.tokenizers.transformers as adapters

    class Broken(FakeHuggingFaceTokenizer):
        def apply_chat_template(
            self,
            conversation: list[dict[str, str]],
            *,
            tokenize: bool,
            add_generation_prompt: bool,
        ) -> str:
            raise RuntimeError("bad template")

    class BrokenAuto:
        @staticmethod
        def from_pretrained(model_id: str, **kwargs: object) -> Broken:
            return Broken()

    monkeypatch.setattr(
        adapters,
        "import_module",
        lambda name: SimpleNamespace(AutoTokenizer=BrokenAuto, __version__="4.99.0"),
    )
    tokenizer = QwenTokenizerAdapter(model_id="fake/model")
    with pytest.raises(TargetLoweringError, match="chat template failed"):
        tokenizer.apply_chat_template((), add_generation_prompt=False)


def test_missing_chat_template_runtime_uses_ctx710_and_preserves_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import contextc.tokenizers.transformers as adapters

    cause = ImportError("apply_chat_template requires jinja2")

    class MissingRuntime(FakeHuggingFaceTokenizer):
        def apply_chat_template(
            self,
            conversation: list[dict[str, str]],
            *,
            tokenize: bool,
            add_generation_prompt: bool,
        ) -> str:
            raise cause

    class MissingRuntimeAuto:
        @staticmethod
        def from_pretrained(model_id: str, **kwargs: object) -> MissingRuntime:
            return MissingRuntime()

    monkeypatch.setattr(
        adapters,
        "import_module",
        lambda name: SimpleNamespace(
            AutoTokenizer=MissingRuntimeAuto,
            __version__="4.99.0",
        ),
    )
    tokenizer = QwenTokenizerAdapter(model_id="fake/model")
    with pytest.raises(TokenizerUnavailableError) as captured:
        tokenizer.apply_chat_template((), add_generation_prompt=False)
    error = captured.value
    assert error.diagnostic_code == "CTX710"
    assert error.original_cause is cause
    assert error.__cause__ is cause
    assert "context-compiler[qwen]" in error.installation_guidance


def test_transformers_is_not_imported_by_core_startup() -> None:
    assert "transformers" not in sys.modules
