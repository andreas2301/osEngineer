# Confluence MCP (Optional)

**Trigger:** Repo has `confluence_page_id` in CLAUDE.md.  
**Context cost:** Loaded on demand.

## Compact Form

When activated:
1. Fetch live Confluence page for repo context.
2. Extract service boundaries and runbooks.
3. Cache page content in `memory/confluence-cache/`.
