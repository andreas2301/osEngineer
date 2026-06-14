---
name: osEngineer:init
description: >-
  Initialises osEngineer wiring on a single repo or a workbench. Runs
  install.sh, detects folder→team mapping (proposes a draft AGENTS.md the
  user confirms), copies agents into .claude/agents/, installs the 10
  enforcement hooks, and seeds .osengineer/state.yml. Use when starting
  osEngineer on a new repo, when re-initialising after a skill update, or
  when adding a new repo to an existing workbench. Don't use during an
  active phase (transition to idle first), and don't use to update an
  existing AGENTS.md — edit it directly.
phase_allowed: [idle]
---

# /osEngineer:init

**Syntax:** `/osEngineer:init <project-root>`  
**Role:** Researcher agent  
**Output:** `RESEARCH.md` in `planning/active/`

---

## Description

Initialize osEngineer on a new project. Discovers repos, ADRs, graphs, and builds the initial knowledge base.

## Steps

1. **Detect execution environment** (`discovery/execution-environment.md`):
   - Run automated probes (shell, IDE, Docker, gh, daemon).
   - **ASK USER** to confirm or correct detection. NEVER assume.
   - Store result in `memory/environment-profile.yml`.
   - All subsequent agents adapt behavior based on this profile.

2. Accept `project-root` (default: current directory).
3. Run `discovery/repo-discovery.md` protocol.
4. Read ADR catalog (if exists).
5. Check for `graphify-out/`.
6. Generate `RESEARCH.md` with repo topology from `.osengineer/workbench-config.yml`.
7. Load project-specific overlays from `examples/<project-name>/` if they exist.

## Example

```
/osEngineer:init /path/to/project-root
```

Output:
```
Discovered 28 repos.
Loaded 14 ADRs.
Graphify graph found (last build: 2026-05-19).
Generated: planning/active/RESEARCH.md
```
