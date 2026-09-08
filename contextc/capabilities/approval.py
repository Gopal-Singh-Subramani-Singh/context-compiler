"""Explicit trusted approval evidence loading and validation helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from contextc.capabilities.models import ApprovalEvidence
from contextc.ir import TrustDomain


def approval_from_mapping(raw: object) -> ApprovalEvidence:
    if not isinstance(raw, Mapping):
        raise ValueError("approval evidence must be an object")
    required = ("approval_id", "plan_id", "flow_identity", "approver_identity")
    values: dict[str, str] = {}
    for name in required:
        value = raw.get(name)
        if not isinstance(value, str) or not value:
            raise ValueError(f"approval {name} must be a non-empty string")
        values[name] = value
    approved = raw.get("approved")
    if not isinstance(approved, bool):
        raise ValueError("approval approved must be boolean")
    evidence_uri = raw.get("evidence_uri")
    if evidence_uri is not None and not isinstance(evidence_uri, str):
        raise ValueError("approval evidence_uri must be a string or null")
    return ApprovalEvidence(
        approval_id=values["approval_id"],
        plan_id=values["plan_id"],
        flow_identity=values["flow_identity"],
        approver_identity=values["approver_identity"],
        approver_trust_domain=TrustDomain(
            str(raw.get("approver_trust_domain", "user_instruction"))
        ),
        approved=approved,
        evidence_uri=evidence_uri,
    )


def load_approval(path: Path) -> ApprovalEvidence:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid approval JSON: {error.msg}") from error
    return approval_from_mapping(raw)
