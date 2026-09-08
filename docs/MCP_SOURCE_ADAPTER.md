# MCP Source Adapter

M9's static MCP source adapter remains the canonical route for retained MCP-shaped results. M10b adds a live acquisition boundary but normalizes runtime tool output back into the same source facts: `mcp://<server>/tools/<tool>/results/<interaction-id>`, explicit trust/sensitivity, and `InstructionAuthority.NONE` for ordinary tool output. Live server identity never grants instruction authority.
