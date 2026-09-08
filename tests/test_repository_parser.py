from pathlib import Path

import pytest

from contextc.diagnostics import DiagnosticCode
from contextc.ir import NodeKind
from contextc.parsers import IndexPolicy, RepositoryParser

FIXTURE = Path(__file__).parent / "fixtures" / "index_repo"


def test_parser_preserves_spans_without_importing_modules() -> None:
    result = RepositoryParser().parse(FIXTURE)
    function = next(node for node in result.nodes if node.kind is NodeKind.FUNCTION)
    assert function.source.uri.endswith("explodes_if_imported.py")
    assert function.source.start_line == 4
    assert function.source.end_line == 5
    assert function.metadata["symbol"] == "useful_function"


def test_index_order_is_independent_of_file_creation_order(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "b.txt").write_text("b")
    (left / "a.txt").write_text("a")
    (right / "a.txt").write_text("a")
    (right / "b.txt").write_text("b")
    parser = RepositoryParser()
    left_result = parser.parse(left)
    right_result = parser.parse(right)
    assert [node.source.uri for node in left_result.nodes] == [
        node.source.uri for node in right_result.nodes
    ]
    assert [node.node_id for node in left_result.nodes] == [
        node.node_id for node in right_result.nodes
    ]


def test_binary_oversized_encoding_and_syntax_policies_are_explicit(tmp_path: Path) -> None:
    (tmp_path / "binary.bin").write_bytes(b"a\x00b")
    (tmp_path / "large.txt").write_text("x" * 20)
    (tmp_path / "latin.txt").write_bytes(b"\xff")
    (tmp_path / "broken.py").write_text("def broken(:\n")
    result = RepositoryParser(IndexPolicy(max_file_bytes=15)).parse(tmp_path)
    codes = {item.code for item in result.diagnostics}
    assert DiagnosticCode.BINARY_SOURCE_SKIPPED in codes
    assert DiagnosticCode.OVERSIZED_SOURCE_SKIPPED in codes
    assert DiagnosticCode.SOURCE_ENCODING_UNSUPPORTED in codes
    assert DiagnosticCode.SOURCE_PARSE_FAILED in codes
    assert any(
        node.metadata.get("parse_status") == "syntax_error_fallback" for node in result.nodes
    )


def test_hidden_files_are_configurable(tmp_path: Path) -> None:
    (tmp_path / ".hidden.txt").write_text("hidden")
    assert RepositoryParser().parse(tmp_path).files_considered == 0
    assert RepositoryParser(IndexPolicy(include_hidden=True)).parse(tmp_path).files_considered == 1


def test_non_directory_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_text("x")
    with pytest.raises(ValueError):
        RepositoryParser().parse(path)


def test_symlinks_are_not_followed(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("target")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    result = RepositoryParser().parse(tmp_path)
    assert DiagnosticCode.SOURCE_SYMLINK_SKIPPED in {item.code for item in result.diagnostics}


def test_repository_source_fact_rules_apply_to_real_paths(tmp_path: Path) -> None:
    from contextc.config import load_project_config
    from contextc.ir import InstructionAuthority, Sensitivity, TrustDomain

    (tmp_path / "external").mkdir()
    (tmp_path / "private").mkdir()
    (tmp_path / "external" / "note.md").write_text("vendor note")
    (tmp_path / "private" / "secret.txt").write_text("canary")
    config_path = tmp_path / "contextc.toml"
    config_path.write_text(
        """
[contextc]

[[contextc.source_rules]]
glob = "external/**"
trust_domain = "external_content"

[[contextc.source_rules]]
glob = "private/**"
sensitivity = "secret"

[[contextc.source_rules]]
glob = "private/secret.txt"
instruction_authority = "none"
""".strip()
        + "\n"
    )
    config = load_project_config(config_path)
    result = RepositoryParser(source_rules=config.source_rules).parse(tmp_path)
    external = next(node for node in result.nodes if node.source.uri.endswith("external/note.md"))
    secret = next(node for node in result.nodes if node.source.uri.endswith("private/secret.txt"))
    assert external.trust_domain is TrustDomain.EXTERNAL_CONTENT
    assert secret.sensitivity is Sensitivity.SECRET
    assert secret.instruction_authority is InstructionAuthority.NONE
    assert secret.metadata["source_fact_rule_globs"] == (
        "private/**",
        "private/secret.txt",
    )
