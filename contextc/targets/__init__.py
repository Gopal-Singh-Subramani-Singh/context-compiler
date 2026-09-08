"""Exact-budget target lowerers and typed rendered output evidence."""

from contextc.targets.generic import lower_generic, render_generic
from contextc.targets.io import write_rendered_context
from contextc.targets.llama import lower_llama
from contextc.targets.qwen import lower_qwen
from contextc.targets.structured_json import lower_structured_json, render_structured_record
from contextc.targets.types import (
    RenderedContext,
    SourceMapEntry,
    TargetId,
    TargetManifestFields,
    TargetRenderRequest,
    TokenBudgetEvidence,
    TrimEvidence,
)

__all__ = [
    "RenderedContext",
    "SourceMapEntry",
    "TargetId",
    "TargetManifestFields",
    "TargetRenderRequest",
    "TokenBudgetEvidence",
    "TrimEvidence",
    "lower_generic",
    "lower_llama",
    "lower_qwen",
    "lower_structured_json",
    "render_generic",
    "render_structured_record",
    "write_rendered_context",
]
