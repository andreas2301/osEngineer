# Confluence MCP Integration

**Status:** Optional — load only when your project uses Atlassian Confluence/Jira for documentation.

## Purpose

Sync ADRs, phase plans, and retrospectives between the osEngineer workbench and a Confluence space. This keeps human stakeholders informed without requiring them to read git-tracked markdown files.

## Configuration

Create `.osengineer/confluence-mcp.yml` in your workbench root:

```yaml
confluence:
  base_url: https://your-org.atlassian.net
  space_key: DOC
  username: $CONFLUENCE_USER
  api_token: $CONFLUENCE_API_TOKEN
sync:
  adrs:
    source: ./meta/docs/adr/
    target_page: "Architecture Decision Records"
  phase_plans:
    source: ./planning/active/
    target_page: "Active Phase Plans"
  retrospectives:
    source: ./memory/retrospectives/
    target_page: "Engineering Retrospectives"
```

## Authentication

Set environment variables before running osEngineer:
```bash
export CONFLUENCE_USER="your.email@company.com"
export CONFLUENCE_API_TOKEN="..."
```

## See Also

- `examples/sovereign-shield/integrations/confluence-mcp.md` for a complete reference implementation.
