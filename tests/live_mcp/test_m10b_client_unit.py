from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import pytest

import contextc.live_mcp.client as client_mod
from contextc.live_mcp.client import LiveMCPClientAdapter, LiveMCPSession
from contextc.live_mcp.errors import (
    MCPInitializationError,
    MCPResourceDiscoveryError,
    MCPResourceReadError,
    MCPTimeoutError,
    MCPToolDiscoveryError,
    MCPToolInvocationError,
)
from contextc.live_mcp.fixture import validate_fixture_server
from contextc.live_mcp.models import LiveMCPServerSpec


class Result:
    def __init__(self, *, tools=(), resources=(), is_error=False):
        self.tools = list(tools)
        self.resources = list(resources)
        self.is_error = is_error


class Session:
    async def list_tools(self):
        return Result(tools=("a",))

    async def list_resources(self):
        return Result(resources=("r",))

    async def read_resource(self, uri):
        return {"uri": uri}

    async def call_tool(self, name, arguments=None):
        return Result()


def spec(tmp_path: Path, timeout: float = 0.05) -> LiveMCPServerSpec:
    return LiveMCPServerSpec(
        "tiny", "python", ("server.py",), str(tmp_path), timeout_seconds=timeout
    )


def test_live_session_success_paths(tmp_path: Path) -> None:
    s = LiveMCPSession(spec(tmp_path), Session())
    assert asyncio.run(s.list_tools()) == ("a",)
    assert asyncio.run(s.list_resources()) == ("r",)
    assert asyncio.run(s.read_resource("x")) == {"uri": "x"}
    assert isinstance(asyncio.run(s.call_tool("a")), Result)


def test_live_session_wraps_discovery_read_and_tool_errors(tmp_path: Path) -> None:
    class Broken:
        async def list_tools(self):
            raise ValueError("tools")

        async def list_resources(self):
            raise ValueError("resources")

        async def read_resource(self, uri):
            raise ValueError(uri)

        async def call_tool(self, name, arguments=None):
            return Result(is_error=True)

    s = LiveMCPSession(spec(tmp_path), Broken())
    with pytest.raises(MCPToolDiscoveryError):
        asyncio.run(s.list_tools())
    with pytest.raises(MCPResourceDiscoveryError):
        asyncio.run(s.list_resources())
    with pytest.raises(MCPResourceReadError):
        asyncio.run(s.read_resource("bad"))
    with pytest.raises(MCPToolInvocationError):
        asyncio.run(s.call_tool("bad"))


def test_live_session_timeout(tmp_path: Path) -> None:
    class Slow:
        async def list_tools(self):
            await asyncio.sleep(0.2)
            return Result()

    server = LiveMCPServerSpec(
        "tiny",
        "python",
        ("server.py",),
        str(tmp_path),
        timeout_seconds=5.0,
        operation_timeout_seconds=0.001,
    )
    with pytest.raises(MCPTimeoutError, match=r"0\.001s"):
        asyncio.run(LiveMCPSession(server, Slow()).list_tools())


def test_client_adapter_uses_sdk_boundary_and_sandbox_environment(
    monkeypatch, tmp_path: Path
) -> None:
    seen = {}

    class Params:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    class Low:
        async def initialize(self):
            seen["initialized"] = True

        async def list_tools(self):
            return Result()

        async def list_resources(self):
            return Result()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    @contextlib.asynccontextmanager
    async def stdio(params):
        yield object(), object()

    def factory(read, write):
        return Low()

    monkeypatch.setattr(client_mod, "_sdk", lambda: (factory, Params, stdio))

    async def run():
        async with LiveMCPClientAdapter().connect(spec(tmp_path)) as live:
            assert isinstance(live, LiveMCPSession)

    asyncio.run(run())
    assert seen["initialized"] is True
    assert seen["cwd"] == str(tmp_path.resolve())
    assert seen["env"]["HOME"] == str(tmp_path.resolve())
    assert seen["env"]["CONTEXTC_MCP_SANDBOX"] == str(tmp_path.resolve())


def test_client_adapter_initialization_failure_is_typed(monkeypatch, tmp_path: Path) -> None:
    class Params:
        def __init__(self, **kwargs):
            pass

    class Low:
        async def initialize(self):
            raise ValueError("bad init")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    @contextlib.asynccontextmanager
    async def stdio(params):
        yield object(), object()

    monkeypatch.setattr(client_mod, "_sdk", lambda: (lambda r, w: Low(), Params, stdio))

    async def run():
        async with LiveMCPClientAdapter().connect(spec(tmp_path)):
            pass

    with pytest.raises(MCPInitializationError):
        asyncio.run(run())


def test_fixture_server_requires_marker(tmp_path: Path) -> None:
    good = tmp_path / "good.py"
    good.write_text("CONTEXTC_TINY_MCP_FIXTURE = True\n")
    assert validate_fixture_server(good) == good.resolve()
    bad = tmp_path / "bad.py"
    bad.write_text("print('no marker')\n")
    with pytest.raises(Exception, match="restricted to a marked bounded fixture"):
        validate_fixture_server(bad)


def test_client_adapter_unwraps_sdk_exception_groups(monkeypatch, tmp_path: Path) -> None:
    class Params:
        def __init__(self, **kwargs):
            pass

    class Low:
        async def initialize(self):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            if exc is not None:
                raise ExceptionGroup("session teardown", [exc])
            return False

    @contextlib.asynccontextmanager
    async def stdio(params):
        try:
            yield object(), object()
        except BaseException as error:
            raise ExceptionGroup("stdio teardown", [error]) from error

    monkeypatch.setattr(client_mod, "_sdk", lambda: (lambda r, w: Low(), Params, stdio))

    async def run():
        async with LiveMCPClientAdapter().connect(spec(tmp_path)):
            raise MCPResourceReadError("typed resource failure")

    with pytest.raises(MCPResourceReadError, match="typed resource failure"):
        asyncio.run(run())
