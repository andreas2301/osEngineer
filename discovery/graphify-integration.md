# Graphify Integration

**Agent:** Researcher  
**Tool:** graphify (AST + LLM knowledge graph)  
**Purpose:** Replace grep cycles with token-cheap graph queries.

---

## When to Use Graphify

| Question Type | Use Graphify? | Alternative |
|---------------|---------------|-------------|
| "What calls X?" | ✅ Yes | grep (slower, more tokens) |
| "What is X's community?" | ✅ Yes | Manual file reading |
| "Architecture overview" | ✅ Yes | ADR + manual exploration |
| "What changed in the last commit?" | ❌ No | git diff |
| "What does this function do?" | ⚠️ Maybe | Context7 MCP (better for docs) |

## Query Patterns

```bash
# Load graph
cat graphify-out/graph.json | jq '.nodes[] | select(.id | contains("SpawnContainer"))'

# Find community
cat graphify-out/graph.json | jq '.communities[] | select(.name | contains("docker lifecycle"))'

# Shortest path between two nodes
# (Use graphify CLI or MCP server for complex queries)
```

## Graph Maintenance

- **Full rebuild:** After major refactor (>20% files changed). Cost: high (LLM extraction).
- **AST-only rebuild:** After routine commits. Cost: low (deterministic, no LLM).
- **Skip filter:** Post-commit hook exits early if all changed files are inside `graphify-out/`.

## Graphify Locations

By default, each repo with graphify produces:
- `graphify-out/graph.json` — raw graph
- `graphify-out/GRAPH_REPORT.md` — human-readable summary
- `graphify-out/graph.html` — interactive visualization

If your project uses a different output path, set it in `.osengineer/workbench-config.yml`:

```yaml
graphify:
  output_dir: ./graphify-out
```
