"""M15 cross-domain source-neutral compilation primitives."""

from contextc.cross_domain.adapters import (
    AdaptedContext,
    RepositoryAdapter,
    SourceAdapter,
    load_source_context,
)
from contextc.cross_domain.conflicts import ConflictResult, analyze_conflicts
from contextc.cross_domain.supersession import (
    SupersessionPolicy,
    SupersessionResult,
    analyze_supersession,
)

__all__ = [
    "AdaptedContext",
    "ConflictResult",
    "RepositoryAdapter",
    "SourceAdapter",
    "SupersessionPolicy",
    "SupersessionResult",
    "analyze_conflicts",
    "analyze_supersession",
    "load_source_context",
]
