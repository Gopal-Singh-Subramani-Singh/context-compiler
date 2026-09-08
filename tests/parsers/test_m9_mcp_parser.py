from __future__ import annotations

import pytest

from contextc.ir import EdgeType, InstructionAuthority, TrustDomain
from contextc.parsers.mcp import StaticMcpParser


def test_mcp_parser_retains_static_metadata_and_edges() -> None:
    result = StaticMcpParser().parse_mapping(
        {
            "server": "alpha",
            "tool": "read",
            "result_id": "42",
            "content": [
                {"node_id": "a", "text": "payload"},
                {
                    "node_id": "b",
                    "text": "sink",
                    "security_sink": "instruction",
                    "trust_domain": "verified_tool",
                },
            ],
            "edges": [{"source": "a", "target": "b", "type": "enables"}],
        }
    )
    assert result.nodes[0].trust_domain is TrustDomain.UNVERIFIED_TOOL
    assert all(node.instruction_authority is InstructionAuthority.NONE for node in result.nodes)
    assert result.edges[0].edge_type is EdgeType.ENABLES


def test_mcp_parser_rejects_non_flow_edges() -> None:
    with pytest.raises(ValueError, match="TAINTS or ENABLES"):
        StaticMcpParser().parse_mapping(
            {
                "server": "s",
                "tool": "t",
                "result_id": "r",
                "content": [
                    {"node_id": "a", "text": "a"},
                    {"node_id": "b", "text": "b"},
                ],
                "edges": [{"source": "a", "target": "b", "type": "requires"}],
            }
        )
