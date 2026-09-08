"""Sandbox containment helpers shared by M10b fixtures and tests."""

from __future__ import annotations

from pathlib import Path

from contextc.live_mcp.errors import MCPSandboxViolationError


def contained_path(root: Path, relative: str, *, must_exist: bool = False) -> Path:
    if not relative or Path(relative).is_absolute():
        raise MCPSandboxViolationError("absolute or empty sandbox path rejected")
    if any(part == ".." for part in Path(relative).parts):
        raise MCPSandboxViolationError("parent traversal rejected")
    root_resolved = root.resolve(strict=True)
    candidate = root / relative
    try:
        resolved = candidate.resolve(strict=must_exist)
    except FileNotFoundError as error:
        raise MCPSandboxViolationError("sandbox path does not exist") from error
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise MCPSandboxViolationError("sandbox escape rejected")
    return resolved


def initialize_fixture_sandbox(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "public.txt").write_text("Context Compiler public MCP fixture.\n", encoding="utf-8")
    (root / "internal.txt").write_text("CONTEXTC_TEST_INTERNAL_RECORD_C442\n", encoding="utf-8")
    (root / "secret.txt").write_text("CONTEXTC_TEST_SECRET_7F31\n", encoding="utf-8")
    (root / "credential.txt").write_text("CONTEXTC_TEST_CREDENTIAL_A91C\n", encoding="utf-8")
    for name in ("outbound-ledger.jsonl", "execution-ledger.jsonl", "network-ledger.jsonl"):
        (root / name).write_text("", encoding="utf-8")
