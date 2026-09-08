"""Optional integration discovery that never imports heavy packages at startup."""

from __future__ import annotations

from importlib.util import find_spec

from contextc.errors import OptionalDependencyError

OPTIONAL_MODULES: dict[str, tuple[str, str]] = {
    "tokenizers": ("tokenizers", "tokenizers"),
    "qwen": ("transformers", "qwen"),
    "llama": ("transformers", "llama"),
    "embeddings": ("sentence_transformers", "embeddings"),
    "ilp": ("pulp", "ilp"),
    "live-mcp": ("mcp", "live-mcp"),
    "ui": ("streamlit", "ui"),
}


def optional_dependency_available(module: str) -> bool:
    """Check module availability without importing it."""

    return find_spec(module) is not None


def require_optional(*, feature: str, module: str, extra: str) -> None:
    """Fail explicitly when a requested optional feature is missing."""

    if not optional_dependency_available(module):
        raise OptionalDependencyError(feature=feature, module=module, extra=extra)
