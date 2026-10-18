# osEngineer

> An epic-level, multi-repo engineering skill for autonomous AI agents.  
> Project-agnostic multi-repo engineering skill. Ships with a [Sovereign Shield](https://github.com/andreas2301/sovereign-shield-install-guide) reference overlay in `examples/`.

## What Problem Does This Solve?

Most AI coding assistants fail when work gets non-trivial because they lack:

- **Cross-repo awareness** — they operate on one repo at a time
- **Session survival** — they forget everything when the window closes
- **Spec enforcement** — they "vibe code" instead of following contracts
- **Verification** — they ship without proving the goal was met
- **Trust boundaries** — they have no circuit-breakers or human gates
- **Live-system discipline** — they confuse workbench edits with production changes
- **Continuous improvement** — they never learn from retrospectives

osEngineer implements all 7 layers required for platform-quality engineering.

## Features

| Layer | Feature | File |
|-------|---------|------|
| **Planning** | Phase lifecycle with token budgets, risk flags, rollback paths | [`planning/`](planning/) |
| **Agents** | 16 mandatory + 6 optional role-based agents | [`agents/`](agents/) |
| **Commands** | 7 slash commands including HITL evolution | [`commands/`](commands/) |
| **Discovery** | Auto-discovers repos, ADRs, graphs, execution environment | [`discovery/`](discovery/) |
| **Specs** | Spec-driven development with JSON schemas | [`specs/`](specs/) |
| **Memory** | Cross-session persistence + evolution counter | [`memory/`](memory/) |
| **Trust** | Circuit breakers, HITL gates, skill evolution protocol | [`trust/`](trust/) |
| **Live System** | Production runbooks for Docker, Vault, RabbitMQ, certs | [`live-system/`](live-system/) |
| **Hooks** | Post-commit graphify rebuild, pre-commit schema lint | [`hooks/`](hooks/) |
| **Integrations** | Optional MCP integrations (Confluence, Vault, Playwright, OpenSpace) | [`integrations/`](integrations/) |

## Quick Start

```bash
# Clone the skill
git clone https://github.com/andreas2301/osEngineer.git
cd osEngineer

# Install on a specific project
./install.sh /path/to/your/project

# Or install on all repos in your workbench
./install.sh --workbench

# Or install everywhere
./install.sh --all
```

The install script is idempotent. It configures `git safe.directory`, symlinks hooks, creates planning directories, and wires zeroclaw repo settings.

### Supported harnesses: Claude Code, Kimi Code, Codex CLI

Pick the harnesses with `RUNTIMES` (space-separated, default `claude`) or the interactive multi-harness menu:

```bash
RUNTIMES="claude kimi codex" ./install.sh /path/to/your/project
```

| | Claude Code (`claude`) | Kimi Code (`kimi`) | Codex CLI (`codex`) |
|---|---|---|---|
| Hook wiring | `.claude/settings.json` (per repo) | `$KIMI_CODE_HOME/config.toml` (machine-global, ledger in `~/.osengineer/repos.json`) | `.codex/hooks.json` (per repo), each guard run through `hooks/lib/codex_hook.py` |
| Guards wired | prompt, edit, read-before-edit, Bash, post-tool, session-start, statusline | prompt, edit, read-before-edit, Bash | prompt, edit (`apply_patch` split per file), Bash, session-start |
| Team context | root `AGENTS.md`, `CLAUDE.md`, `.claude/agents/*.md` | `.kimi-code/AGENTS.md` | root `AGENTS.md` (read natively) |
| Commands | `.claude/commands/osEngineer/<verb>.md` | `.kimi-code/skills/<verb>/SKILL.md` | `.agents/skills/<verb>/SKILL.md` |

Codex limits:
- Codex runs project hooks only after you trust the project and then each osEngineer hook in `/hooks`. Trust is recorded per command hash, so after an upgrade that changes a command you must trust it again. Until then, Codex enforces nothing locally, and only the git hooks (`commit-msg`, `pre-commit`) and the CI gate (`.github/workflows/osengineer-gate.yml`) apply. `install.sh` prints a warning about this.
- Codex has no statusline and no context-usage bridge, so the post-tool context monitor is not wired. The read-before-edit advisory is not wired either.
- Codex custom agents are TOML files, so no agent role files are copied to `.codex/agents/`. Codex gets the roles through `AGENTS.md`.
- Hosted Codex tools such as web search never reach `PreToolUse`.

`./uninstall.sh` removes only the osEngineer handlers and skills. It keeps foreign hooks and skills you have edited.

### Relocating the checkout: `OSENGINEER_HOME`

`OSENGINEER_HOME` points at the osEngineer skill checkout. The per-repo launcher installed at `.osengineer/bin/osengineer` honours it, preferring the variable over the checkout path baked in at install time, so setting it is how CI runners and relocated checkouts work without re-running `install.sh`:

```bash
export OSENGINEER_HOME=/path/to/osEngineer
```

To remove osEngineer wiring from a project:

```bash
./uninstall.sh /path/to/your/project
./uninstall.sh --workbench
./uninstall.sh --global
./uninstall.sh --all
```

The uninstall script asks before deleting planning directories that may contain your work.

## Usage

### Initialize on a project

```
/osEngineer:init /path/to/project
```

Runs the discovery protocol:
1. **Detects execution environment** — terminal server, IDE, web, or daemon (asks you to confirm)
2. Scans for repos
3. Reads ADR catalogs
4. Loads existing graphs
5. Generates `RESEARCH.md`

### Plan a phase

```
/osEngineer:plan "Implement retry-with-backoff for fleet executor"
```

Generates `PHASE_PLAN.md` with numbered tasks, dependencies, acceptance criteria, and token estimates.

### Execute

```
/osEngineer:fix TICKET-123
/osEngineer:feature TICKET-124
```

Dispatches the developer agent. Each task = atomic commit. Rollback path is documented.

### Verify

```
/osEngineer:verify phase-3
```

Runs verification protocol: tests, e2e tracer bullets, cost recalibration.

### Evolve (HITL skill improvement)

```
/osEngineer:evolve
```

Triggers the skill evolution protocol. Every 5 completed phases, osEngineer auto-nudges you with 3 improvement options. You select one, skip, or propose your own. Accepted proposals are appended to `memory/patterns/`.

### Sandbox (containerized local testing)

```
/osEngineer:sandbox start specs/TEMPLATES/mission-test.json --clean
```

Spins up an isolated local container cluster (RabbitMQ, Vault) to run and test swarm missions locally.

### Evaluation harness (detectors, classifiers, scanners)

```
/osEngineer:recipe-eval-harness /path/to/detector-repo
```

Sets up pinned, sha256-verified labeled datasets with dev/holdout/sealed splits and set roles, a deterministic fetch script, per-set P/R/F1/latency, and an eval policy (`specs/SCHEMAS/eval-policy.schema.json`). Then it runs a keep/revert improvement loop in which every verdict comes from `bin/ose-eval-gate`. Lessons from the reference loop are in [`docs/eval-harness-lessons.md`](docs/eval-harness-lessons.md).

### Explain (built-in help)

```
/osEngineer:explain
/osEngineer:explain artifacts
/osEngineer:explain commands
/osEngineer:explain lifecycle
```

Explains how osEngineer works, what artifacts it creates, which commands are available, and how the skill lifecycle flows. Use this anytime you need a refresher.

## Architecture

```
osEngineer/
├── SKILL.md              # Manifest & entry point
├── AGENTS.md             # Agent catalog
├── install.sh            # Installation script
├── planning/             # Phase lifecycle + templates
├── agents/               # 14 mandatory + 5 optional agents
├── commands/             # 7 slash commands
├── discovery/            # Repo discovery, graphify, context7, env detection
├── specs/                # Spec-driven development
├── memory/               # Cross-session persistence + evolution counter
├── trust/                # Circuit breakers, HITL gates, evolution
├── hooks/                # Automation hooks
├── live-system/          # Production runbooks
└── integrations/         # Optional MCP integrations
```

Every directory has a `README.md` (human-readable) and `INDEX.md` (bot-navigable file list).

## Agent Team

### Mandatory (always loaded)

| Agent | Role |
|-------|------|
| **Developer** | Primary implementer; writes code, tests, commits |
| **Reviewer** | Per-PR code review; style, correctness, coverage |
| **Judge** | Merge gate; architectural alignment, ADR compliance |
| **Red Team (Local)** | Per-PR security scan; SAST, secrets, allowlist |
| **Red Team (Architect)** | Cross-repo invariant checks; topology drift |
| **Tech Writer** | Contracts, docs, OpenAPI, ADR amendments |
| **Researcher** | Discovery, graph queries, ADR catalog read |
| **Planner** | Phase breakdown, deps, token estimates, risk flags |
| **Live System Operator** | Docker ops, hotfixes, log inspection |
| **Metrics Onboarding** | promauto setup, test generation, endpoint wiring |
| **Topology Validator** | Code vs ansible drift, schema consistency |
| **Cert Monitor** | Expiry tracking, renewal scripts |
| **Health Verifier** | Container health, metrics endpoints |
| **Scope Manager** | Context window optimization for large workbenches |
| **Sandbox Provisioner** | Swarm testbed setup, unsealing mock secrets, metrics |

### Optional (compacted; loaded on demand)

| Agent | Trigger |
|-------|---------|
| **DBA** | Database change detected |
| **QA** | Test coverage < 80% |
| **UI/UX Designer** | Frontend change detected |
| **Sync Agent** | Hotfix on live system |
| **Budget Tracker** | Cost threshold exceeded |
| **Eval Harness Engineer** | Detector/classifier/scanner accuracy work |

## Key Principles

1. **Project-agnostic core, project-specific overlay** — Discovers your structure; not hardcoded to any project.
2. **Mandatory agents are lean** — Load fast and stay in context.
3. **Optional agents are compacted** — Only load when explicitly invoked.
4. **Spec-first, test-first, docs-first** — No code without a contract. No commit without a test.
5. **Graphify is the source of truth** — Query the graph before grepping.
6. **Token budgets are hard rules** — Exceed 150% of estimate → abort with handoff.
7. **Live system is read-only for source code** — Workbench → PR. Hotfixes require backport.
8. **Environment-aware execution** — Adapts to terminal, IDE, web, or daemon contexts.
9. **Continuous evolution via HITL** — Every 5 phases: "How can I serve you better?"

## External Dependencies

osEngineer is **standalone** but integrates with these tools when available:

- **[Graphify](https://github.com/your-org/graphify)** — AST + LLM knowledge graphs
- **Context7** — Code documentation MCP
- **AgentMemory** — Persistent memory backend
- **GitHub CLI (`gh`)** — PR creation, issue tracking
- **Docker** — Local test environments

## Contributing

This skill evolves via retrospectives and the HITL evolution protocol. After each phase, findings are appended to `memory/retrospectives/`. Validated patterns are promoted to `memory/patterns/`. Use `/osEngineer:evolve` anytime to propose improvements.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Repo profile

The repo profile adds a scoped Coding Skill and a portable local/headless
execution adapter. It reuses the target repository's policy, skill registry,
configurable plan directory (default `.plans/`) and review path. It does not
install generic reviewer roles, rewrite the policy file or CLAUDE.md, modify global configuration, or connect live accounts.

```bash
python3 bin/osengineer profile install --repo /path/to/repo
# Optional: --policy-file POLICY.md --plan-dir .plans
# Equivalent: bash install.sh --profile repo /path/to/repo
python3 bin/osengineer profile integrations doctor --config profiles/repo/integrations.json
python3 bin/osengineer profile runtime --help
python3 bin/osengineer profile learn --help
```

Codex discovers `.agents/skills/osengineer-repo-profile`; Claude uses its canonical
`.claude/skills/osengineer-repo-profile` copy. All runtime assets are copied inside
the skill, so the original checkout location is not required. Existing project
hooks are preserved; no new runtime hooks are automatically trusted or installed.
The repaired optional hooks remain available for separately configured launchers.

Copy integration configuration to a local untracked location before adding
project/page IDs and credential environment names. Configuration never contains
secret values. Provider reads and runner execution require explicit selections.
Headless operation defaults to local evidence; remote effects need a separately
authorized and sandboxed launch policy. A passing fixture suite does not promote
production autonomy.

Installation is repeatable when owned assets are unchanged. A modified skill,
projection or profile is preserved and produces a conflict instead of being
overwritten. Uninstall with `python3 bin/osengineer profile uninstall --repo
/path/to/repo`; unrelated policy, settings, agents and learning remain.
See [the skill](profiles/repo/SKILL.md), [execution](profiles/repo/references/execution.md)
for scope and verification.
