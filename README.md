# osEngineer

> An epic-level, multi-repo engineering skill for autonomous agents.  
> Built for Sovereign Shield. Reusable for any project.

## What Problem Does This Solve?

Most AI coding skills fail when work gets non-trivial because they lack:
- **Cross-repo awareness** — they operate on one repo at a time
- **Session survival** — they forget everything when the window closes
- **Spec enforcement** — they "vibe code" instead of following contracts
- **Verification** — they ship without proving the goal was met
- **Trust boundaries** — they have no circuit-breakers or human gates
- **Live-system discipline** — they confuse workbench edits with production changes
- **Continuous improvement** — they never learn from retrospectives

osEngineer implements all 7 layers required for platform-quality engineering.

## Architecture

```
osEngineer/
├── SKILL.md              # Manifest & entry point
├── AGENTS.md             # Agent catalog
├── planning/             # osEngineer phase lifecycle + templates
├── agents/               # Role-based agent definitions (14 total)
│   ├── developer.md              [MANDATORY]
│   ├── reviewer.md               [MANDATORY]
│   ├── judge.md                  [MANDATORY]
│   ├── red-team-local.md         [MANDATORY]
│   ├── red-team-architect.md     [MANDATORY]
│   ├── tech-writer.md            [MANDATORY]
│   ├── researcher.md             [MANDATORY]
│   ├── planner.md                [MANDATORY]
│   ├── live-system-operator.md   [MANDATORY]
│   ├── metrics-onboarding.md     [MANDATORY]
│   ├── topology-validator.md     [MANDATORY]
│   ├── cert-monitor.md           [MANDATORY]
│   ├── health-verifier.md        [MANDATORY]
│   ├── scope-manager.md          [MANDATORY]
│   ├── dba.md                    [OPTIONAL — compacted]
│   ├── qa.md                     [OPTIONAL — compacted]
│   ├── ui-ux-designer.md         [OPTIONAL — compacted]
│   ├── sync-agent.md             [OPTIONAL — compacted]
│   └── budget-tracker.md         [OPTIONAL — compacted]
├── commands/             # Slash commands (/osEngineer:*)
├── discovery/            # Project discovery, graphify, context7, env detection
├── specs/                # Spec-driven development templates
├── memory/               # Cross-session persistence + evolution counter
├── trust/                # Circuit-breakers, HITL gates, skill evolution
├── hooks/                # Automation hooks (post-commit, pre-commit)
├── live-system/          # Production runbooks
└── integrations/         # Optional MCP integrations (compacted)
```

## Installation

```bash
# Install on a specific project
./install.sh /path/to/project

# Install on all workbench repos
./install.sh --workbench

# Install global git hooks
./install.sh --global

# Install everywhere (workbench + global + /opt/sovereign-shield)
./install.sh --all
```

The install script is idempotent. It:
- Configures `git safe.directory` for all discovered repos
- Symlinks git hooks (graphify rebuild, schema lint)
- Creates `planning/active/` and `planning/completed/` directories
- Copies planning templates if missing

## Directory Structure

Every directory has a `README.md` (human-readable overview) and `INDEX.md` (bot-navigable file list):

```
osEngineer/
├── SKILL.md              # Skill manifest & entry point
├── README.md             # This file
├── AGENTS.md             # Agent catalog
├── install.sh            # Installation script
├── planning/             # osEngineer phase lifecycle + templates
│   ├── README.md
│   ├── INDEX.md
│   └── TEMPLATES/        # PHASE_PLAN, RESEARCH, VERIFICATION, RETROSPECTIVE, EVOLUTION_PROPOSAL
├── agents/               # Role-based agent definitions
│   ├── README.md
│   ├── INDEX.md
│   ├── developer.md              [MANDATORY]
│   ├── reviewer.md               [MANDATORY]
│   ├── judge.md                  [MANDATORY]
│   ├── red-team-local.md         [MANDATORY]
│   ├── red-team-architect.md     [MANDATORY]
│   ├── tech-writer.md            [MANDATORY]
│   ├── researcher.md             [MANDATORY]
│   ├── planner.md                [MANDATORY]
│   ├── live-system-operator.md   [MANDATORY]
│   ├── metrics-onboarding.md     [MANDATORY]
│   ├── topology-validator.md     [MANDATORY]
│   ├── cert-monitor.md           [MANDATORY]
│   ├── health-verifier.md        [MANDATORY]
│   ├── scope-manager.md          [MANDATORY]
│   ├── dba.md                    [OPTIONAL — compacted]
│   ├── qa.md                     [OPTIONAL — compacted]
│   ├── ui-ux-designer.md         [OPTIONAL — compacted]
│   ├── sync-agent.md             [OPTIONAL — compacted]
│   └── budget-tracker.md         [OPTIONAL — compacted]
├── commands/             # Slash commands (/osEngineer:*)
│   ├── README.md
│   ├── INDEX.md
│   ├── osEngineer-init.md
│   ├── osEngineer-plan.md
│   ├── osEngineer-fix.md
│   ├── osEngineer-feature.md
│   ├── osEngineer-investigate.md
│   ├── osEngineer-verify.md
│   └── osEngineer-evolve.md      # HITL skill improvement
├── discovery/            # Project discovery, graphify, context7, env detection
│   ├── README.md
│   ├── INDEX.md
│   ├── repo-discovery.md
│   ├── graphify-integration.md
│   ├── context7-integration.md
│   ├── adr-catalog-protocol.md
│   ├── execution-environment.md  # Terminal/IDE/web/daemon detection
│   └── sovereign-shield-repo-map.yml
├── specs/                # Spec-driven development
│   ├── README.md
│   ├── INDEX.md
│   ├── PROTOCOL.md
│   ├── TEMPLATES/
│   └── SCHEMAS/
├── memory/               # Cross-session persistence + evolution counter
│   ├── README.md
│   ├── INDEX.md
│   ├── PROTOCOL.md
│   ├── evolution-counter.yml     # Auto-nudge at 5 phases
│   ├── environment-profile.yml   # Detected execution environment
│   ├── retrospectives/
│   └── patterns/
├── trust/                # Circuit breakers, HITL gates, skill evolution
│   ├── README.md
│   ├── INDEX.md
│   ├── circuit-breakers.md
│   ├── hitl-gates.md
│   └── evolve-protocol.md        # HITL evolution protocol
├── hooks/                # Automation hooks
│   ├── README.md
│   ├── INDEX.md
│   ├── post-commit-graphify.sh
│   └── pre-commit-schema-lint.sh
├── live-system/          # Production runbooks
│   ├── README.md
│   ├── INDEX.md
│   ├── restart-service.md
│   ├── vault-unseal.md
│   ├── rabbitmq-recovery.md
│   ├── cert-rotation.md
│   └── docker-health-check.md
└── integrations/         # Optional MCP integrations (compacted)
    ├── README.md
    ├── INDEX.md
    ├── confluence-mcp.md
    ├── vault-mcp.md
    ├── playwright-mcp.md
    └── openspace-mcp.md
```

## Usage

### 1. Initialize on a project

```
/osEngineer:init /path/to/project
```

This runs the discovery protocol:
1. **Detects execution environment** — terminal server, IDE, web, or daemon
2. Scans for repos
3. Reads ADR catalogs
4. Loads existing graphs
5. Generates `RESEARCH.md`

### 2. Plan a phase

```
/osEngineer:plan "Implement ADR-033 retry-with-backoff for fleet executor"
```

Generates `PHASE_PLAN.md` with numbered tasks, deps, acceptance criteria, and token estimates.

### 3. Execute

```
/osEngineer:fix OSP-123
/osEngineer:feature OSP-124
```

Dispatches the developer agent. Each task = atomic commit. Rollback path documented.

### 4. Verify

```
/osEngineer:verify phase-3
```

Runs verification protocol: tests, e2e tracer bullets, cost recalibration.

### 5. Evolve (HITL skill improvement)

```
/osEngineer:evolve
```

Triggers the skill evolution protocol. Every 5 completed phases, osEngineer auto-nudges you with 3 improvement options. You select one, skip, or propose your own. Accepted proposals are appended to `memory/patterns/`.

## Key Principles

1. **Project-agnostic core, project-specific overlay** — The skill discovers your project structure; it is not hardcoded to Sovereign Shield.
2. **Mandatory agents are lean** — They load fast and stay in context.
3. **Optional agents are compacted** — They only load when explicitly invoked, avoiding context waste.
4. **Spec-first, test-first, docs-first** — No code without a contract. No commit without a test. No merge without docs.
5. **Graphify is the source of truth** — For architectural questions, query the graph before grepping.
6. **Token budgets are hard rules** — Exceed 150% of estimate → abort with structured handoff.
7. **Live system is read-only for source code** — Fixes authored in workbench, submitted via PR. Hotfixes on live require immediate backport.
8. **Environment-aware execution** — Behavior adapts to terminal server, IDE, web, or autonomous daemon contexts.
9. **Continuous evolution via HITL** — Every 5 phases, the agent asks: "How can I serve you better?"

## External Dependencies

osEngineer is **standalone** but integrates with these tools when available:
- **Graphify** — AST + LLM knowledge graphs
- **Context7** — Code documentation MCP
- **AgentMemory** — Persistent memory backend
- **GitHub CLI (`gh`)** — PR creation, issue tracking
- **Docker** — Local test environments

## Contributing

This skill evolves via retrospectives and the HITL evolution protocol. After each phase, the developer agent appends findings to `memory/retrospectives/`. The judge agent promotes validated patterns to the pattern library. Use `/osEngineer:evolve` anytime to propose improvements.
