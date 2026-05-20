# Context7 Integration

**Agent:** Researcher, Developer  
**Tool:** Context7 MCP Server  
**Purpose:** Up-to-date code documentation for any prompt.

---

## When to Use Context7

| Question Type | Use Context7? |
|---------------|---------------|
| "What does function X do?" | ✅ Yes |
| "Show me all usages of type Y" | ✅ Yes |
| "What is the signature of Z?" | ✅ Yes |
| "Architecture overview" | ❌ No → use graphify |
| "Why was this decision made?" | ❌ No → read ADR |

## MCP Configuration

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"]
    }
  }
}
```

## Project Usage

Context7 is most useful for:
- **External dependencies:** Quick docs for RabbitMQ client, Docker SDK, Vault API.
- **Shared utilities:** `<shared-lib>` functions used across repos.
- **New team members:** Onboarding questions without grepping the whole codebase.

## Limitations

- Context7 knows code, not architecture. For "why" questions, read ADRs.
- Context7 may lag behind latest commits by hours. For bleeding-edge changes, read code directly.
