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
| **Live System Operator** | Docker ops, hotfixes, log inspection, AMQP/Vault checks | `agents/live-system-operator.md` |
| **Metrics Onboarding** | promauto setup, test generation, endpoint wiring | `agents/metrics-onboarding.md` |
| **Topology Validator** | Code vs ansible diff, schema consistency | `agents/topology-validator.md` |
| **Cert Monitor** | Expiry tracking, renewal scripts, ADR-021 compliance | `agents/cert-monitor.md` |
| **Health Verifier** | Container health, metrics endpoints, AMQP consumers | `agents/health-verifier.md` |
| **Scope Manager** | Context window optimization, repo pruning per phase | `agents/scope-manager.md` |

## Optional Agents (compacted; loaded on demand)

| Agent | Role | File | Trigger |
|-------|------|------|---------|
| **DBA** | Schema design, migrations, query optimization | `agents/dba.md` | Database change detected |
| **QA** | Test strategy, edge-case analysis, load testing | `agents/qa.md` | Test coverage < 80% |
| **UI/UX Designer** | Design intelligence, accessibility, component systems | `agents/ui-ux-designer.md` | Frontend change detected |
| **Sync Agent** | Live ↔ workbench synchronization, backport tracking | `agents/sync-agent.md` | Hotfix on live system |
| **Budget Tracker** | Token spend tracking, cost alerting | `agents/budget-tracker.md` | Cost threshold exceeded |

## Agent Dispatch Rules

1. **Default:** Developer operates alone for single-file changes.
2. **Medium:** Developer + Reviewer for PRs touching >3 files.
3. **Large:** Developer + Reviewer + Judge + Red-Team-Local for cross-cutting changes.
4. **Epic:** Full team (all mandatory) + optional specialists for multi-repo phases.
5. **Live System:** Live-System-Operator + Health-Verifier + Sync-Agent for production incidents.
6. **Metrics Rollout:** Metrics-Onboarding + Topology-Validator for observability work.

## Project Conventions

- **Small repos** (< 5K LOC, single service): Developer handles everything; Reviewer runs on PR.
- **Large repos** (> 20K LOC, complex topology): Full mandatory team.
- **Cross-repo** (changes touch >1 repo): Red-Team-Architect activates automatically.
- **Live system ops** (docker, vault, certs): Live-System-Operator takes lead; Developer never edits source on `/opt/<project>` directly.
- **Context pressure** (>20 repos in workbench): Scope-Manager prunes repo list per phase goal.
