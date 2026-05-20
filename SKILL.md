# osEngineer — Epic-Level Multi-Repo Engineering Skill

**Version:** 0.1.0  
**Scope:** Cross-repo, cross-SDLC, cross-session engineering  
**Project-Agnostic:** Yes — discovers repos, ADRs, and topology from any project root  
**Primary Target:** Sovereign Shield (28 repos) as reference implementation  
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

- `agents/developer.md` — primary implementation agent
- `agents/reviewer.md` — code review agent
- `agents/judge.md` — merge gate / architectural judge
- `agents/red-team-local.md` — per-PR security scan
- `agents/red-team-architect.md` — cross-repo invariant checks
- `agents/tech-writer.md` — docs & contract authoring
- `agents/researcher.md` — discovery & graph query agent
- `agents/planner.md` — phase planning agent
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

## Sovereign Shield Reference Mapping

For Sovereign Shield specifically, osEngineer knows these repo categories:

| Category | Repos |
|----------|-------|
| **Management Layer** | `ola-management-strategist`, `ola-management-supervisor`, `ola-management-guardian`, `ola-management-metronome`, `ola-management-persist`, `ola-management-registry`, `ola-management-accountant`, `ola-management-witness`, `ola-management-operator`, `ola-management-oracle`, `ola-management-gatekeeper`, `ola-management-wand`, `ola-management-scribe` |
| **Fleet Layer** | `ola-fleet-chameleon`, `ola-fleet-executor`, `ola-fleet-executor-core`, `ola-fleet-ex-hermes`, `ola-fleet-ex-jcode`, `ola-fleet-ex-opencode`, `ola-fleet-routine` |
| **Host / Config** | `ola-host-engineer-config`, `ola-management-wizard-config`, `ola-management-universal-agent` |
| **Observability** | `OS-MDashboard`, `OpenSpace` |
| **Meta / Install** | `sovereign-shield-install-guide`, `sovereign-shield-backup`, `fleet-backup` |
| **Shared** | `ola-shared-utility` |

*(This mapping is loaded from `discovery/sovereign-shield-repo-map.yml` when the project is identified as Sovereign Shield.)*
