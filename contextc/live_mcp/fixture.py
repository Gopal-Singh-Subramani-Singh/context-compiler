"""Fixture-server allowlist checks for M10b CLI execution."""

from __future__ import annotations

from pathlib import Path

from contextc.live_mcp.errors import MCPConnectionError

MARKER = "CONTEXTC_TINY_MCP_FIXTURE = True"


def validate_fixture_server(path: Path) -> Path:
    resolved = path.resolve(strict=True)
    text = resolved.read_text(encoding="utf-8")
    if MARKER not in text:
        raise MCPConnectionError(
            "M10b live execution is restricted to a marked bounded fixture server"
        )
    return resolved
