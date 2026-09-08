"""Typed operational failures for the bounded M10b MCP adapter."""

from contextc.errors import ContextCompilerError


class MCPConnectionError(ContextCompilerError):
    """Local MCP process or transport could not be established."""


class MCPInitializationError(ContextCompilerError):
    """MCP initialization failed."""


class MCPProtocolError(ContextCompilerError):
    """MCP protocol exchange was invalid."""


class MCPToolDiscoveryError(ContextCompilerError):
    """Tool discovery failed."""


class MCPResourceDiscoveryError(ContextCompilerError):
    """Resource discovery failed."""


class MCPToolInvocationError(ContextCompilerError):
    """A bounded fixture tool invocation failed."""


class MCPResourceReadError(ContextCompilerError):
    """A bounded fixture resource read failed."""


class MCPSandboxViolationError(ContextCompilerError):
    """A fixture path attempted to escape the sandbox."""


class MCPPolicyBlockedError(ContextCompilerError):
    """The enforcement gate blocked an MCP sink."""


class MCPApprovalRequiredError(ContextCompilerError):
    """Trusted explicit approval is required before a sink may run."""


class MCPDeclarationMismatchError(ContextCompilerError):
    """Observed fixture behavior differed from the declaration."""


class MCPTimeoutError(ContextCompilerError):
    """A bounded live MCP operation timed out."""
