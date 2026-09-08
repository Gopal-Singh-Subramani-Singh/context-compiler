"""Application-facing M9 SecurityService."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from contextc.ir import ContextGraph
from contextc.parsers.mcp import StaticMcpParser
from contextc.security.analysis import analyze_security
from contextc.security.models import SecurityPolicy, SecurityResult
from contextc.security.policy import load_policy


@dataclass(frozen=True, slots=True)
class SecurityService:
    policy: SecurityPolicy

    @classmethod
    def from_policy_path(cls, path: Path | None = None) -> SecurityService:
        return cls(load_policy(path))

    def scan_graph(self, graph: ContextGraph) -> SecurityResult:
        return analyze_security(graph, self.policy)

    def scan_mcp_file(self, path: Path) -> SecurityResult:
        parsed = StaticMcpParser().parse_file(path)
        graph = ContextGraph()
        for node in parsed.nodes:
            graph.add_node(node)
        for edge in parsed.edges:
            graph.add_edge(edge)
        return self.scan_graph(graph)
