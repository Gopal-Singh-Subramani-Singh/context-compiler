"""Deterministic Generic lowering with honest approximate token accounting."""

from __future__ import annotations

from collections.abc import Sequence

from contextc.ir.nodes import ContextNode
from contextc.targets.budget import enforce_final_budget
from contextc.targets.rendering import RenderDraft, chat_messages, render_node_segment
from contextc.targets.types import RenderedContext, TargetId, TargetRenderRequest
from contextc.tokenizers.generic import GenericTokenizer


def render_generic(nodes: Sequence[ContextNode]) -> str:
    """Retain the M1 ordered context-only rendering compatibility surface."""

    sections = [render_node_segment(node) for node in nodes]
    return "\n\n".join(sections) + ("\n" if sections else "")


def _render_draft(request: TargetRenderRequest, selected_node_ids: Sequence[str]) -> RenderDraft:
    messages, segments = chat_messages(request, selected_node_ids)
    parts = ["<<<GENERIC_CHAT version=1>>>"]
    for message in messages:
        parts.extend(
            (
                f"<<<ROLE {message.role.value}>>>",
                message.content,
                "<<<END_ROLE>>>",
            )
        )
    if request.add_generation_prompt:
        parts.append("<<<GENERATION_PROMPT role=assistant>>>")
    text = "\n".join(parts) + "\n"
    return RenderDraft(text=text, segments=segments)


def lower_generic(
    request: TargetRenderRequest,
    *,
    tokenizer: GenericTokenizer | None = None,
) -> RenderedContext:
    """Lower and exactly recount the final Generic approximation target."""

    adapter = tokenizer or GenericTokenizer()
    return enforce_final_budget(
        target_id=TargetId.GENERIC,
        request=request,
        tokenizer=adapter,
        render_draft=_render_draft,
    )
