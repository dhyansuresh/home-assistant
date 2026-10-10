"""Application runtime MCP scaffold. Tools are added after persistence is reviewed."""

from mcp.server import MCPServer

mcp = MCPServer("homepilot-runtime")

# Add only the allowlisted tools in docs/API_CONTRACTS.md. Each tool must bind
# household identity from trusted server configuration, validate inputs, and
# return the observed Supabase result. Do not add placeholder write tools.

if __name__ == "__main__":
    mcp.run(transport="stdio")
