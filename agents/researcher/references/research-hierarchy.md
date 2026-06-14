# Research Hierarchy

When asked "How does X work?", follow this order:

1. **Project Overview first**:
   - Read `PROJECT_OVERVIEW.md` at the workbench root.
   - Check `knowledge_sources` in `.osengineer/workbench-config.yml`.
   - If X is documented externally (Confluence, Notion, Miro, Figma), query that source BEFORE grepping code.

2. **Graphify second** (if `graphify-out/` exists):
   - Query the graph for X's community, call sites, and dependencies.
   - Cost: ~1.5K tokens vs 8–10 grep cycles at 4–5K.

3. **ADR catalog third**:
   - Read `docs/adr/INDEX.md` or `.claude/adr-catalog/INDEX.md`.
   - Find ADRs mentioning X.

4. **CLAUDE.md fourth**:
   - Read `.claude/CLAUDE.md` or `AGENTS.md` in the relevant repo.
   - Look for "How X works" or "X architecture" sections.

5. **Code read last**:
   - Only if all above sources don't answer the question.
   - Read the minimal set of files (≤ 3 files, ≤ 200 lines each).
