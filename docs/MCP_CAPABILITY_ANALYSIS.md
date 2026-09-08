# MCP Capability Analysis

M10a remains the canonical static capability/composition analyzer. M10b discovers live declarations and maps them into the existing M10a `ToolDeclaration` and `ResourceDeclaration` types before any dangerous sink invocation. The live layer does not create a parallel capability vocabulary or approval system.

Runtime observations are compared with declarations. Unexpected observed capabilities or sensitivity produce `CTX445` and a hard M10b execution stop for subsequent calls.
