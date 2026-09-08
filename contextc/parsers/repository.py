"""Deterministic, non-executing repository indexing."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from contextc.canonical import normalize_text
from contextc.diagnostics import Diagnostic, DiagnosticCode, get_definition
from contextc.hashing import semantic_hash
from contextc.ir.nodes import ContextNode, NodeKind
from contextc.ir.source import InstructionAuthority, Sensitivity, SourceReference, TrustDomain
from contextc.parsers.base import IndexPolicy, IndexResult
from contextc.source_rules import SourceFactRule


class RepositoryParser:
    """Index local files with static parsing only."""

    def __init__(
        self,
        policy: IndexPolicy | None = None,
        *,
        revision: str | None = None,
        source_rules: tuple[SourceFactRule, ...] = (),
    ) -> None:
        self.policy = policy or IndexPolicy()
        self.revision = revision
        self.source_rules = tuple(source_rules)

    def parse(self, root: Path) -> IndexResult:
        root = root.resolve()
        if not root.is_dir():
            raise ValueError(f"repository path is not a directory: {root}")
        nodes: list[ContextNode] = []
        diagnostics: list[Diagnostic] = []
        candidates = self._discover(root)
        for path in candidates:
            relative = path.relative_to(root)
            if path.is_symlink():
                diagnostics.append(
                    self._diagnostic(
                        DiagnosticCode.SOURCE_SYMLINK_SKIPPED,
                        relative,
                        {"policy": "do_not_follow_symlinks"},
                    )
                )
                continue
            try:
                raw = path.read_bytes()
            except OSError as error:
                diagnostics.append(
                    self._diagnostic(
                        DiagnosticCode.SOURCE_PARSE_FAILED,
                        relative,
                        {"error_type": type(error).__name__},
                    )
                )
                continue
            if len(raw) > self.policy.max_file_bytes:
                diagnostics.append(
                    self._diagnostic(
                        DiagnosticCode.OVERSIZED_SOURCE_SKIPPED,
                        relative,
                        {"size_bytes": len(raw), "limit_bytes": self.policy.max_file_bytes},
                    )
                )
                continue
            if b"\x00" in raw:
                diagnostics.append(
                    self._diagnostic(
                        DiagnosticCode.BINARY_SOURCE_SKIPPED,
                        relative,
                        {"detector": "nul_byte"},
                    )
                )
                continue
            try:
                content = normalize_text(raw.decode("utf-8"))
            except UnicodeDecodeError as error:
                diagnostics.append(
                    self._diagnostic(
                        DiagnosticCode.SOURCE_ENCODING_UNSUPPORTED,
                        relative,
                        {"encoding": "utf-8", "error_start": error.start},
                    )
                )
                continue
            file_nodes, file_diagnostics = self._parse_text(relative, content)
            nodes.extend(file_nodes)
            diagnostics.extend(file_diagnostics)
        ordered_nodes = tuple(sorted(nodes, key=self._node_sort_key))
        ordered_diagnostics = tuple(
            sorted(
                diagnostics,
                key=lambda item: (
                    item.code.value,
                    str(item.evidence.get("source_uri", "")),
                    item.message,
                ),
            )
        )
        return IndexResult(
            root=str(root),
            nodes=ordered_nodes,
            diagnostics=ordered_diagnostics,
            files_considered=len(candidates),
        )

    def _discover(self, root: Path) -> tuple[Path, ...]:
        candidates: list[Path] = []
        for path in root.rglob("*"):
            relative = path.relative_to(root)
            if not self.policy.include_hidden and any(
                part.startswith(".") for part in relative.parts
            ):
                continue
            if path.is_file() or path.is_symlink():
                candidates.append(path)
        return tuple(sorted(candidates, key=lambda path: path.relative_to(root).as_posix()))

    def _parse_text(
        self, relative: Path, content: str
    ) -> tuple[list[ContextNode], list[Diagnostic]]:
        if relative.suffix.lower() != ".py":
            kind = (
                NodeKind.DOCUMENT
                if relative.suffix.lower() in {".md", ".rst", ".txt"}
                else NodeKind.FILE
            )
            return [self._make_node(relative, kind, content, 1, self._line_count(content))], []
        try:
            tree = ast.parse(content, filename=relative.as_posix())
        except SyntaxError as error:
            diagnostic = self._diagnostic(
                DiagnosticCode.SOURCE_PARSE_FAILED,
                relative,
                {"language": "python", "line": error.lineno, "offset": error.offset},
            )
            fallback = self._make_node(
                relative,
                NodeKind.MODULE,
                content,
                1,
                self._line_count(content),
                {"parse_status": "syntax_error_fallback"},
            )
            return [fallback], [diagnostic]
        nodes = [
            self._make_node(
                relative,
                NodeKind.MODULE,
                content,
                1,
                self._line_count(content),
                {"parse_status": "parsed"},
            )
        ]
        lines = content.splitlines(keepends=True)
        for statement in tree.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                end_line = statement.end_lineno or statement.lineno
                snippet = "".join(lines[statement.lineno - 1 : end_line])
                kind = NodeKind.CLASS if isinstance(statement, ast.ClassDef) else NodeKind.FUNCTION
                nodes.append(
                    self._make_node(
                        relative,
                        kind,
                        snippet,
                        statement.lineno,
                        end_line,
                        {"symbol": statement.name},
                    )
                )
        return nodes, []

    @staticmethod
    def _line_count(content: str) -> int:
        return max(1, len(content.splitlines()))

    @staticmethod
    def _node_sort_key(node: ContextNode) -> tuple[str, int, int, str, str]:
        return (
            node.source.uri,
            node.source.start_line or 0,
            node.source.end_line or 0,
            node.kind.value,
            node.node_id,
        )

    def _make_node(
        self,
        relative: Path,
        kind: NodeKind,
        content: str,
        start_line: int,
        end_line: int,
        metadata: dict[str, object] | None = None,
    ) -> ContextNode:
        uri = f"repo:///{relative.as_posix()}"
        source = SourceReference(
            uri=uri,
            revision=self.revision,
            start_line=start_line,
            end_line=end_line,
            language="python" if relative.suffix.lower() == ".py" else "text",
        )
        identity = semantic_hash(
            {
                "source": source,
                "kind": kind,
                "content": content,
                "node_schema_version": 2,
            }
        )
        node_id = f"node-{identity.removeprefix('sha256:')[:24]}"
        trust_domain = TrustDomain.LOCAL_REPOSITORY
        sensitivity = Sensitivity.INTERNAL
        authority = InstructionAuthority.NONE
        relative_path = relative.as_posix()
        matched_rules: list[str] = []
        for rule in self.source_rules:
            if not rule.matches(relative_path):
                continue
            matched_rules.append(rule.glob)
            if rule.trust_domain is not None:
                trust_domain = rule.trust_domain
            if rule.sensitivity is not None:
                sensitivity = rule.sensitivity
            if rule.instruction_authority is not None:
                authority = rule.instruction_authority
        final_metadata = {} if metadata is None else dict(metadata)
        if matched_rules:
            final_metadata["source_fact_rule_globs"] = tuple(matched_rules)
        return ContextNode.create(
            node_id=node_id,
            kind=kind,
            content=content,
            source=source,
            trust_domain=trust_domain,
            sensitivity=sensitivity,
            instruction_authority=authority,
            metadata=final_metadata,
        )

    @staticmethod
    def _diagnostic(
        code: DiagnosticCode, relative: Path, evidence: dict[str, object]
    ) -> Diagnostic:
        definition = get_definition(code)
        source_uri = f"repo:///{relative.as_posix()}"
        return Diagnostic(
            code=code,
            severity=definition.default_severity,
            message=f"{definition.title}: {source_uri}",
            evidence={"source_uri": source_uri, **evidence},
            owning_pass="repository_parser",
        )


def iter_source_uris(nodes: Iterable[ContextNode]) -> tuple[str, ...]:
    """Expose stable source order for tests and application services."""

    return tuple(node.source.uri for node in nodes)
