from __future__ import annotations

import builtins

import pytest

from contextc.errors import OptionalDependencyError
from contextc.live_mcp import client


def test_missing_sdk_is_typed_optional_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "mcp" or name.startswith("mcp."):
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(OptionalDependencyError, match="live-mcp"):
        client._sdk()
