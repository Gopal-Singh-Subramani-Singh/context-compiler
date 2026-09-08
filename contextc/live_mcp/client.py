"""Official MCP SDK adapter for bounded stdio validation.

The SDK is imported lazily so the core CLI still starts without the live-mcp extra.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contextc.errors import ContextCompilerError, OptionalDependencyError
from contextc.live_mcp.errors import (
    MCPConnectionError,
    MCPInitializationError,
    MCPResourceDiscoveryError,
    MCPResourceReadError,
    MCPTimeoutError,
    MCPToolDiscoveryError,
    MCPToolInvocationError,
)
from contextc.live_mcp.models import LiveMCPServerSpec


def _sdk() -> tuple[Any, Any, Any]:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as error:
        raise OptionalDependencyError(
            feature="live MCP validation", module="mcp", extra="live-mcp"
        ) from error
    return ClientSession, StdioServerParameters, stdio_client


@dataclass(slots=True)
class LiveMCPSession:
    spec: LiveMCPServerSpec
    session: Any

    async def _bounded(self, awaitable: Any, label: str) -> Any:
        timeout_seconds = (
            self.spec.operation_timeout_seconds
            if self.spec.operation_timeout_seconds is not None
            else self.spec.timeout_seconds
        )
        try:
            return await asyncio.wait_for(awaitable, timeout=timeout_seconds)
        except TimeoutError as error:
            raise MCPTimeoutError(f"live MCP {label} timed out after {timeout_seconds}s") from error

    async def list_tools(self) -> tuple[object, ...]:
        try:
            result = await self._bounded(self.session.list_tools(), "tools/list")
            return tuple(result.tools)
        except MCPTimeoutError:
            raise
        except Exception as error:
            raise MCPToolDiscoveryError(
                f"MCP tool discovery failed: {type(error).__name__}: {error}"
            ) from error

    async def list_resources(self) -> tuple[object, ...]:
        try:
            result = await self._bounded(self.session.list_resources(), "resources/list")
            return tuple(result.resources)
        except MCPTimeoutError:
            raise
        except Exception as error:
            raise MCPResourceDiscoveryError(
                f"MCP resource discovery failed: {type(error).__name__}: {error}"
            ) from error

    async def read_resource(self, uri: str) -> object:
        try:
            return await self._bounded(self.session.read_resource(uri), "resources/read")
        except MCPTimeoutError:
            raise
        except Exception as error:
            raise MCPResourceReadError(
                f"MCP resource read failed for {uri}: {type(error).__name__}: {error}"
            ) from error

    async def call_tool(self, name: str, arguments: Mapping[str, object] | None = None) -> object:
        try:
            result = await self._bounded(
                self.session.call_tool(name, arguments=dict(arguments or {})),
                f"tools/call {name}",
            )
            is_error = getattr(result, "is_error", getattr(result, "isError", False))
            if is_error:
                raise MCPToolInvocationError(f"MCP tool {name} returned an error result")
            return result
        except (MCPTimeoutError, MCPToolInvocationError):
            raise
        except Exception as error:
            raise MCPToolInvocationError(
                f"MCP tool invocation failed for {name}: {type(error).__name__}: {error}"
            ) from error


def _walk_exception_tree(error: BaseException) -> tuple[BaseException, ...]:
    """Flatten nested exception groups emitted by AnyIO/MCP teardown."""
    if isinstance(error, BaseExceptionGroup):
        flattened: list[BaseException] = []
        for nested in error.exceptions:
            flattened.extend(_walk_exception_tree(nested))
        return tuple(flattened)
    return (error,)


def _raise_normalized_transport_error(error: BaseExceptionGroup) -> None:
    """Restore Context Compiler's typed boundary after SDK task-group cleanup.

    AnyIO may wrap an exception raised while the MCP session is active in one or
    more ExceptionGroup instances when its task groups unwind.  Those wrappers
    are transport implementation detail and must not escape the Context Compiler
    application boundary.
    """
    flattened = _walk_exception_tree(error)
    for nested in flattened:
        if isinstance(nested, ContextCompilerError):
            raise nested from error
    for nested in flattened:
        if isinstance(nested, OSError):
            raise MCPConnectionError(f"unable to start local MCP server: {nested}") from error
    raise error


class LiveMCPClientAdapter:
    """Small boundary around the maintained MCP SDK stdio transport."""

    @contextlib.asynccontextmanager
    async def connect(self, spec: LiveMCPServerSpec) -> AsyncIterator[LiveMCPSession]:
        ClientSession, StdioServerParameters, stdio_client = _sdk()
        sandbox = Path(spec.sandbox).resolve()
        env = {
            "CONTEXTC_MCP_SANDBOX": str(sandbox),
            "CONTEXTC_MCP_FIXTURE_VERSION": spec.fixture_version,
            "HOME": str(sandbox),
            "PATH": os.environ.get("PATH", ""),
        }
        params = StdioServerParameters(
            command=spec.command,
            args=list(spec.args),
            env=env,
            cwd=str(sandbox),
        )
        try:
            async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
                try:
                    await asyncio.wait_for(session.initialize(), timeout=spec.timeout_seconds)
                except TimeoutError as error:
                    raise MCPTimeoutError(
                        f"MCP initialization timed out after {spec.timeout_seconds}s"
                    ) from error
                except Exception as error:
                    raise MCPInitializationError(
                        f"MCP initialization failed: {type(error).__name__}: {error}"
                    ) from error
                yield LiveMCPSession(spec, session)
        except ContextCompilerError:
            raise
        except BaseExceptionGroup as error:
            _raise_normalized_transport_error(error)
        except OSError as error:
            raise MCPConnectionError(f"unable to start local MCP server: {error}") from error
