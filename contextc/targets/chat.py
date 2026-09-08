"""Shared actual chat-template lowering for model-specific targets."""

from __future__ import annotations

from collections.abc import Sequence

from contextc.targets.budget import enforce_final_budget
from contextc.targets.rendering import RenderDraft, chat_messages
from contextc.targets.types import RenderedContext, TargetId, TargetRenderRequest
from contextc.tokenizers.types import ChatTemplateTokenizer


def lower_chat_target(
    *,
    target_id: TargetId,
    request: TargetRenderRequest,
    tokenizer: ChatTemplateTokenizer,
) -> RenderedContext:
    def render_draft(
        current_request: TargetRenderRequest,
        selected_node_ids: Sequence[str],
    ) -> RenderDraft:
        messages, segments = chat_messages(
            current_request,
            selected_node_ids,
            model_compatible=True,
        )
        text = tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=current_request.add_generation_prompt,
        )
        return RenderDraft(text=text, segments=segments)

    return enforce_final_budget(
        target_id=target_id,
        request=request,
        tokenizer=tokenizer,
        render_draft=render_draft,
    )
