"""Deterministic source-neutral structured JSON lowering for M15."""

from __future__ import annotations

from collections.abc import Sequence

from contextc.canonical import canonical_json_text, to_canonical_primitive
from contextc.ir import ContextNode
from contextc.targets.budget import enforce_final_budget
from contextc.targets.rendering import NodeSegment, RenderDraft
from contextc.targets.types import RenderedContext, TargetId, TargetRenderRequest
from contextc.tokenizers.structured_json import StructuredJsonTokenizer


def _record(node: ContextNode) -> dict[str, object]:
    metadata = to_canonical_primitive(node.metadata)
    if not isinstance(metadata, dict):
        raise AssertionError("node metadata did not canonicalize to object")
    return {
        "content": node.content,
        "created_at": node.created_at,
        "instruction_authority": node.instruction_authority.value,
        "kind": node.kind.value,
        "metadata": metadata,
        "node_id": node.node_id,
        "provenance": node.source.to_dict(),
        "sensitivity": node.sensitivity.value,
        "transformations": node.transformations,
        "trust_domain": node.trust_domain.value,
    }


def render_structured_record(node: ContextNode) -> str:
    """Render one deterministic record for analysis/token accounting."""

    return canonical_json_text(_record(node))


def _render_draft(request: TargetRenderRequest, selected_node_ids: Sequence[str]) -> RenderDraft:
    segments: list[NodeSegment] = []
    record_texts: list[str] = []
    for node_id in selected_node_ids:
        node = request.graph.get_node(node_id)
        text = render_structured_record(node)
        encoded_content = canonical_json_text(node.content)
        source_start = text.find(encoded_content)
        if source_start < 0:
            raise AssertionError("structured record omitted node content")
        segments.append(
            NodeSegment(
                node=node,
                text=text,
                source_start=source_start,
                source_end=source_start + len(encoded_content),
            )
        )
        record_texts.append(text)
    instructions = canonical_json_text(
        {
            "developer": request.developer_instruction,
            "policy": request.policy_instruction,
            "system": request.system_instruction,
            "tool_schema": request.tool_schema_text,
        }
    )
    task = canonical_json_text(request.user_instruction)
    text = (
        '{"instructions":'
        + instructions
        + ',"records":['
        + ",".join(record_texts)
        + '],"schema_version":1,"target":"structured-json","task":'
        + task
        + "}\n"
    )
    return RenderDraft(text=text, segments=tuple(segments))


def lower_structured_json(
    request: TargetRenderRequest,
    *,
    tokenizer: StructuredJsonTokenizer | None = None,
) -> RenderedContext:
    adapter = tokenizer or StructuredJsonTokenizer()
    return enforce_final_budget(
        target_id=TargetId.STRUCTURED_JSON,
        request=request,
        tokenizer=adapter,
        render_draft=_render_draft,
    )
