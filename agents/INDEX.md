# Agent Catalog — agents/INDEX.md

osEngineer uses a **role-based agent team** sized to repo complexity. For small repos, roles collapse into the developer. For large cross-repo work, all roles fire in sequence. Two scope-level orchestrators (architect, verifier) sit above the implementation roles.

This file is the canonical agent catalog. It replaces the previous root-level `AGENTS.md` (deleted in osEngineer 0.2.0 P2 to free the convention for per-repo `AGENTS.md` manifests, which now own that filename).

## Layout convention (P6.2)

Every agent lives in its own directory:

```
agents/<role>/
  AGENT.md            # lean entry point (frontmatter + mandate + protocol overview)
  references/         # heavyweight material loaded on demand
    <topic>.md
```

`AGENT.md` is what gets copied into target repos at `<repo>/.claude/agents/<role>.md` by `install.sh` (Claude Code expects flat `.md` files in `.claude/agents/`). The `references/` subdirectory stays in the osEngineer skill home; the LLM follows the relative links inside `AGENT.md` when it needs deeper material. Smaller agents may have no `references/` at all — their entire body fits cleanly in `AGENT.md`.

## Orchestration agents (always active in osEngineer-initialised repos)

| Agent | Role | Entry |
|-------|------|------|
| **Architect** | Per-scope (workbench / repo) router; reads AGENTS.md, dispatches to teams, owns handoff filesystem | [architect/AGENT.md](architect/AGENT.md) |
| **Verifier** | Phase verification gate; produces VERIFICATION.md; independent of developer | [verifier/AGENT.md](verifier/AGENT.md) |

## Mandatory implementation agents (always loaded)

| Agent | Role | Entry |
|-------|------|------|
| **Developer** | Primary implementer; writes code, tests, commits | [developer/AGENT.md](developer/AGENT.md) |
| **Reviewer** | Per-PR code review; style, correctness, test coverage | [reviewer/AGENT.md](reviewer/AGENT.md) |
| **Judge** | Merge gate; architectural alignment, ADR compliance | [judge/AGENT.md](judge/AGENT.md) |
| **Red Team (Local)** | Per-PR security scan; SAST, secrets, allowlist | [red-team-local/AGENT.md](red-team-local/AGENT.md) |
| **Red Team (Architect)** | Cross-repo invariant checks; topology drift, ADR violations | [red-team-architect/AGENT.md](red-team-architect/AGENT.md) |
| **Tech Writer** | Contracts, docs, OpenAPI/AMQP message contracts, ADR amendments | [tech-writer/AGENT.md](tech-writer/AGENT.md) |
| **Researcher** | Discovery, graph queries, ADR catalog read | [researcher/AGENT.md](researcher/AGENT.md) |
| **Planner** | Phase breakdown, deps, token estimates, risk flags | [planner/AGENT.md](planner/AGENT.md) |
| **Live System Operator** | Docker ops, hotfixes, log inspection, AMQP/Vault checks | [live-system-operator/AGENT.md](live-system-operator/AGENT.md) |
| **Metrics Onboarding** | promauto setup, test generation, endpoint wiring | [metrics-onboarding/AGENT.md](metrics-onboarding/AGENT.md) |
| **Topology Validator** | Code vs ansible diff, schema consistency | [topology-validator/AGENT.md](topology-validator/AGENT.md) |
| **Cert Monitor** | Expiry tracking, renewal scripts, ADR-021 compliance | [cert-monitor/AGENT.md](cert-monitor/AGENT.md) |
| **Health Verifier** | Container health, metrics endpoints, AMQP consumers | [health-verifier/AGENT.md](health-verifier/AGENT.md) |
| **Scope Manager** | Context window optimization, repo pruning per phase | [scope-manager/AGENT.md](scope-manager/AGENT.md) |
| **Sandbox Provisioner** | Compose-based sandbox provisioning + smoke checks | [sandbox-provisioner/AGENT.md](sandbox-provisioner/AGENT.md) |

## Optional implementation agents (compacted; loaded on demand)

| Agent | Role | Entry | Trigger |
|-------|------|------|---------|
| **DBA** | Schema design, migrations, query optimization | [dba/AGENT.md](dba/AGENT.md) | Database change detected |
| **QA** | Test strategy, edge-case analysis, load testing | [qa/AGENT.md](qa/AGENT.md) | Test coverage < 80% |
| **UI/UX Designer** | Design intelligence, accessibility, component systems | [ui-ux-designer/AGENT.md](ui-ux-designer/AGENT.md) | Frontend change detected |
| **Sync Agent** | Live ↔ workbench synchronization, backport tracking | [sync-agent/AGENT.md](sync-agent/AGENT.md) | Hotfix on live system |
| **Budget Tracker** | Token spend tracking, cost alerting | [budget-tracker/AGENT.md](budget-tracker/AGENT.md) | Cost threshold exceeded |

## Agent dispatch rules

1. **Default:** Developer operates alone for single-file changes.
2. **Medium:** Developer + Reviewer for PRs touching >3 files.
3. **Large:** Developer + Reviewer + Judge + Red-Team-Local for cross-cutting changes.
4. **Epic:** Full team (all mandatory) + optional specialists for multi-repo phases.
5. **Live System:** Live-System-Operator + Health-Verifier + Sync-Agent for production incidents.
6. **Metrics Rollout:** Metrics-Onboarding + Topology-Validator for observability work.
7. **Verification:** Verifier fires before every `verify → accepted` transition.

In osEngineer-initialised repos with team manifests (P3+), the architect agent reads `<repo>/AGENTS.md` and routes per-team rather than per-role.

## Project-Specific Conventions

- **Small repos** (<5K LOC, single service): Developer handles everything; Reviewer runs on PR.
- **Large repos** (>20K LOC, complex topology): Full mandatory team.
- **Cross-repo** (changes touch >1 repo): Red-Team-Architect activates automatically.
- **Live system ops** (docker, vault, certs): Live-System-Operator takes lead; Developer never edits source on the live system directly (enforced by `osEngineer-pre-edit-guard.js`).
- **Context pressure** (>20 repos in workbench): Scope-Manager prunes repo list per phase goal.

## How agents are delivered

`install.sh` copies `agents/<role>/AGENT.md` from the osEngineer skill home into `<repo>/.claude/agents/<role>.md` for every entry in the `MANDATORY_AGENTS` array. Optional agents are not auto-copied — they're referenced in this INDEX and loaded on demand when the user invokes `/Task <agent-name>`.

The `agents/<role>/references/` subdirectories stay in the osEngineer skill home. They are *not* copied into target repos to keep the per-repo footprint lean. The LLM follows the relative links inside `AGENT.md` (e.g. `[tdd-protocol](references/tdd-protocol.md)`) when it needs deeper material, resolving them relative to the agent file's location in the source skill.
