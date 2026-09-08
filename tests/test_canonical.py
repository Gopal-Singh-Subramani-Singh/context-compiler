from dataclasses import dataclass
from enum import StrEnum

import pytest

from contextc.canonical import (
    canonical_json_bytes,
    canonical_json_text,
    freeze_value,
    normalize_text,
)
from contextc.errors import CanonicalizationError
from contextc.hashing import normalized_content_hash, semantic_hash


class Choice(StrEnum):
    VALUE = "value"


@dataclass(frozen=True)
class Payload:
    choice: Choice
    text: str


def test_mapping_insertion_order_does_not_change_canonical_bytes() -> None:
    left = {"b": 2, "a": 1}
    right = {"a": 1, "b": 2}
    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert semantic_hash(left) == semantic_hash(right)


def test_semantic_change_changes_identity() -> None:
    assert semantic_hash({"value": 1}) != semantic_hash({"value": 2})


def test_text_newlines_are_normalized() -> None:
    assert normalize_text("a\r\nb\rc") == "a\nb\nc"
    assert normalized_content_hash("a\r\nb") == normalized_content_hash("a\nb")
    assert canonical_json_text(Payload(Choice.VALUE, "a\r\nb")) == (
        '{"choice":"value","text":"a\\nb"}'
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_float_is_rejected(value: float) -> None:
    with pytest.raises(CanonicalizationError):
        canonical_json_bytes(value)


def test_unsupported_values_and_non_string_keys_are_rejected() -> None:
    with pytest.raises(CanonicalizationError):
        canonical_json_bytes(object())
    with pytest.raises(CanonicalizationError):
        canonical_json_bytes({1: "bad"})


def test_freeze_value_copies_nested_collections() -> None:
    original = {"items": [3, 2, 1], "set": {"b", "a"}}
    frozen = freeze_value(original)
    original["items"].append(0)  # type: ignore[union-attr]
    assert canonical_json_text(frozen) == '{"items":[3,2,1],"set":["a","b"]}'
