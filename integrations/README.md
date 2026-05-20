# integrations/

Optional MCP and external tool integrations.

All files here are **compacted** and loaded on demand only.

## MCP Wiring Status

| Integration | Documented | Wired in Runtime | Status |
|-------------|------------|------------------|--------|
| **OpenSpace** | `openspace-mcp.md` | ✅ Yes (stdio) | Active — configured in agent runtime |
| **Context7** | `context7-integration.md` | ❌ No | Not wired — add MCP server config to enable |
| **Vault** | `vault-mcp.md` | ❌ No | Not wired — add MCP server config to enable |
| **Confluence** | `confluence-mcp.md` | ❌ No | Not wired — add MCP server config to enable |
| **Playwright** | `playwright-mcp.md` | ❌ No | Not wired — add MCP server config to enable |

### How to Wire an MCP

1. Install the MCP server binary or npm package.
2. Add a `[[mcp.servers]]` entry to your agent runtime config.
3. Set required environment variables.
4. Test with a simple query before relying on it in production.

### Fail-Closed Rule

If an MCP server is documented but not wired, osEngineer falls back to the legacy path (e.g., grepping code instead of Context7, manual Vault CLI instead of Vault MCP). No operation fails due to a missing optional integration.
