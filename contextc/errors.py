"""Typed errors shared by the core package."""


class ContextCompilerError(Exception):
    """Base class for expected Context Compiler failures."""


class ConfigurationError(ContextCompilerError):
    """Raised when configuration cannot be parsed or validated."""


class CanonicalizationError(ContextCompilerError):
    """Raised when a value has no stable semantic representation."""


class SourceValidationError(ContextCompilerError):
    """Raised when immutable source facts are invalid."""


class SchemaVersionError(ContextCompilerError):
    """Raised when a semantic artifact uses an unsupported schema version."""

    diagnostic_code = "CTX720"

    def __str__(self) -> str:
        detail = super().__str__()
        return detail if detail.startswith("CTX720") else f"CTX720 {detail}"


class GraphInvariantError(ContextCompilerError):
    """Raised when a graph mutation would violate a typed graph invariant."""


class DependencyCycleError(GraphInvariantError):
    """Raised when an acyclic dependency order is requested for a cyclic graph."""

    diagnostic_code = "CTX320"

    def __init__(self, cycles: tuple[tuple[str, ...], ...]) -> None:
        self.cycles = cycles
        evidence = "; ".join(" -> ".join(cycle) for cycle in cycles)
        super().__init__(f"dependency cycles prevent topological ordering: {evidence}")


class OptionalDependencyError(ContextCompilerError):
    """Raised when an explicitly requested optional feature is unavailable."""

    def __init__(self, *, feature: str, module: str, extra: str) -> None:
        self.feature = feature
        self.module = module
        self.extra = extra
        super().__init__(
            f"{feature} requires optional module {module!r}; "
            f"install Context Compiler with the {extra!r} extra"
        )


class TokenizerUnavailableError(ContextCompilerError):
    """Raised when an explicitly requested exact tokenizer cannot be loaded."""

    diagnostic_code = "CTX710"

    def __init__(
        self,
        *,
        target_id: str,
        tokenizer_id: str,
        installation_guidance: str,
        original_cause: BaseException,
    ) -> None:
        self.target_id = target_id
        self.tokenizer_id = tokenizer_id
        self.installation_guidance = installation_guidance
        self.original_cause = original_cause
        super().__init__(
            f"CTX710 {target_id} tokenizer {tokenizer_id!r} is unavailable: "
            f"{original_cause}. {installation_guidance}"
        )


class TargetLoweringError(ContextCompilerError):
    """Raised when a target cannot be rendered with its exact contract."""


class FinalBudgetOverflowError(TargetLoweringError):
    """Raised when mandatory dependency closure cannot fit the final budget."""

    diagnostic_code = "CTX510"

    def __init__(
        self,
        *,
        target_id: str,
        token_budget: int,
        final_token_count: int,
        reason: str,
    ) -> None:
        self.target_id = target_id
        self.token_budget = token_budget
        self.final_token_count = final_token_count
        self.reason = reason
        super().__init__(
            f"CTX510 {target_id} final target uses {final_token_count} tokens, "
            f"exceeding budget {token_budget}: {reason}"
        )


class OptimizerInfeasibleError(ContextCompilerError):
    """Raised when mandatory optimizer constraints admit no valid selection."""

    diagnostic_code = "CTX530"

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"CTX530 optimizer constraints are infeasible: {reason}")


class SecurityPolicyBlockedError(ContextCompilerError):
    """Raised before artifact creation when M9 policy blocks compilation."""

    def __init__(self, *, blocked_node_ids: tuple[str, ...], rule_ids: tuple[str, ...]) -> None:
        self.blocked_node_ids = blocked_node_ids
        self.rule_ids = rule_ids
        nodes = ", ".join(blocked_node_ids) or "unknown"
        rules = ", ".join(rule_ids) or "unknown"
        super().__init__(f"security policy blocked compilation; nodes=[{nodes}], rules=[{rules}]")


class ManifestSourceMismatchError(ContextCompilerError):
    """Raised when supplied source evidence differs from a build manifest."""

    diagnostic_code = "CTX600"

    def __init__(self, differences: tuple[str, ...]) -> None:
        self.differences = differences
        super().__init__(f"CTX600 manifest/source mismatch: {'; '.join(differences)}")


class ReproductionMismatchError(ContextCompilerError):
    """Raised when artifact, manifest, or rebuild evidence does not agree."""

    diagnostic_code = "CTX610"

    def __init__(self, differences: tuple[str, ...]) -> None:
        self.differences = differences
        super().__init__(f"CTX610 reproduction mismatch: {'; '.join(differences)}")


class ArtifactTransactionError(ContextCompilerError):
    """Raised when an artifact/manifest transaction cannot be committed."""

    diagnostic_code = "CTX610"

    def __init__(self, stage: str, original_cause: BaseException) -> None:
        self.stage = stage
        self.original_cause = original_cause
        super().__init__(f"CTX610 artifact transaction failed during {stage}: {original_cause}")


class RebuildCompatibilityError(ContextCompilerError):
    """Raised before rebuild when recorded compiler semantics are unavailable."""

    diagnostic_code = "CTX720"

    def __init__(self, differences: tuple[str, ...]) -> None:
        self.differences = differences
        super().__init__(f"CTX720 rebuild is incompatible: {'; '.join(differences)}")
