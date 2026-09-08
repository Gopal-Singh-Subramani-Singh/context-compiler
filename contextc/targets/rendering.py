"""Deterministic node rendering, chat construction, and source maps."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from contextc.errors import TargetLoweringError
from contextc.ir.nodes import ContextNode
from contextc.targets.types import SourceMapEntry, TargetRenderRequest
from contextc.tokenizers.types import ChatMessage, ChatRole


@dataclass(frozen=True, slots=True)
class NodeSegment:
    node: ContextNode
    text: str
    source_start: int
    source_end: int


@dataclass(frozen=True, slots=True)
class RenderDraft:
    text: str
    segments: tuple[NodeSegment, ...]


def render_node_segment(node: ContextNode) -> str:
    source = node.source
    start = source.start_line or 1
    end = source.end_line or start
    return (
        f"<<<CONTEXT node_id={node.node_id} kind={node.kind.value} "
        f"source={source.uri}:{start}-{end}>>>\n"
        f"{node.content}\n"
        "<<<END_CONTEXT>>>"
    )


def selected_segments(
    request: TargetRenderRequest, selected_node_ids: Sequence[str]
) -> tuple[NodeSegment, ...]:
    segments = []
    for node_id in selected_node_ids:
        node = request.graph.get_node(node_id)
        text = render_node_segment(node)
        source_start = text.find(node.content)
        if source_start < 0:
            raise AssertionError("node content was absent from its deterministic segment")
        segments.append(
            NodeSegment(
                node=node,
                text=text,
                source_start=source_start,
                source_end=source_start + len(node.content),
            )
        )
    return tuple(segments)


def chat_messages(
    request: TargetRenderRequest,
    selected_node_ids: Sequence[str],
    *,
    model_compatible: bool = False,
) -> tuple[tuple[ChatMessage, ...], tuple[NodeSegment, ...]]:
    segments = selected_segments(request, selected_node_ids)
    messages: list[ChatMessage] = []
    developer_parts = tuple(
        (label, part)
        for label, part in (
            ("Developer instruction", request.developer_instruction),
            ("Policy instruction", request.policy_instruction),
            ("Tool schema", request.tool_schema_text),
        )
        if part
    )
    if model_compatible:
        system_parts = [request.system_instruction] if request.system_instruction else []
        system_parts.extend(f"{label}:\n{part}" for label, part in developer_parts)
        if system_parts:
            messages.append(ChatMessage(ChatRole.SYSTEM, "\n\n".join(system_parts)))
    else:
        if request.system_instruction:
            messages.append(ChatMessage(ChatRole.SYSTEM, request.system_instruction))
        if developer_parts:
            messages.append(
                ChatMessage(
                    ChatRole.DEVELOPER,
                    "\n\n".join(part for _label, part in developer_parts),
                )
            )
    if request.user_instruction:
        messages.append(ChatMessage(ChatRole.USER, request.user_instruction))
    if segments:
        messages.append(
            ChatMessage(ChatRole.USER, "\n\n".join(segment.text for segment in segments))
        )
    return tuple(messages), segments


def source_map_for_draft(draft: RenderDraft) -> tuple[SourceMapEntry, ...]:
    """Map the complete final string, including all compiler-generated gaps."""

    locations: list[tuple[int, int, NodeSegment]] = []
    cursor = 0
    for segment in draft.segments:
        start = draft.text.find(segment.text, cursor)
        if start < 0:
            raise TargetLoweringError(
                f"rendered target omitted selected node segment {segment.node.node_id}"
            )
        end = start + len(segment.text)
        locations.append((start, end, segment))
        cursor = end
    entries: list[SourceMapEntry] = []
    cursor = 0
    for start, end, segment in locations:
        source_start = start + segment.source_start
        source_end = start + segment.source_end
        if source_start > cursor:
            entries.append(SourceMapEntry(cursor, source_start, True))
            cursor = source_start
        source = segment.node.source
        if source_end > source_start:
            entries.append(
                SourceMapEntry(
                    source_start,
                    source_end,
                    False,
                    node_id=segment.node.node_id,
                    source_uri=source.uri,
                    source_start_line=source.start_line,
                    source_end_line=source.end_line,
                    transformations=segment.node.transformations,
                )
            )
        cursor = source_end
        if end > cursor:
            entries.append(SourceMapEntry(cursor, end, True))
            cursor = end
    if cursor < len(draft.text):
        entries.append(SourceMapEntry(cursor, len(draft.text), True))
    return tuple(entries)
