# Vault MCP (Optional)

**Trigger:** Secret rotation or policy change.  
**Context cost:** Loaded on demand.

## Compact Form

When activated:
1. Query Vault for current policy state.
2. Validate secret paths against allowlist.
3. NEVER write secrets to disk or logs.
