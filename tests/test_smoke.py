from pathlib import Path

from contextc.application import compile_repository

FIXTURE = Path(__file__).parent / "fixtures" / "index_repo"


def test_generic_smoke_pipeline_is_deterministic_and_separated() -> None:
    first = compile_repository(FIXTURE, task="static repository indexing")
    second = compile_repository(FIXTURE, task="static repository indexing")
    assert first.compiled == second.compiled
    assert first.compiled.rendered_text.startswith("<<<CONTEXT")
    assert first.compiled.selection.selected_node_ids == tuple(
        node.node_id for node in first.index.nodes
    )
    assert (
        tuple(item.node_id for item in first.analyses) == first.compiled.selection.selected_node_ids
    )
