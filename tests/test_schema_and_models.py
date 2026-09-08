from dataclasses import FrozenInstanceError, replace

import pytest

from contextc.errors import SchemaVersionError, SourceValidationError
from contextc.hashing import normalized_content_hash
from contextc.ir import ContextNode, NodeAnalysis, NodeKind, SourceReference
from contextc.ir.serialization import deserialize_ir, serialize_ir
from contextc.schema import NODE_SCHEMA, SchemaVersion, migrate_legacy_major_version


def test_source_reference_round_trip_retains_revision_and_spans() -> None:
    source = SourceReference(
        uri="repo:///pkg/a.py",
        revision="git:abc123",
        start_line=2,
        end_line=7,
        start_byte=4,
        end_byte=91,
        language="python",
    )
    payload = serialize_ir(source)
    restored = deserialize_ir(
        payload,
        expected_artifact_type="SourceReference",
        decoder=SourceReference.from_dict,
    )
    assert restored == source


@pytest.mark.parametrize(
    ("start_line", "end_line", "start_byte", "end_byte"),
    [
        (0, 1, None, None),
        (2, 1, None, None),
        (1, None, None, None),
        (None, None, -1, 0),
        (None, None, 2, 1),
        (None, None, 1, None),
    ],
)
def test_source_reference_rejects_malformed_spans(
    start_line: int | None,
    end_line: int | None,
    start_byte: int | None,
    end_byte: int | None,
) -> None:
    with pytest.raises(SourceValidationError):
        SourceReference(
            uri="repo:///a.py",
            start_line=start_line,
            end_line=end_line,
            start_byte=start_byte,
            end_byte=end_byte,
        )


def test_schema_policy_rejects_unsupported_major_and_explicitly_migrates_m1() -> None:
    source = SourceReference(uri="repo:///a.py")
    value = source.to_dict()
    value["schema_version"] = {"major": 9, "minor": 0}
    with pytest.raises(SchemaVersionError) as captured:
        SourceReference.from_dict(value)
    assert captured.value.diagnostic_code == "CTX720"
    assert migrate_legacy_major_version(2) == NODE_SCHEMA
    with pytest.raises(SchemaVersionError):
        migrate_legacy_major_version("2")


def test_schema_version_structure_and_minor_policy_are_strict() -> None:
    with pytest.raises(SourceValidationError):
        SchemaVersion(0, 0)
    with pytest.raises(SourceValidationError):
        SchemaVersion(1, -1)
    source = SourceReference(uri="repo:///a.py")
    value = source.to_dict()
    value["schema_version"] = {"major": 1, "minor": 1}
    with pytest.raises(SchemaVersionError):
        SourceReference.from_dict(value)
    value["schema_version"] = 1
    with pytest.raises(SchemaVersionError):
        SourceReference.from_dict(value)


def test_node_normalization_preserves_semantic_whitespace_and_round_trips() -> None:
    source = SourceReference(uri="repo:///a.txt", start_line=1, end_line=2)
    node = ContextNode.create(
        node_id="node-a",
        kind=NodeKind.DOCUMENT_SECTION,
        content="line  \r\nnext\r",
        source=source,
    )
    assert node.content == "line  \nnext\n"
    assert node.normalized_content_hash == normalized_content_hash("line  \nnext\n")
    assert node.normalized_content_hash != normalized_content_hash("line\nnext\n")
    assert ContextNode.from_dict(node.to_dict()) == node
    with pytest.raises(FrozenInstanceError):
        node.node_id = "changed"  # type: ignore[misc]


def test_unknown_node_kind_is_rejected() -> None:
    node = ContextNode.create(
        node_id="node-a",
        kind=NodeKind.MESSAGE,
        content="hello",
        source=SourceReference(uri="conversation:///1"),
    )
    value = node.to_dict()
    value["kind"] = "future_unknown_kind"
    with pytest.raises(SourceValidationError):
        ContextNode.from_dict(value)


def test_same_source_node_supports_distinct_task_analyses_without_mutation() -> None:
    node = ContextNode.create(
        node_id="node-a",
        kind=NodeKind.FILE,
        content="source",
        source=SourceReference(uri="repo:///a"),
    )
    before = node.to_dict()
    task_a = NodeAnalysis(node_id=node.node_id, relevance=0.9, token_counts={"generic": 4})
    task_b = NodeAnalysis(node_id=node.node_id, relevance=0.1, mandatory=True)
    assert task_a != task_b
    assert node.to_dict() == before
    assert NodeAnalysis.from_dict(task_a.to_dict()) == task_a
    assert not hasattr(node, "token_counts")
    assert not hasattr(node, "selected")


@pytest.mark.parametrize("score", [-0.01, 1.01, float("inf"), float("nan")])
def test_analysis_scores_are_bounded(score: float) -> None:
    with pytest.raises(SourceValidationError):
        NodeAnalysis(node_id="node-a", relevance=score)


def test_analysis_rejects_invalid_token_counts_and_schema_mutation() -> None:
    with pytest.raises(SourceValidationError):
        NodeAnalysis(node_id="node-a", token_counts={"generic": -1})
    with pytest.raises(SourceValidationError):
        NodeAnalysis(node_id="node-a", token_counts={"": 1})
    analysis = NodeAnalysis(node_id="node-a")
    with pytest.raises(SchemaVersionError):
        replace(analysis, schema_version=SchemaVersion(2, 0))
