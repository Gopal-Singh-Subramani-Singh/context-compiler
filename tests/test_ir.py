from dataclasses import FrozenInstanceError

import pytest

from contextc.errors import SourceValidationError
from contextc.ir import (
    ContextEdge,
    ContextNode,
    EdgeType,
    NodeAnalysis,
    NodeKind,
    SelectionResult,
    SourceReference,
)
from contextc.ir.serialization import serialize_ir


def source() -> SourceReference:
    return SourceReference(uri="repo:///a.py", start_line=1, end_line=2, language="python")


def test_source_reference_validation() -> None:
    with pytest.raises(SourceValidationError):
        SourceReference(uri="")
    with pytest.raises(SourceValidationError):
        SourceReference(uri="x", start_line=2, end_line=1)
    with pytest.raises(SourceValidationError):
        SourceReference(uri="x", start_byte=0)


def test_context_node_is_immutable_and_metadata_is_deeply_frozen() -> None:
    metadata = {"nested": {"items": [1, 2]}}
    node = ContextNode.create(
        node_id="node-1",
        kind=NodeKind.MODULE,
        content="x = 1\r\n",
        source=source(),
        metadata=metadata,
    )
    metadata["new"] = True
    with pytest.raises(FrozenInstanceError):
        node.content = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        node.metadata["changed"] = True  # type: ignore[index]
    assert node.content == "x = 1\n"
    assert "new" not in node.metadata


def test_context_node_rejects_false_content_identity() -> None:
    with pytest.raises(SourceValidationError):
        ContextNode(
            node_id="node-1",
            kind=NodeKind.FILE,
            content="content",
            normalized_content_hash="sha256:not-real",
            source=source(),
        )


def test_analysis_and_selection_are_separate_from_source_facts() -> None:
    node = ContextNode.create(
        node_id="node-1", kind=NodeKind.FILE, content="content", source=source()
    )
    analysis = NodeAnalysis(node_id=node.node_id, relevance=0.5, token_counts={"generic": 3})
    selection = SelectionResult((node.node_id,))
    assert not hasattr(node, "selected")
    assert not hasattr(node, "relevance")
    assert analysis.relevance == 0.5
    assert selection.selected_node_ids == (node.node_id,)


def test_analysis_validation() -> None:
    with pytest.raises(SourceValidationError):
        NodeAnalysis(node_id="n", relevance=float("nan"))
    with pytest.raises(SourceValidationError):
        NodeAnalysis(node_id="n", token_counts={"generic": -1})


def test_edges_are_typed_and_validate_endpoints() -> None:
    assert ContextEdge("a", "b", EdgeType.IMPORTS).edge_type is EdgeType.IMPORTS
    with pytest.raises(SourceValidationError):
        ContextEdge("", "b", EdgeType.CALLS)


def test_versioned_ir_serialization_is_deterministic() -> None:
    node = ContextNode.create(
        node_id="node-1", kind=NodeKind.FILE, content="content", source=source()
    )
    assert serialize_ir(node) == serialize_ir(node)
    assert b'"schema_version":{"major":1,"minor":0}' in serialize_ir(node)
