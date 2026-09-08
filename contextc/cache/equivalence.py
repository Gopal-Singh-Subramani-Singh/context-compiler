"""Semantic equivalence checks between incremental and clean compilations."""

from __future__ import annotations

from dataclasses import dataclass

from contextc.application.compile import TargetCompilation
from contextc.canonical import to_canonical_primitive
from contextc.hashing import digest_bytes, semantic_hash
from contextc.reproduction.manifest import BuildManifest


@dataclass(frozen=True, slots=True)
class EquivalenceResult:
    equivalent: bool
    differences: tuple[str, ...]


def _semantic_selection(value: object) -> object:
    primitive = to_canonical_primitive(value)
    if not isinstance(primitive, dict):
        return primitive
    # Runtime is operational evidence and may legitimately differ across cache/full paths.
    primitive = dict(primitive)
    primitive.pop("solver_runtime_ms", None)
    return primitive


def compare_compilations(
    incremental: TargetCompilation, clean: TargetCompilation
) -> EquivalenceResult:
    differences: list[str] = []
    checks = (
        (
            "source_graph",
            incremental.source_graph.semantic_identity,
            clean.source_graph.semantic_identity,
        ),
        ("secured_graph", incremental.graph.semantic_identity, clean.graph.semantic_identity),
        ("security", semantic_hash(incremental.security), semantic_hash(clean.security)),
        (
            "supersession",
            semantic_hash(incremental.supersession),
            semantic_hash(clean.supersession),
        ),
        ("analyses", semantic_hash(incremental.analyses), semantic_hash(clean.analyses)),
        (
            "selection",
            semantic_hash(_semantic_selection(incremental.selection)),
            semantic_hash(_semantic_selection(clean.selection)),
        ),
        (
            "render_order",
            semantic_hash(incremental.rendered.ordered_node_ids),
            semantic_hash(clean.rendered.ordered_node_ids),
        ),
        (
            "rendered_bytes",
            digest_bytes(incremental.rendered.rendered_bytes),
            digest_bytes(clean.rendered.rendered_bytes),
        ),
        (
            "token_count",
            str(incremental.rendered.exact_token_count),
            str(clean.rendered.exact_token_count),
        ),
    )
    for name, left, right in checks:
        if left != right:
            differences.append(f"{name}: incremental={left} clean={right}")
    return EquivalenceResult(not differences, tuple(differences))


def semantic_render_order(compilation: TargetCompilation) -> tuple[str, ...]:
    """Return the target-defined semantic selected/render order."""

    return compilation.rendered.ordered_node_ids


def compare_manifests(incremental: BuildManifest, clean: BuildManifest) -> EquivalenceResult:
    differences: list[str] = []
    left = incremental.semantic_form()
    right = clean.semantic_form()
    if left != right:
        left_keys = set(left)
        right_keys = set(right)
        for key in sorted(left_keys | right_keys):
            if left.get(key) != right.get(key):
                differences.append(f"manifest.{key} differs")
    return EquivalenceResult(not differences, tuple(differences))


def combine_equivalence(*results: EquivalenceResult) -> EquivalenceResult:
    differences = tuple(diff for result in results for diff in result.differences)
    return EquivalenceResult(not differences, differences)
