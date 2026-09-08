"""Secret-safe audit serialization for M10b."""

from __future__ import annotations

import json
from pathlib import Path

from contextc.canonical import to_canonical_primitive
from contextc.hashing import semantic_hash
from contextc.live_mcp.models import LiveMCPAuditEvent


def write_audit(path: Path, events: tuple[LiveMCPAuditEvent, ...]) -> str:
    payload = [to_canonical_primitive(event) for event in events]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return semantic_hash(payload)
