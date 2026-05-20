# Agent Catalog

osEngineer uses a **role-based agent team** sized to repo complexity. For small repos, roles collapse into the developer. For large cross-repo work, all roles fire in sequence.

## Mandatory Agents (always loaded)

| Agent | Role | File |
|-------|------|------|
| **Developer** | Primary implementer; writes code, tests, commits | `agents/developer.md` |
| **Reviewer** | Per-PR code review; style, correctness, test coverage | `agents/reviewer.md` |
| **Judge** | Merge gate; architectural alignment, ADR compliance | `agents/judge.md` |
| **Red Team (Local)** | Per-PR security scan; SAST, secrets, allowlist | `agents/red-team-local.md` |
| **Red Team (Architect)** | Cross-repo invariant checks; topology drift, ADR violations | `agents/red-team-architect.md` |
| **Tech Writer** | Contracts, docs, OpenAPI, ADR amendments | `agents/tech-writer.md` |
| **Researcher** | Discovery, graph queries, ADR catalog read | `agents/researcher.md` |
| **Planner** | Phase breakdown, deps, token estimates, risk flags | `agents/planner.md` |

## Optional Agents (compacted; loaded on demand)

| Agent | Role | File | Trigger |
|-------|------|------|---------|
| **DBA** | Schema design, migrations, query optimization | `agents/dba.md` | Database change detected |
| **QA** | Test strategy, edge-case analysis, load testing | `agents/qa.md` | Test coverage < 80% |
| **UI/UX Designer** | Design intelligence, accessibility, component systems | `agents/ui-ux-designer.md` | Frontend change detected |

## Agent Dispatch Rules

1. **Default:** Developer operates alone for single-file changes.
2. **Medium:** Developer + Reviewer for PRs touching >3 files.
3. **Large:** Developer + Reviewer + Judge + Red-Team-Local for cross-cutting changes.
4. **Epic:** Full team (all mandatory) + optional specialists for multi-repo phases.

## Sovereign Shield Conventions

- **Small repos** (< 5K LOC, single service): Developer handles everything; Reviewer runs on PR.
- **Large repos** (> 20K LOC, complex topology): Full mandatory team.
- **Cross-repo** (changes touch >1 repo): Red-Team-Architect activates automatically.
