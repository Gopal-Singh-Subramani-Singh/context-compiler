"""Deterministic M9 node transformations."""

from __future__ import annotations

from contextc.ir import ContextNode

_REDACTED = "[REDACTED BY CONTEXTC SECURITY POLICY]"


def quote_as_data(node: ContextNode, rule_id: str) -> ContextNode:
    content = "[BEGIN QUOTED SOURCE DATA]\n" + node.content + "\n[END QUOTED SOURCE DATA]"
    return ContextNode.create(
        node_id=node.node_id,
        kind=node.kind,
        content=content,
        source=node.source,
        created_at=node.created_at,
        trust_domain=node.trust_domain,
        sensitivity=node.sensitivity,
        instruction_authority=node.instruction_authority,
        transformations=(*node.transformations, f"security:{rule_id}:quote_as_data"),
        metadata=node.metadata,
    )


def redact(node: ContextNode, rule_id: str) -> ContextNode:
    return ContextNode.create(
        node_id=node.node_id,
        kind=node.kind,
        content=_REDACTED,
        source=node.source,
        created_at=node.created_at,
        trust_domain=node.trust_domain,
        sensitivity=node.sensitivity,
        instruction_authority=node.instruction_authority,
        transformations=(*node.transformations, f"security:{rule_id}:redact"),
        metadata=node.metadata,
    )
