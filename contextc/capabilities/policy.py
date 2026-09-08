"""Versioned canonical M10a capability-policy loading."""

from __future__ import annotations

import json
from collections.abc import Mapping
from importlib.resources import files
from pathlib import Path

from contextc.capabilities.models import (
    CapabilityPolicy,
    CapabilityPolicyAction,
    CapabilityPolicyRule,
    RiskKind,
)
from contextc.ir import TrustDomain


def policy_from_mapping(raw: object) -> CapabilityPolicy:
    if not isinstance(raw, Mapping):
        raise ValueError("capability policy must be an object")
    policy_id = raw.get("policy_id")
    version = raw.get("version")
    rules_raw = raw.get("rules")
    if not isinstance(policy_id, str) or not policy_id:
        raise ValueError("capability policy_id must be a non-empty string")
    if not isinstance(version, str) or not version:
        raise ValueError("capability policy version must be a non-empty string")
    if not isinstance(rules_raw, list):
        raise ValueError("capability policy rules must be a list")
    rules: list[CapabilityPolicyRule] = []
    seen: set[str] = set()
    for item in rules_raw:
        if not isinstance(item, Mapping):
            raise ValueError("capability policy rules must be objects")
        rule_id = item.get("rule_id")
        risks = item.get("risk_kinds")
        if not isinstance(rule_id, str) or not rule_id or rule_id in seen:
            raise ValueError("capability rule_id must be unique and non-empty")
        if not isinstance(risks, list) or not risks:
            raise ValueError(f"capability rule {rule_id} risk_kinds must be non-empty")
        seen.add(rule_id)
        rules.append(
            CapabilityPolicyRule(
                rule_id=rule_id,
                risk_kinds=tuple(RiskKind(str(value)) for value in risks),
                action=CapabilityPolicyAction(str(item.get("action"))),
                enabled=bool(item.get("enabled", True)),
            )
        )
    trusted_raw = raw.get(
        "trusted_approval_domains",
        ["user_instruction", "developer_instruction", "system_policy"],
    )
    untrusted_raw = raw.get(
        "untrusted_domains",
        ["unverified_tool", "external_content", "retrieved_document"],
    )
    if not isinstance(trusted_raw, list) or not isinstance(untrusted_raw, list):
        raise ValueError("capability policy trust-domain fields must be lists")
    return CapabilityPolicy(
        policy_id=policy_id,
        version=version,
        rules=tuple(rules),
        trusted_approval_domains=tuple(TrustDomain(str(value)) for value in trusted_raw),
        untrusted_domains=tuple(TrustDomain(str(value)) for value in untrusted_raw),
    )


def load_policy(path: Path | None = None) -> CapabilityPolicy:
    if path is None:
        text = (
            files("contextc.resources.capabilities")
            .joinpath("default_capability_policy.yaml")
            .read_text(encoding="utf-8")
        )
    else:
        text = path.read_text(encoding="utf-8")
    semantic_text = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith(("#", "//"))
    )
    try:
        raw = json.loads(semantic_text)
    except json.JSONDecodeError as error:
        raise ValueError(
            "capability policy must use JSON syntax with optional whole-line # or // comments"
        ) from error
    return policy_from_mapping(raw)
