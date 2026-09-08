"""Deterministic project-local source-fact classification rules."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fnmatch import fnmatchcase

from contextc.errors import ConfigurationError
from contextc.hashing import semantic_hash
from contextc.ir import InstructionAuthority, Sensitivity, TrustDomain

_SAFE_REPOSITORY_TRUST_DOMAINS = frozenset(
    {
        TrustDomain.LOCAL_REPOSITORY,
        TrustDomain.RETRIEVED_DOCUMENT,
        TrustDomain.UNVERIFIED_TOOL,
        TrustDomain.EXTERNAL_CONTENT,
    }
)
_SAFE_REPOSITORY_SENSITIVITIES = frozenset(
    {Sensitivity.INTERNAL, Sensitivity.SENSITIVE, Sensitivity.SECRET}
)


@dataclass(frozen=True, slots=True)
class SourceFactRule:
    """Classify immutable source facts for repository-relative paths.

    Rules are evaluated in declaration order. For each fact, the last matching
    rule that specifies that fact wins. Unspecified facts retain the repository
    parser defaults.
    """

    glob: str
    trust_domain: TrustDomain | None = None
    sensitivity: Sensitivity | None = None
    instruction_authority: InstructionAuthority | None = None

    def __post_init__(self) -> None:
        if not self.glob or self.glob.startswith("/"):
            raise ConfigurationError("source rule glob must be a non-empty relative pattern")
        if ".." in self.glob.split("/"):
            raise ConfigurationError("source rule glob must not traverse above the repository")
        if (
            self.trust_domain is None
            and self.sensitivity is None
            and self.instruction_authority is None
        ):
            raise ConfigurationError("source rule must override at least one source fact")
        if (
            self.trust_domain is not None
            and self.trust_domain not in _SAFE_REPOSITORY_TRUST_DOMAINS
        ):
            raise ConfigurationError(
                "repository source rules may not promote trust into privileged domains"
            )
        if self.sensitivity is not None and self.sensitivity not in _SAFE_REPOSITORY_SENSITIVITIES:
            raise ConfigurationError(
                "repository source rules may not declassify content below internal"
            )
        if (
            self.instruction_authority is not None
            and self.instruction_authority is not InstructionAuthority.NONE
        ):
            raise ConfigurationError("repository source rules may not grant instruction authority")

    def matches(self, relative_path: str) -> bool:
        """Return whether the POSIX repository-relative path matches this rule."""

        return fnmatchcase(relative_path, self.glob)

    @property
    def identity(self) -> str:
        return semantic_hash(self)


def source_rules_identity(rules: Sequence[SourceFactRule]) -> str:
    """Hash ordered rule semantics, including precedence."""

    return semantic_hash(tuple(rules))


def source_rule_from_mapping(value: Mapping[str, object]) -> SourceFactRule:
    """Decode one strict TOML/manifest source-fact rule."""

    allowed = {"glob", "trust_domain", "sensitivity", "instruction_authority"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigurationError(f"unknown source rule keys: {', '.join(unknown)}")
    glob = value.get("glob")
    if not isinstance(glob, str):
        raise ConfigurationError("source rule glob must be text")

    def _optional_enum(name: str, enum_type: type[object]) -> object | None:
        raw = value.get(name)
        if raw is None:
            return None
        if not isinstance(raw, str):
            raise ConfigurationError(f"source rule {name} must be text")
        try:
            return enum_type(raw)  # type: ignore[call-arg]
        except ValueError as error:
            raise ConfigurationError(f"unsupported source rule {name}: {raw}") from error

    return SourceFactRule(
        glob=glob,
        trust_domain=_optional_enum("trust_domain", TrustDomain),  # type: ignore[arg-type]
        sensitivity=_optional_enum("sensitivity", Sensitivity),  # type: ignore[arg-type]
        instruction_authority=_optional_enum("instruction_authority", InstructionAuthority),  # type: ignore[arg-type]
    )


def source_rules_from_sequence(value: object) -> tuple[SourceFactRule, ...]:
    """Decode an ordered array of source rules."""

    if value is None:
        return ()
    if not isinstance(value, list):
        raise ConfigurationError("source_rules must be an array of tables")
    rules: list[SourceFactRule] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ConfigurationError(f"source_rules[{index}] must be a table")
        rules.append(source_rule_from_mapping(item))
    return tuple(rules)


def source_rules_from_manifest(value: object) -> tuple[SourceFactRule, ...]:
    """Decode canonical manifest source rules."""

    if not isinstance(value, (tuple, list)):
        raise ConfigurationError("stored source_rules must be a sequence")
    rules: list[SourceFactRule] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ConfigurationError(f"stored source_rules[{index}] must be a mapping")
        rules.append(source_rule_from_mapping(item))
    return tuple(rules)
