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
| `live-system-operator.md` | Production operations | Deploy, hotfix, incident response |
| `metrics-onboarding.md` | Metrics setup & validation | Repo missing/broken metrics |
| `topology-validator.md` | Infra/code topology diff | AMQP/compose/ansible changes |
| `cert-monitor.md` | Certificate expiry tracking | Periodic or cert-related work |
| `health-verifier.md` | Post-deploy health checks | After deploy or verification |
| `scope-manager.md` | Context window management | Every plan/fix/feature |

## Optional Agents (loaded on demand)

| File | Role | Trigger |
|------|------|---------|
| `dba.md` | Database schema | DB migration detected |
| `qa.md` | Test strategy | Coverage < 80% or complex logic |
| `ui-ux-designer.md` | Design intelligence | Frontend change |
| `sync-agent.md` | Live ↔ workbench sync | Divergence detected |
| `budget-tracker.md` | Token budget tracking | Phase verification |

## Agent Dispatch Rules

1. **Default:** Developer operates alone for single-file changes.
2. **Medium:** Developer + Reviewer for PRs touching >3 files.
3. **Large:** Developer + Reviewer + Judge + Red-Team-Local for cross-cutting changes.
4. **Epic:** Full mandatory team + optional specialists for multi-repo phases.
5. **Incident:** Live-System-Operator + Developer for production hotfixes.

## Project Conventions

- **Small repos** (< 5K LOC, single service): Developer handles everything; Reviewer runs on PR.
- **Large repos** (> 20K LOC, complex topology): Full mandatory team.
- **Cross-repo** (changes touch >1 repo): Red-Team-Architect activates automatically.
- **Production incident:** Live-System-Operator leads; Developer backports.
