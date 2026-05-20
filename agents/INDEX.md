# Agent Catalog — agents/INDEX.md

osEngineer uses a **role-based agent team** sized to repo complexity. For small repos, roles collapse into the developer. For large cross-repo work, all roles fire in sequence. Two scope-level orchestrators (architect, verifier) sit above the implementation roles.

This file is the canonical agent catalog. It replaces the previous root-level `AGENTS.md` (deleted in osEngineer 0.2.0 P2 to free the convention for per-repo `AGENTS.md` manifests, which now own that filename).

## Orchestration agents (always active in osEngineer-initialised repos)

| Agent | Role | File |
|-------|------|------|
| **Architect** | Per-scope (workbench / repo) router; reads AGENTS.md, dispatches to teams, owns handoff filesystem | [architect.md](architect.md) |
| **Verifier** | Phase verification gate; produces VERIFICATION.md; independent of developer | [verifier.md](verifier.md) |

## Mandatory implementation agents (always loaded)

| Agent | Role | File |
|-------|------|------|
| **Developer** | Primary implementer; writes code, tests, commits | [developer.md](developer.md) |
| **Reviewer** | Per-PR code review; style, correctness, test coverage | [reviewer.md](reviewer.md) |
| **Judge** | Merge gate; architectural alignment, ADR compliance | [judge.md](judge.md) |
| **Red Team (Local)** | Per-PR security scan; SAST, secrets, allowlist | [red-team-local.md](red-team-local.md) |
| **Red Team (Architect)** | Cross-repo invariant checks; topology drift, ADR violations | [red-team-architect.md](red-team-architect.md) |
| **Tech Writer** | Contracts, docs, OpenAPI/AMQP message contracts, ADR amendments | [tech-writer.md](tech-writer.md) |
| **Researcher** | Discovery, graph queries, ADR catalog read | [researcher.md](researcher.md) |
| **Planner** | Phase breakdown, deps, token estimates, risk flags | [planner.md](planner.md) |
| **Live System Operator** | Docker ops, hotfixes, log inspection, AMQP/Vault checks | [live-system-operator.md](live-system-operator.md) |
| **Metrics Onboarding** | promauto setup, test generation, endpoint wiring | [metrics-onboarding.md](metrics-onboarding.md) |
| **Topology Validator** | Code vs ansible diff, schema consistency | [topology-validator.md](topology-validator.md) |
| **Cert Monitor** | Expiry tracking, renewal scripts, ADR-021 compliance | [cert-monitor.md](cert-monitor.md) |
| **Health Verifier** | Container health, metrics endpoints, AMQP consumers | [health-verifier.md](health-verifier.md) |
| **Scope Manager** | Context window optimization, repo pruning per phase | [scope-manager.md](scope-manager.md) |

## Optional implementation agents (compacted; loaded on demand)

| Agent | Role | File | Trigger |
|-------|------|------|---------|
| **DBA** | Schema design, migrations, query optimization | [dba.md](dba.md) | Database change detected |
| **QA** | Test strategy, edge-case analysis, load testing | [qa.md](qa.md) | Test coverage < 80% |
| **UI/UX Designer** | Design intelligence, accessibility, component systems | [ui-ux-designer.md](ui-ux-designer.md) | Frontend change detected |
| **Sync Agent** | Live ↔ workbench synchronization, backport tracking | [sync-agent.md](sync-agent.md) | Hotfix on live system |
| **Budget Tracker** | Token spend tracking, cost alerting | [budget-tracker.md](budget-tracker.md) | Cost threshold exceeded |

## Agent dispatch rules

1. **Default:** Developer operates alone for single-file changes.
2. **Medium:** Developer + Reviewer for PRs touching >3 files.
3. **Large:** Developer + Reviewer + Judge + Red-Team-Local for cross-cutting changes.
4. **Epic:** Full team (all mandatory) + optional specialists for multi-repo phases.
5. **Live System:** Live-System-Operator + Health-Verifier + Sync-Agent for production incidents.
6. **Metrics Rollout:** Metrics-Onboarding + Topology-Validator for observability work.
7. **Verification:** Verifier fires before every `verify → accepted` transition.

In osEngineer-initialised repos with team manifests (P3+), the architect agent reads `<repo>/AGENTS.md` and routes per-team rather than per-role.

## Observer Shield conventions

- **Small repos** (<5K LOC, single service): Developer handles everything; Reviewer runs on PR.
- **Large repos** (>20K LOC, complex topology): Full mandatory team.
- **Cross-repo** (changes touch >1 repo): Red-Team-Architect activates automatically.
- **Live system ops** (docker, vault, certs): Live-System-Operator takes lead; Developer never edits source on `/opt/sovereign-shield` directly (enforced by `osEngineer-pre-edit-guard.js`).
- **Context pressure** (>20 repos in workbench): Scope-Manager prunes repo list per phase goal.

## How agents are delivered

Each agent file lives in `osEngineer/agents/*.md` and is **copied** into target repos at `<repo>/.claude/agents/*.md` by `install.sh`. Mandatory agents are always copied. Optional agents are referenced by INDEX but loaded on-demand (via the user invoking `/Task <agent-name>`).
