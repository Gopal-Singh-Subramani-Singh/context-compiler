"""Partial trust relation helpers."""

from __future__ import annotations

from contextc.ir import TrustDomain
from contextc.security.models import SecurityPolicy


def dominates(policy: SecurityPolicy, higher: TrustDomain, lower: TrustDomain) -> bool:
    """Return whether policy establishes higher >= lower through transitive closure."""
    if higher == lower:
        return True
    adjacency: dict[TrustDomain, set[TrustDomain]] = {}
    for source, target in policy.trust_dominates:
        adjacency.setdefault(source, set()).add(target)
    frontier = [higher]
    seen: set[TrustDomain] = set()
    while frontier:
        current = frontier.pop()
        if current in seen:
            continue
        seen.add(current)
        for target in sorted(adjacency.get(current, ()), key=lambda item: item.value):
            if target == lower:
                return True
            frontier.append(target)
    return False
