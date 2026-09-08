from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from contextc.application.compile import (
    CompileRepositoryRequest,
    compile_repository_to_path,
)
from contextc.diagnostics import DiagnosticCode
from contextc.errors import FinalBudgetOverflowError, TargetLoweringError
from contextc.hashing import semantic_hash
from contextc.ir import (
    CompilationUnit,
    ContextEdge,
    ContextGraph,
    ContextNode,
    EdgeType,
    NodeKind,
    SelectionResult,
    SourceReference,
)
from contextc.targets import (
    TargetId,
    TargetManifestFields,
    TargetRenderRequest,
    lower_generic,
    lower_llama,
    lower_qwen,
    write_rendered_context,
)
from contextc.tokenizers import ChatMessage, GenericTokenizer, TokenizerIdentity


class FakeChatTokenizer:
    def __init__(self, target: TargetId) -> None:
        self._identity = TokenizerIdentity(
            target_id=target.value,
            tokenizer_id=f"fake:{target.value}:chars",
            tokenizer_version="1.0.0",
            tokenizer_revision="test-revision",
            configuration={"unit": "utf8-byte", "template": target.value},
        )
        self.target = target

    @property
    def identity(self) -> TokenizerIdentity:
        return self._identity

    def encode(self, text: str) -> tuple[int, ...]:
        return tuple(text.encode())

    def count(self, text: str) -> int:
        return len(self.encode(text))

    def apply_chat_template(
        self,
        messages: Sequence[ChatMessage],
        *,
        add_generation_prompt: bool,
    ) -> str:
        text = "".join(
            f"<{self.target.value}:{message.role.value}>{message.content}"
            f"</{self.target.value}:{message.role.value}>"
            for message in messages
        )
        if add_generation_prompt:
            text += f"<{self.target.value}:assistant>"
        return text


def make_node(node_id: str, content: str, *, transformed: bool = False) -> ContextNode:
    return ContextNode.create(
        node_id=node_id,
        kind=NodeKind.FILE,
        content=content,
        source=SourceReference(
            uri=f"repo:///{node_id}.txt",
            start_line=2,
            end_line=3,
        ),
        transformations=("normalize:newlines",) if transformed else (),
    )


def make_graph(*nodes: ContextNode) -> ContextGraph:
    graph = ContextGraph()
    for node in nodes:
        graph.add_node(node)
    return graph


def compilation(*, target: TargetId, tokenizer_id: str, budget: int) -> CompilationUnit:
    return CompilationUnit(
        task_id="task-m3",
        task_description="Explain exact targets",
        target_id=target.value,
        tokenizer_id=tokenizer_id,
        token_budget=budget,
        policy_id="policy:test",
        time_anchor=datetime(2026, 8, 29, tzinfo=UTC),
        random_seed=0,
        compiler_version="0.3.0",
        pipeline_config_hash=semantic_hash({"pipeline": "m3"}),
    )


def request_for(
    graph: ContextGraph,
    selection: SelectionResult,
    *,
    target: TargetId = TargetId.GENERIC,
    tokenizer_id: str = "generic:regex-v1",
    budget: int = 10_000,
) -> TargetRenderRequest:
    return TargetRenderRequest(
        graph=graph,
        selection=selection,
        compilation=compilation(target=target, tokenizer_id=tokenizer_id, budget=budget),
        system_instruction="System policy",
        developer_instruction="Developer instruction",
        user_instruction="User task",
        policy_instruction="Policy evidence",
        tool_schema_text='{"tool":"lookup"}',
    )


def test_generic_final_recount_source_map_and_manifest_fields() -> None:
    tokenizer = GenericTokenizer()
    graph = make_graph(make_node("a", "alpha beta", transformed=True), make_node("b", "gamma"))
    rendered = lower_generic(request_for(graph, SelectionResult(("a", "b"))), tokenizer=tokenizer)
    assert rendered.exact_token_count == tokenizer.count(rendered.rendered_text)
    assert rendered.exact_token_count <= rendered.budget_evidence.configured_budget
    assert rendered.ordered_node_ids == ("a", "b")
    assert rendered.source_map[0].output_start_char == 0
    assert rendered.source_map[-1].output_end_char == len(rendered.rendered_text)
    assert any(entry.compiler_generated for entry in rendered.source_map)
    source_entries = [entry for entry in rendered.source_map if not entry.compiler_generated]
    assert [entry.node_id for entry in source_entries] == ["a", "b"]
    assert source_entries[0].source_uri == "repo:///a.txt"
    assert source_entries[0].transformations == ("normalize:newlines",)
    manifest = TargetManifestFields.from_rendered(rendered)
    assert manifest.exact_final_token_count == rendered.exact_token_count
    assert manifest.source_allowance_tokens == rendered.budget_evidence.source_allowance_tokens
    assert manifest.pre_render_selected_tokens == rendered.exact_token_count
    assert manifest.trim_iterations == 0
    assert manifest.tokenizer_configuration_identity.startswith("sha256:")


@pytest.mark.parametrize(
    ("target", "lowerer"),
    [(TargetId.QWEN, lower_qwen), (TargetId.LLAMA, lower_llama)],
)
def test_model_targets_include_full_fake_chat_template_and_exact_count(
    target: TargetId,
    lowerer: object,
) -> None:
    tokenizer = FakeChatTokenizer(target)
    graph = make_graph(make_node("a", "model context"))
    request = request_for(
        graph,
        SelectionResult(("a",)),
        target=target,
        tokenizer_id=tokenizer.identity.tokenizer_id,
    )
    rendered = lowerer(request, tokenizer=tokenizer)  # type: ignore[operator]
    assert f"<{target.value}:system>" in rendered.rendered_text
    assert f"<{target.value}:assistant>" in rendered.rendered_text
    assert "Developer instruction:\nDeveloper instruction" in rendered.rendered_text
    assert "Policy instruction:\nPolicy evidence" in rendered.rendered_text
    assert 'Tool schema:\n{"tool":"lookup"}' in rendered.rendered_text
    assert rendered.exact_token_count == len(rendered.rendered_bytes)


def test_exact_boundary_succeeds_and_one_token_overflow_trims() -> None:
    tokenizer = GenericTokenizer()
    graph = make_graph(make_node("a", "alpha"), make_node("b", "beta"))
    initial_request = request_for(graph, SelectionResult(("a", "b")))
    initial = lower_generic(initial_request, tokenizer=tokenizer)
    exact_request = replace(
        initial_request,
        compilation=replace(
            initial_request.compilation,
            token_budget=initial.exact_token_count,
        ),
    )
    boundary = lower_generic(exact_request, tokenizer=tokenizer)
    assert boundary.exact_token_count == initial.exact_token_count
    assert not boundary.trim_evidence

    overflow_request = replace(
        exact_request,
        compilation=replace(
            exact_request.compilation,
            token_budget=initial.exact_token_count - 1,
        ),
    )
    trimmed = lower_generic(overflow_request, tokenizer=tokenizer)
    assert trimmed.exact_token_count <= initial.exact_token_count - 1
    assert trimmed.ordered_node_ids == ("a",)
    assert trimmed.trim_evidence[0].removed_node_ids == ("b",)
    assert DiagnosticCode.EXCLUDED_BY_TOKEN_BUDGET in {
        diagnostic.code for diagnostic in trimmed.diagnostics
    }


def test_dependency_cluster_is_trimmed_together_and_closure_preserved() -> None:
    tokenizer = GenericTokenizer()
    graph = make_graph(
        make_node("a", "dependent"),
        make_node("b", "dependency"),
        make_node("keep", "mandatory"),
    )
    graph.add_edge(ContextEdge("a", "b", EdgeType.REQUIRES))
    selection = SelectionResult(
        selected_node_ids=("keep", "a", "b"),
        mandatory_node_ids=("keep",),
    )
    roomy = lower_generic(request_for(graph, selection), tokenizer=tokenizer)
    keep_only = lower_generic(
        request_for(
            graph,
            SelectionResult(("keep",), mandatory_node_ids=("keep",)),
        ),
        tokenizer=tokenizer,
    )
    request = request_for(graph, selection, budget=keep_only.exact_token_count)
    result = lower_generic(request, tokenizer=tokenizer)
    assert roomy.exact_token_count > result.exact_token_count
    assert result.ordered_node_ids == ("keep",)
    assert result.trim_evidence[0].removed_node_ids == ("a", "b")
    assert set(graph.dependency_closure(result.ordered_node_ids).node_ids) == set(
        result.ordered_node_ids
    )


def test_mandatory_closure_overflow_is_typed_and_has_no_partial_write(tmp_path: Path) -> None:
    tokenizer = GenericTokenizer()
    graph = make_graph(make_node("mandatory", "content that cannot fit"))
    request = request_for(
        graph,
        SelectionResult(("mandatory",), mandatory_node_ids=("mandatory",)),
        budget=1,
    )
    output = tmp_path / "context.txt"
    output.write_text("previous complete artifact")
    with pytest.raises(FinalBudgetOverflowError) as captured:
        lower_generic(request, tokenizer=tokenizer)
    assert captured.value.diagnostic_code == "CTX510"
    assert "mandatory dependency closure" in captured.value.reason
    assert output.read_text() == "previous complete artifact"


def test_repeated_render_is_byte_identical_and_blocked_nodes_are_rejected() -> None:
    tokenizer = GenericTokenizer()
    graph = make_graph(make_node("b", "second"), make_node("a", "first"))
    request = request_for(graph, SelectionResult(("a", "b")))
    first = lower_generic(request, tokenizer=tokenizer)
    repeated = lower_generic(request, tokenizer=tokenizer)
    assert first == repeated
    assert first.rendered_bytes == repeated.rendered_bytes
    with pytest.raises(TargetLoweringError, match="blocked"):
        lower_generic(replace(request, blocked_node_ids=("a",)), tokenizer=tokenizer)


def test_graph_insertion_order_does_not_change_explicit_render_order() -> None:
    tokenizer = GenericTokenizer()
    a = make_node("a", "first")
    b = make_node("b", "second")
    left = make_graph(a, b)
    right = make_graph(b, a)
    selection = SelectionResult(("b", "a"))
    assert (
        lower_generic(request_for(left, selection), tokenizer=tokenizer).rendered_bytes
        == lower_generic(request_for(right, selection), tokenizer=tokenizer).rendered_bytes
    )


@pytest.mark.parametrize("node_count", range(1, 6))
@pytest.mark.parametrize("budget", (25, 50, 100, 200))
def test_small_graph_success_always_recounts_with_same_tokenizer_within_budget(
    node_count: int, budget: int
) -> None:
    tokenizer = GenericTokenizer()
    graph = make_graph(
        *(make_node(f"n{index}", "token " * (index + 1)) for index in range(node_count))
    )
    request = request_for(
        graph,
        SelectionResult(tuple(f"n{index}" for index in range(node_count))),
        budget=budget,
    )
    try:
        rendered = lower_generic(request, tokenizer=tokenizer)
    except FinalBudgetOverflowError:
        return
    assert tokenizer.count(rendered.rendered_text) == rendered.exact_token_count
    assert rendered.exact_token_count <= budget


def test_atomic_write_replaces_only_with_complete_render(tmp_path: Path) -> None:
    tokenizer = GenericTokenizer()
    graph = make_graph(make_node("a", "complete"))
    rendered = lower_generic(request_for(graph, SelectionResult(("a",))), tokenizer=tokenizer)
    output = tmp_path / "nested" / "context.txt"
    assert write_rendered_context(output, rendered) == output.resolve()
    assert output.read_bytes() == rendered.rendered_bytes
    assert not tuple(output.parent.glob(".*.tmp"))


def test_application_lowerer_failure_does_not_overwrite_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import contextc.application.compile as application

    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text("value = 1\n")
    output = tmp_path / "context.txt"
    output.write_text("previous artifact")

    def fail_lowering(*args: object, **kwargs: object) -> object:
        raise TargetLoweringError("simulated lowerer failure")

    monkeypatch.setattr(application, "lower_generic", fail_lowering)
    request = CompileRepositoryRequest(
        repository=repository,
        task="explain app",
        target_id=TargetId.GENERIC,
        token_budget=200,
        time_anchor=datetime(2026, 8, 29, tzinfo=UTC),
    )
    with pytest.raises(TargetLoweringError, match="simulated"):
        compile_repository_to_path(request, output)
    assert output.read_text() == "previous artifact"
