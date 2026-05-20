# /osEngineer:init

**Syntax:** `/osEngineer:init <project-root>`  
**Role:** Researcher agent  
**Output:** `RESEARCH.md` in `planning/active/`

---

## Description

Initialize osEngineer on a new project. Discovers repos, ADRs, graphs, and builds the initial knowledge base.

## Steps

1. Accept `project-root` (default: current directory).
2. Run `discovery/repo-discovery.md` protocol.
3. Read ADR catalog (if exists).
4. Check for `graphify-out/`.
5. Generate `RESEARCH.md` with repo topology.
6. If project identified as Sovereign Shield, load `discovery/sovereign-shield-repo-map.yml`.

## Example

```
/osEngineer:init /opt/sovereign-shield
```

Output:
```
Discovered 28 repos.
Loaded 14 ADRs.
Graphify graph found (last build: 2026-05-19).
Generated: planning/active/RESEARCH.md
```
