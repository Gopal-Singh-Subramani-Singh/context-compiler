"""The authoritative diagnostic registry."""

from __future__ import annotations

from contextc.diagnostics.codes import DiagnosticCode
from contextc.diagnostics.models import DiagnosticDefinition, Severity


def _definition(
    code: DiagnosticCode,
    title: str,
    description: str,
    severity: Severity,
    owner: str,
    may_continue: bool = True,
) -> DiagnosticDefinition:
    return DiagnosticDefinition(code, title, description, severity, owner, may_continue)


_DEFINITIONS = (
    _definition(
        DiagnosticCode.BINARY_SOURCE_SKIPPED,
        "Binary source skipped",
        "A binary source was excluded by indexing policy.",
        Severity.INFO,
        "repository_parser",
    ),
    _definition(
        DiagnosticCode.OVERSIZED_SOURCE_SKIPPED,
        "Oversized source skipped",
        "A source exceeded the configured byte limit.",
        Severity.WARNING,
        "repository_parser",
    ),
    _definition(
        DiagnosticCode.SOURCE_PARSE_FAILED,
        "Source parse failed",
        "Structured parsing failed and deterministic fallback handling was used.",
        Severity.WARNING,
        "repository_parser",
    ),
    _definition(
        DiagnosticCode.SOURCE_ENCODING_UNSUPPORTED,
        "Unsupported source encoding",
        "A text source was not valid UTF-8.",
        Severity.WARNING,
        "repository_parser",
    ),
    _definition(
        DiagnosticCode.SOURCE_SYMLINK_SKIPPED,
        "Source symlink skipped",
        "A symlink was excluded to keep indexing inside the repository.",
        Severity.INFO,
        "repository_parser",
    ),
    _definition(
        DiagnosticCode.EXACT_DUPLICATE,
        "Exact duplicate",
        "Two nodes have identical normalized content.",
        Severity.INFO,
        "duplicate_analysis",
    ),
    _definition(
        DiagnosticCode.SEMANTIC_DUPLICATE_CANDIDATE,
        "Semantic duplicate candidate",
        "Two nodes may express equivalent content.",
        Severity.INFO,
        "duplicate_analysis",
    ),
    _definition(
        DiagnosticCode.OVERLAPPING_SOURCE_SPAN,
        "Overlapping source span",
        "Two nodes overlap in one source.",
        Severity.INFO,
        "span_analysis",
    ),
    _definition(
        DiagnosticCode.INSTRUCTION_CONFLICT,
        "Instruction conflict",
        "Instructions conflict under the active analysis.",
        Severity.WARNING,
        "conflict_analysis",
    ),
    _definition(
        DiagnosticCode.STALE_OR_SUPERSEDED,
        "Stale or superseded source",
        "A newer source supersedes this node.",
        Severity.INFO,
        "supersession_analysis",
    ),
    _definition(
        DiagnosticCode.MISSING_DEPENDENCY,
        "Missing dependency",
        "A required graph dependency is absent.",
        Severity.ERROR,
        "dependency_analysis",
        False,
    ),
    _definition(
        DiagnosticCode.DEPENDENCY_FORCED_INCLUSION,
        "Dependency-forced inclusion",
        "A node was included to satisfy dependency closure.",
        Severity.INFO,
        "dependency_analysis",
    ),
    _definition(
        DiagnosticCode.DEPENDENCY_CYCLE,
        "Dependency cycle",
        "Dependency traversal encountered a cycle.",
        Severity.WARNING,
        "dependency_analysis",
    ),
    _definition(
        DiagnosticCode.INJECTION_RISK_SIGNAL,
        "Injection-risk signal",
        "Untrusted content contains an instruction-like risk signal.",
        Severity.WARNING,
        "security_analysis",
    ),
    _definition(
        DiagnosticCode.SENSITIVITY_POLICY_VIOLATION,
        "Sensitivity-policy violation",
        "Content violates the active sensitivity policy.",
        Severity.ERROR,
        "security_policy",
        False,
    ),
    _definition(
        DiagnosticCode.UNTRUSTED_INSTRUCTION_SCOPE,
        "Untrusted content in instruction scope",
        "Untrusted content entered an instruction-bearing scope.",
        Severity.ERROR,
        "taint_analysis",
        False,
    ),
    _definition(
        DiagnosticCode.TRUST_AUTHORITY_OVERRIDE,
        "Trust or authority override",
        "A policy override changed trust or instruction authority handling.",
        Severity.WARNING,
        "security_policy",
    ),
    _definition(
        DiagnosticCode.SENSITIVE_EXTERNAL_FLOW,
        "Sensitive external flow",
        "Sensitive or secret content can flow externally.",
        Severity.ERROR,
        "taint_analysis",
        False,
    ),
    _definition(
        DiagnosticCode.DANGEROUS_CAPABILITY_COMPOSITION,
        "Dangerous capability composition",
        "Static capability composition enables a dangerous chain.",
        Severity.ERROR,
        "capability_analysis",
        False,
    ),
    _definition(
        DiagnosticCode.INCOMPLETE_CAPABILITY_DECLARATIONS,
        "Incomplete capability declarations",
        "Capability declarations lack required evidence.",
        Severity.WARNING,
        "capability_analysis",
    ),
    _definition(
        DiagnosticCode.INVALID_CAPABILITY_PLAN,
        "Invalid capability plan",
        "A static capability plan is structurally invalid.",
        Severity.ERROR,
        "capability_analysis",
        False,
    ),
    _definition(
        DiagnosticCode.EXPLICIT_APPROVAL_REQUIRED,
        "Explicit approval required",
        "Policy requires explicit approval before this capability plan.",
        Severity.WARNING,
        "capability_policy",
        False,
    ),
    _definition(
        DiagnosticCode.CAPABILITY_POLICY_EVIDENCE_FAILURE,
        "Capability policy or evidence failure",
        "Capability evidence does not satisfy policy.",
        Severity.ERROR,
        "capability_policy",
        False,
    ),
    _definition(
        DiagnosticCode.MCP_DECLARATION_MISMATCH,
        "Observed MCP declaration mismatch",
        "Observed bounded MCP behavior differs from the live declaration snapshot.",
        Severity.ERROR,
        "live_mcp_correspondence",
        False,
    ),
    _definition(
        DiagnosticCode.EXCLUDED_BY_TOKEN_BUDGET,
        "Excluded by token budget",
        "A node was excluded to satisfy the target budget.",
        Severity.INFO,
        "optimizer",
    ),
    _definition(
        DiagnosticCode.FINAL_TOKEN_BUDGET_OVERFLOW,
        "Final target token-budget overflow",
        "Exact rendered target tokens exceed the configured budget.",
        Severity.ERROR,
        "target_validation",
        False,
    ),
    _definition(
        DiagnosticCode.OPTIMIZER_FALLBACK,
        "Optimizer fallback",
        "The requested optimizer fell back with recorded status.",
        Severity.WARNING,
        "optimizer",
    ),
    _definition(
        DiagnosticCode.OPTIMIZER_INFEASIBLE,
        "Optimizer constraints are infeasible",
        "Mandatory dependency closure cannot satisfy allowance or policy constraints.",
        Severity.ERROR,
        "optimizer",
        False,
    ),
    _definition(
        DiagnosticCode.MANIFEST_SOURCE_MISMATCH,
        "Manifest or source mismatch",
        "Current source identity differs from the manifest.",
        Severity.ERROR,
        "reproduction",
        False,
    ),
    _definition(
        DiagnosticCode.REPRODUCTION_ARTIFACT_MISMATCH,
        "Reproduction artifact mismatch",
        "Rebuilt artifact evidence differs from the stored artifact.",
        Severity.ERROR,
        "reproduction",
        False,
    ),
    _definition(
        DiagnosticCode.CACHE_ENTRY_CORRUPT,
        "Cache entry corrupt",
        "A cache metadata/object pair failed integrity validation and cannot be reused.",
        Severity.WARNING,
        "cache",
    ),
    _definition(
        DiagnosticCode.CACHE_SCHEMA_INCOMPATIBLE,
        "Cache schema incompatible",
        "A cache entry uses a schema version that this build will not reuse.",
        Severity.WARNING,
        "cache",
    ),
    _definition(
        DiagnosticCode.CACHE_INVALIDATED,
        "Cache entry invalidated",
        "A cache entry was invalidated through a dependency-aware plan.",
        Severity.INFO,
        "cache",
    ),
    _definition(
        DiagnosticCode.CACHE_RECOMPUTED,
        "Cache stage recomputed",
        "A semantic stage was recomputed after a miss or invalid entry.",
        Severity.INFO,
        "incremental",
    ),
    _definition(
        DiagnosticCode.INCREMENTAL_FULL_MISMATCH,
        "Incremental/full semantic mismatch",
        "Incremental output differs from a clean build.",
        Severity.ERROR,
        "incremental",
        False,
    ),
    _definition(
        DiagnosticCode.OPTIONAL_DEPENDENCY_UNAVAILABLE,
        "Optional dependency unavailable",
        "A requested optional integration is not installed.",
        Severity.ERROR,
        "startup",
        False,
    ),
    _definition(
        DiagnosticCode.UNSUPPORTED_SCHEMA_VERSION,
        "Unsupported schema version",
        "Input uses a schema version unsupported by this build.",
        Severity.ERROR,
        "serialization",
        False,
    ),
)

REGISTRY: dict[DiagnosticCode, DiagnosticDefinition] = {item.code: item for item in _DEFINITIONS}

if len(REGISTRY) != len(DiagnosticCode):
    raise RuntimeError("diagnostic registry is incomplete or contains duplicate codes")


def get_definition(code: DiagnosticCode) -> DiagnosticDefinition:
    """Look up a stable diagnostic definition."""

    return REGISTRY[code]
