# agents/

Agent role definitions for the osEngineer skill team.

Each `.md` file defines a role: mandate, protocol, output format, and trigger conditions.

## Mandatory Agents (always loaded)

These agents form the core team. For small repos, the developer handles everything.
For large cross-repo work, all roles fire in sequence.

| File | Role | When to use |
|------|------|-------------|
| `developer.md` | Primary implementer | Every execution task |
| `reviewer.md` | Per-PR code review | Every PR |
| `judge.md` | Merge gate / architecture | Every merge |
| `red-team-local.md` | Per-PR security scan | Every PR |
| `red-team-architect.md` | Cross-repo invariant checks | Multi-repo changes |
| `tech-writer.md` | Contracts & docs | Contract surface changes |
| `researcher.md` | Discovery & graph queries | New project or unknown codebase |
| `planner.md` | Phase planning | Every phase |

## Optional Agents (loaded on demand)

| File | Role | Trigger |
|------|------|---------|
| `dba.md` | Database schema | DB migration detected |
| `qa.md` | Test strategy | Coverage < 80% or complex logic |
| `ui-ux-designer.md` | Design intelligence | Frontend change |
