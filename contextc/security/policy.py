"""Security policy loading, validation, and canonical identity."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from importlib.resources import files
from pathlib import Path

from contextc.hashing import semantic_hash
from contextc.ir import Sensitivity, TrustDomain
from contextc.security.models import PolicyAction, SecurityPolicy, SecurityRule


def _sequence(value: object, name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a list")
    return value


def policy_from_mapping(data: object) -> SecurityPolicy:
    if not isinstance(data, Mapping):
        raise ValueError("security policy must be an object")
    policy_id = data.get("policy_id")
    version = data.get("version")
    if (
        not isinstance(policy_id, str)
        or not policy_id
        or not isinstance(version, str)
        or not version
    ):
        raise ValueError("policy_id and version must be non-empty strings")

    rules: list[SecurityRule] = []
    seen: set[str] = set()
    for raw in _sequence(data.get("rules", ()), "rules"):
        if not isinstance(raw, Mapping):
            raise ValueError("each security rule must be an object")
        rule_id = raw.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id or rule_id in seen:
            raise ValueError("rule_id must be unique and non-empty")
        seen.add(rule_id)
        diagnostic_code = raw.get("diagnostic_code")
        rules.append(
            SecurityRule(
                rule_id=rule_id,
                action=PolicyAction(str(raw.get("action"))),
                diagnostic_code=(diagnostic_code if isinstance(diagnostic_code, str) else None),
                source_domains=tuple(
                    TrustDomain(str(value))
                    for value in _sequence(raw.get("source_domains", ()), "source_domains")
                ),
                sensitivities=tuple(
                    Sensitivity(str(value))
                    for value in _sequence(raw.get("sensitivities", ()), "sensitivities")
                ),
                signal_categories=tuple(
                    str(value)
                    for value in _sequence(raw.get("signal_categories", ()), "signal_categories")
                ),
                sink_kinds=tuple(
                    str(value) for value in _sequence(raw.get("sink_kinds", ()), "sink_kinds")
                ),
                enabled=bool(raw.get("enabled", True)),
            )
        )

    trust: list[tuple[TrustDomain, TrustDomain]] = []
    for pair in _sequence(data.get("trust_dominates", ()), "trust_dominates"):
        values = _sequence(pair, "trust_dominates entries")
        if len(values) != 2:
            raise ValueError("trust_dominates entries must be [higher, lower]")
        trust.append((TrustDomain(str(values[0])), TrustDomain(str(values[1]))))

    default_untrusted = (
        "unverified_tool",
        "external_content",
        "retrieved_document",
    )
    untrusted = tuple(
        TrustDomain(str(value))
        for value in _sequence(
            data.get("untrusted_domains", default_untrusted), "untrusted_domains"
        )
    )
    return SecurityPolicy(
        policy_id=policy_id,
        version=version,
        rules=tuple(rules),
        trust_dominates=tuple(trust),
        untrusted_domains=untrusted,
        external_sink_kinds=tuple(
            str(value)
            for value in _sequence(
                data.get("external_sink_kinds", ("external", "tool", "network")),
                "external_sink_kinds",
            )
        ),
        instruction_sink_kinds=tuple(
            str(value)
            for value in _sequence(
                data.get(
                    "instruction_sink_kinds",
                    ("instruction", "system", "developer"),
                ),
                "instruction_sink_kinds",
            )
        ),
    )


def load_policy(path: Path | None = None) -> SecurityPolicy:
    if path is None:
        text = (
            files("contextc.resources.security")
            .joinpath("default_policy.yaml")
            .read_text(encoding="utf-8")
        )
    else:
        text = path.read_text(encoding="utf-8")
    # The packaged format remains JSON-compatible YAML. M8 permits whole-line
    # YAML/JSON-style comments so comment-only edits preserve canonical policy
    # semantics and therefore preserve the security-stage cache key.
    semantic_text = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith(("#", "//"))
    )
    try:
        data = json.loads(semantic_text)
    except json.JSONDecodeError as error:
        raise ValueError(
            "policy must use JSON syntax with optional whole-line # or // comments"
        ) from error
    return policy_from_mapping(data)


def policy_identity(policy: SecurityPolicy) -> str:
    return semantic_hash(policy.identity_payload)
