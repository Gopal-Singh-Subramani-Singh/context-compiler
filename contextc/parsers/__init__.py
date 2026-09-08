"""Static source parser contracts."""

from contextc.parsers.base import IndexPolicy, IndexResult, SourceParser
from contextc.parsers.repository import RepositoryParser

__all__ = [
    "IndexPolicy",
    "IndexResult",
    "RepositoryParser",
    "SourceParser",
    "StaticMcpParser",
    "StaticMcpResult",
]

from contextc.parsers.mcp import StaticMcpParser, StaticMcpResult
