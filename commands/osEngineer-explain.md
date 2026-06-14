---
name: osEngineer:explain
description: >-
  Built-in self-documentation — prints the osEngineer overview or a
  scoped topic (artifacts, commands, lifecycle, agents, install,
  trust) to chat. Use when a user asks how osEngineer works, what
  files it creates, what command to run next, or which agent owns a
  responsibility. Don't use to investigate a codebase symptom (use
  /osEngineer:investigate); don't use to plan or execute work; don't
  use to modify any artifact — explain is strictly read-only output.
phase_allowed: [idle, discuss, plan, execute, verify, accepted]
---

# /osEngineer:explain

**Syntax:** `/osEngineer:explain [topic]`  
**Role:** Meta-agent (self-documentation)  
**Output:** Markdown explanation printed to chat

---

## Description

Explains how osEngineer works, what artifacts it creates, and how to use it. This is the built-in help system. If no topic is given, prints the full overview.

## Topics

| Topic | Description |
|-------|-------------|
| (none) | Full overview — artifacts, commands, lifecycle |
| `artifacts` | Files and directories created by osEngineer |
| `commands` | All slash commands and when to use them |
| `lifecycle` | How a phase flows from plan to verify to evolve |
| `agents` | The agent team and dispatch rules |
| `install` | What `install.sh` does and how to uninstall |
| `trust` | Circuit breakers, HITL gates, and safety rules |

---

## Full Overview (default output)

### What is osEngineer?

osEngineer is a role-based, multi-repo engineering skill for AI agents. It breaks work into **phases**, each with a plan, execution, verification, and retrospective. A team of specialized agents handles different aspects of engineering work.

### Artifacts Created

When osEngineer initializes on a project (`/osEngineer:init`), it creates or discovers:

```
<project-root>/
├── planning/
│   ├── active/
│   │   └── RESEARCH.md           # Auto-generated: repo topology, ADRs, graph summary
│   └── completed/                # Finished phases are moved here
│   └── TEMPLATES/                # Copied from osEngineer if missing
│       ├── PHASE_PLAN.md         # Task list with deps, acceptance criteria, token budget
│       ├── RESEARCH.md           # Template for discovery output
│       ├── VERIFICATION.md       # Test results, acceptance check, lessons
│       ├── RETROSPECTIVE.md      # What worked, what didn't, pattern extraction
│       └── EVOLUTION_PROPOSAL.md # Skill improvement proposal (HITL)
├── .claude/
│   └── settings.json             # Zeroclaw hook config (graphify PreToolUse)
├── graphify-out/                 # Existing or suggested; source of truth for architecture
└── .git/hooks/                   # Symlinked: post-commit-graphify, pre-commit-schema-lint
```

During phase execution, osEngineer writes:
- `planning/active/PHASE_PLAN.md` — The plan for the current phase
- `planning/active/VERIFICATION.md` — Verification results after `/osEngineer:verify`
- `planning/completed/<phase-name>/` — Archived phase artifacts after completion
- `memory/retrospectives/<date>-<phase>.md` — Findings appended by the developer agent
- `memory/patterns/<pattern-name>.md` — Promoted patterns by the judge agent

### Slash Commands

| Command | When to Use |
|---------|-------------|
| `/osEngineer:init <path>` | First time on a project. Discovers repos, ADRs, graphs. |
| `/osEngineer:plan "<goal>"` | Start a new phase. Generates PHASE_PLAN.md. |
| `/osEngineer:fix <ticket>` | Execute a bug fix from an existing plan. |
| `/osEngineer:feature <ticket>` | Execute a feature from an existing plan. |
| `/osEngineer:investigate "<symptom>"` | Research an error or unknown behavior. |
| `/osEngineer:verify <phase-id>` | Run tests and acceptance criteria after execution. |
| `/osEngineer:evolve` | Propose skill improvements (HITL). Auto-nudge every 5 phases. |
| `/osEngineer:explain [topic]` | Get help on how osEngineer works. |

### Skill Lifecycle

A typical engagement flows through these states:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   INIT      │────▶│   PLAN      │────▶│  EXECUTE    │
│  (discover) │     │  (breakdown)│     │ (developer) │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
┌─────────────┐     ┌─────────────┐     ┌──────▼──────┐
│   EVOLVE    │◀────│  RETRO      │◀────│   VERIFY    │
│  (improve)  │     │  (learn)    │     │  (prove)    │
└─────────────┘     └─────────────┘     └─────────────┘
```

1. **Init** — Discovery protocol runs. Environment detected (you confirm). Repo map built.
2. **Plan** — Planner agent breaks the goal into numbered tasks with deps, risks, and token budgets.
3. **Execute** — Developer agent works task-by-task. Each task = atomic commit. Rollback path documented.
4. **Verify** — Tests run, acceptance criteria checked, e2e tracer bullets fired. If fail → back to Execute.
5. **Retrospective** — Developer writes findings. Judge promotes validated patterns to `memory/patterns/`.
6. **Evolve** — Every 5 phases, auto-nudge asks: "How can I serve you better?" You pick an improvement or skip.

### Agent Dispatch

Not all agents run for every task. The dispatch rules:

- **Single file change** → Developer only
- **PR touching >3 files** → Developer + Reviewer
- **Cross-cutting change** → Developer + Reviewer + Judge + Red-Team-Local
- **Multi-repo phase** → Full mandatory team + optional specialists
- **Live system incident** → Live-System-Operator + Health-Verifier + Sync-Agent
- **Metrics rollout** → Metrics-Onboarding + Topology-Validator

### Safety Rules

- **Token budget hard limit:** Exceed 150% of estimate → abort with structured handoff.
- **Live system read-only:** Never edit source on the live system directly. Workbench → PR.
- **Circuit breakers:** 3 consecutive failures on same agent → escalate to human.
- **HITL gates:** Deployments, schema changes, and auth modifications require explicit approval.

---

## Example

```
/osEngineer:explain artifacts
```

Output: Shows only the artifacts section.

```
/osEngineer:explain
```

Output: Shows this entire document.
