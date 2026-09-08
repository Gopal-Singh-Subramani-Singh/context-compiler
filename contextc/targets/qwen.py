"""Qwen target lowering through the configured exact chat tokenizer."""

from __future__ import annotations

from contextc.targets.chat import lower_chat_target
from contextc.targets.types import RenderedContext, TargetId, TargetRenderRequest
from contextc.tokenizers.types import ChatTemplateTokenizer


def lower_qwen(
    request: TargetRenderRequest,
    *,
    tokenizer: ChatTemplateTokenizer,
) -> RenderedContext:
    return lower_chat_target(
        target_id=TargetId.QWEN,
        request=request,
        tokenizer=tokenizer,
    )
