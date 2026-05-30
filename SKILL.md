# osEngineer — Epic-Level Multi-Repo Engineering Skill

**Version:** 0.2.0  
**Scope:** Cross-repo, cross-SDLC, cross-session engineering  
**Project-Agnostic:** Yes — discovers repos, ADRs, and topology from any project root  
**Primary Target:** Any multi-repo project (ships with a Sovereign Shield reference overlay in `examples/`)  
**License:** MIT

---

## What is osEngineer?

osEngineer is a **platform-quality engineering skill** that operates across multiple repositories, SDLC stages, and sessions. It is not a one-shot helper. It implements all 7 architectural layers required for non-trivial work:

| # | Layer | Artifact |
|---|-------|----------|
| 1 | **Discovery / Research** | `RESEARCH.md`, graph extraction, ADR catalog read |
| 2 | **Planning** | `PHASE_PLAN.md` with task numbering, deps, acceptance criteria, token estimates |
| 3 | **Execution** | Atomic commits, rollback paths, branch-per-phase, PR-per-phase |
| 4 | **Verification** | `VERIFICATION.md`, tracer-bullet e2e runs, cost recalibration |
| 5 | **Knowledge Persistence** | Persistent graph (`graphify-out/`), auto-memory, ADRs, `CLAUDE.md` per repo |
| 6 | **Trust Boundary** | HITL gate (PR merge), 4-part plans on hard rules, circuit-breakers on token budgets |
| 7 | **Evolution** | Retrospectives, pattern library, prompt-template version control |

---

## Quick Start

1. **Initialize:** Run `/osEngineer:init /path/to/project` to detect environment and discover repos.
2. **Discovery:** Run `/osEngineer:investigate <symptom>` to understand the current state.
3. **Plan:** Run `/osEngineer:plan <goal>` to generate a `PHASE_PLAN.md`.
4. **Execute:** Run `/osEngineer:fix <ticket>` or `/osEngineer:feature <ticket>` to execute a planned phase.
5. **Verify:** Run `/osEngineer:verify <phase>` to validate deliverables.
6. **Evolve:** Run `/osEngineer:evolve` to improve the skill itself (HITL, auto-nudge at 5 phases).
7. **Explain:** Run `/osEngineer:explain [topic]` to learn how osEngineer works, what artifacts it creates, and which commands are available.

---

## Mandatory vs Optional Components

### Mandatory (loaded into context by default)

- `agents/architect.md` — repo-level orchestration & team coordination
- `agents/verifier.md` — phase verification & acceptance gate
- `agents/developer.md` — primary implementation agent
- `agents/reviewer.md` — code review agent
- `agents/judge.md` — merge gate / architectural judge
- `agents/red-team-local.md` — per-PR security scan
- `agents/red-team-architect.md` — cross-repo invariant checks
- `agents/tech-writer.md` — docs & contract authoring
- `agents/researcher.md` — discovery & graph query agent
- `agents/planner.md` — phase planning agent
- `agents/live-system-operator.md` — Docker ops, hotfixes, log inspection
- `agents/metrics-onboarding.md` — promauto setup, test generation, endpoint wiring
- `agents/topology-validator.md` — code vs ansible drift, schema consistency
- `agents/cert-monitor.md` — expiry tracking, renewal scripts
- `agents/health-verifier.md` — container health, metrics endpoints
- `agents/scope-manager.md` — context window optimization for large workbenches
- `planning/PROTOCOL.md` — osEngineer phase lifecycle
- `discovery/repo-discovery.md` — auto-discover project repos
- `trust/circuit-breakers.md` — token budget & abort rules
- `trust/hitl-gates.md` — human-in-the-loop protocol

### Optional (compacted; loaded only when explicitly invoked)

- `agents/dba.md` — database schema agent
- `agents/qa.md` — testing specialist
- `agents/ui-ux-designer.md` — UI/UX reasoning rules
- `agents/sync-agent.md` — live ↔ workbench synchronization
- `agents/budget-tracker.md` — token spend tracking
- `integrations/confluence-mcp.md` — Atlassian Confluence MCP
- `integrations/vault-mcp.md` — HashiCorp Vault MCP
- `integrations/playwright-mcp.md` — browser testing MCP
- `integrations/openspace-mcp.md` — OpenSpace MCP

---

## External Skill Integrations

osEngineer integrates patterns from these external skills but is **completely standalone**:

| External Skill | Role in osEngineer | Location |
|----------------|-------------------|----------|
| **GSD** (get-shit-done) | Phase lifecycle protocol, planning templates, slash commands | `planning/`, `commands/` |
| **Context7** | Code documentation MCP, rules engine | `discovery/context7-integration.md` |
| **AgentMemory** | Session recovery, cross-session context, memory backend protocol | `memory/` |
| **Spec Kit** | Spec-driven development templates, contract schemas | `specs/` |
| **UI UX Pro Max** | Optional UI/UX reasoning rules (compacted) | `agents/ui-ux-designer.md` |

---

## Project Discovery Protocol

When osEngineer starts on a new project:

1. **Detect execution environment:** `discovery/execution-environment.md` probes terminal/IDE/web/daemon and ASKS THE USER to confirm. NEVER assume.
2. **Scan for repos:** `discovery/repo-discovery.md` scans the project root for `.git` directories.
3. **Read ADR catalog:** Looks for `docs/adr/`, `.claude/adr-catalog/`, or `META/` ADR indices.
4. **Run Graphify:** If `graphify-out/` exists, loads the graph; if not, suggests building it.
5. **Read CLAUDE.md files:** Per-repo `.claude/CLAUDE.md` or `AGENTS.md` files are ingested.
6. **Build repo map:** Creates a `RESEARCH.md` with repo topology, dependencies, and classification.

---

## Project Discovery

osEngineer does not hardcode any repo list. During `install.sh` or `/osEngineer:init`, the skill:

1. **Asks** for the project name.
2. **Discovers** repos by scanning for `.git` directories.
3. **Confirms** the discovered list with the user (add/remove/rename).
4. **Identifies** (or creates) the META repo that holds ADRs and architecture docs.
5. **Stores** the topology in `.osengineer/workbench-config.yml`.

See `examples/sovereign-shield/` for a reference implementation of how a real 28-repo platform documents its conventions, runbooks, and patterns.
