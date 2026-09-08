"""Bounded instruction-like pattern signals with conservative quote controls."""

from __future__ import annotations

import re

from contextc.hashing import semantic_hash
from contextc.ir import ContextNode
from contextc.security.models import PatternSignal

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "override_prior_instructions",
        re.compile(
            r"\b(ignore|override|disregard)\b.{0,48}\b(instruction|policy|rule)s?\b",
            re.I | re.S,
        ),
    ),
    (
        "claim_higher_authority",
        re.compile(
            r"\b(i am|act as|this is)\b.{0,32}\b(system|developer|administrator|root)\b",
            re.I | re.S,
        ),
    ),
    (
        "credential_disclosure",
        re.compile(
            r"\b(reveal|send|print|expose)\b.{0,48}"
            r"\b(password|token|credential|secret|api key)\b",
            re.I | re.S,
        ),
    ),
    (
        "external_exfiltration",
        re.compile(
            r"\b(send|upload|post|exfiltrate)\b.{0,64}"
            r"\b(external|remote|server|url|endpoint)\b",
            re.I | re.S,
        ),
    ),
    (
        "embedded_execution",
        re.compile(
            r"\b(run|execute|shell|bash|powershell)\b.{0,48}"
            r"\b(command|script|code|curl|wget)\b",
            re.I | re.S,
        ),
    ),
    (
        "change_privileged_policy",
        re.compile(
            r"\b(change|replace|disable|bypass)\b.{0,48}"
            r"\b(system|developer)\b.{0,24}"
            r"\b(policy|instruction|guardrail)s?\b",
            re.I | re.S,
        ),
    ),
)

_DISCUSSION = re.compile(
    r"\b(example|discussion|discuss|quoted|quote|attack string|security training|documentation)\b",
    re.I,
)


def detect_instruction_signals(node: ContextNode) -> tuple[PatternSignal, ...]:
    content = node.content
    if _DISCUSSION.search(content) and (content.count('"') >= 2 or content.count("`") >= 2):
        return ()
    found: list[PatternSignal] = []
    for category, pattern in _PATTERNS:
        match = pattern.search(content)
        if match is None:
            continue
        fragment = match.group(0)
        found.append(
            PatternSignal(
                category=category,
                node_id=node.node_id,
                matched_fragment_hash=semantic_hash({"fragment": fragment.casefold()}),
                confidence=0.8,
            )
        )
    return tuple(sorted(found, key=lambda item: (item.node_id, item.category)))
