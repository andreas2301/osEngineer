# ADR Catalog Protocol

**Agent:** Researcher, Tech-Writer  
**Purpose:** Read and maintain Architectural Decision Records.

---

## ADR Locations

Search in this order:
1. `docs/adr/` — standard location
2. `.claude/adr-catalog/` — agent-optimized location
3. `META/docs/adr/` — meta-repo location
4. Any `ADR-*.md` file in the repo root

## ADR Frontmatter Schema

```yaml
---
adr_id: ADR-018
status: Accepted | Proposed | Superseded
date: 2026-05-10
authors: [Andreas Greger]
tags: [amqp, topology, v3.6]
supersedes: ADR-NNN  # optional
superseded_by: ADR-NNN  # optional
---
```

## Reading Protocol

When researching a topic:
1. Read `INDEX.md` first (catalog of all ADRs).
2. Read ADRs with `status: Accepted` and relevant `tags`.
3. If an ADR is `Superseded`, follow the chain to the latest.
4. Note `supersedes` links for historical context.

## Writing Protocol

When a new cross-cutting decision is needed:
1. Check existing ADRs — does one already cover this?
2. If YES → amend or supersede.
3. If NO → write new ADR with:
   - Context (why now?)
   - Decision (what was decided?)
   - Consequences (trade-offs, risks)
   - References (related ADRs, issues)
4. Update `INDEX.md`.
5. Notify affected repos (via PR description or issue).
