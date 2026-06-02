# osEngineer — Real-Enforcement, Per-Team, Multi-Repo Engineering Skill

**Status:** Approved design — 2026-05-20
**Owner:** [Your Name]
**Scope:** osEngineer skill — full design covering all 7 platform-quality layers with runtime enforcement
**Supersedes:** Implicit scaffolding intent in `SKILL.md` v0.1.0

---

## 1. Goal

Turn osEngineer from a scaffold of protocol-markdown into an engineering skill that:
- Initialises a single repo OR a workbench (folder of N repos) with one command
- Discovers the Platform META repo (`<meta-repo>`) or helps create one
- Drops per-folder team manifests with auto-detected ownership (Go / Ansible / tests / docs / security)
- Enforces every claimed rule at runtime via git + Claude hooks + a Node CLI + CI status checks
- Supports the full phase lifecycle (`discuss → plan → execute → verify → accepted`) with persistent state
- Subsumes `get-shit-done` — all `gsd-*` names rewritten to `osEngineer-*`; no external skill references remain

## 2. Non-goals

- Building a new META repo (a reference project already serves that role)
- Replacing Claude Code or Anthropic SDK functionality
- Supporting non-git projects
- Calendar-based scheduling — work is token-bound, not week-bound

## 3. Mental model — three-level nesting

```
Workbench  (a folder containing 1..N repos)
  └── Repo  (a git repository)
        └── Team  (a folder owned by one role: coding / testing / infra / docs / security)
```

At every level: one `AGENTS.md` declares membership and routing; one `.osengineer/` holds state, handoffs, and counters; the architect agent reads its `AGENTS.md` and dispatches downward. The runtime is the same `osengineer` Node CLI at all levels, scoped by `pwd`.

## 4. The AGENTS.md contract

Every `AGENTS.md` has a YAML frontmatter block. The frontmatter is machine-parseable; the body below it is prose for humans. The runtime parses only the frontmatter.

### 4.1 Workbench-level frontmatter

```yaml
---
scope: workbench
schema_version: 1
meta_ref:
  path: ./<meta-repo>
  role: codified-source-of-truth
repos:
  - path: ./<service-repo-a>
    category: management
  - path: ./<service-repo-b>
    category: fleet
  - path: ./<observability-repo>
    category: observability
cross_repo_handoffs_dir: ./.osengineer/handoffs/
---
```

### 4.2 Repo-level frontmatter

```yaml
---
scope: repo
schema_version: 1
architect: true
project_classification: large  # small | medium | large | specialist
teams:
  - team_id: coding
    folder: internal/
    agents: [developer, reviewer]
    owns_paths: ["internal/**", "cmd/**", "pkg/**"]
    reads_paths: ["api/**", "contracts/**", "ansible/**"]
    excludes: ["internal/**/*_test.go"]
    escalates_to: [testing, infra]
  - team_id: testing
    folder: null  # glob-only; no canonical folder
    agents: [qa]
    owns_paths: ["internal/**/*_test.go", "tests/**", "integration/**"]
    reads_paths: ["internal/**", "cmd/**"]
    escalates_to: [coding]
  - team_id: infra
    folder: ansible/
    agents: [topology-validator, live-system-operator]
    owns_paths: ["ansible/**", "docker-compose*.yml", "Dockerfile*", "scripts/**"]
    reads_paths: ["**/*.yml", "**/Dockerfile"]
    escalates_to: [coding, security]
  - team_id: docs
    folder: docs/
    agents: [tech-writer]
    owns_paths: ["docs/**", "README*.md", "**/*.openapi.yaml"]
    reads_paths: ["**"]
    escalates_to: []
  - team_id: security
    folder: null
    agents: [red-team-local]
    owns_paths: [".github/codeql/**", "security/**"]
    reads_paths: ["**"]
    escalates_to: [coding, infra]
meta_ref: ../<meta-repo>
phase_state_file: ./.osengineer/state.yml
---
```

### 4.3 Team-level frontmatter (in each team folder)

```yaml
---
scope: team
schema_version: 1
team_id: coding
parent_repo: ../
agents: [developer, reviewer]
owns_paths: ["internal/**", "cmd/**", "pkg/**"]
---
```

### 4.4 Validation

`specs/SCHEMAS/agents-md.schema.json` (JSON Schema 2020-12) validates the frontmatter. `osEngineer-validate-commit.sh` re-validates on any commit touching an `AGENTS.md` file.

## 5. Component inventory

| Component | Lives in | Built / ported / refactored |
|---|---|---|
| `bin/osengineer` Node CLI | `osEngineer/bin/` | Port `get-shit-done/bin/gsd-sdk.js`; rename + repurpose |
| 10 hooks `osEngineer-*` | `osEngineer/hooks/` | Port relevant subset of `get-shit-done/hooks/*`; rename all `gsd-*` → `osEngineer-*` |
| 19 agent files | `osEngineer/agents/` | Already exist; add `agents/architect.md` and `agents/verifier.md`; merge the root `AGENTS.md` (current 19-agent catalog) into the existing `agents/INDEX.md` (currently a bot-navigable file list), producing one catalog at `agents/INDEX.md`; delete the root `AGENTS.md` |
| 5 team templates | `osEngineer/templates/team-*.md` | New |
| AGENTS.md template (per scope) | `osEngineer/templates/AGENTS.md.{workbench,repo,team}.tmpl` | New |
| Phase artifact templates | `osEngineer/planning/TEMPLATES/` | Exist; add `RETROSPECTIVE.md` if missing |
| JSON schemas | `osEngineer/specs/SCHEMAS/` | New: `agents-md.schema.json`, `phase-plan.schema.json`, `service-manifest.schema.json`, `message-contract.schema.json` |
| Service-manifest example | `osEngineer/specs/TEMPLATES/service-manifest.yml` | New |
| Message-contract example | `osEngineer/specs/TEMPLATES/message-contract.yaml` | New |
| `VERSION` file | `osEngineer/VERSION` | New, starts at `0.2.0` (post-GSD-merge) |
| `CHANGELOG.md` | `osEngineer/CHANGELOG.md` | New, first entry = "0.2.0 — initial GSD merge + real enforcement" |
| `install.sh` | `osEngineer/install.sh` | Heavy refactor: must copy `agents/*.md` into `<repo>/.claude/agents/`, install both git hooks + Claude hooks, write `AGENTS.md` per scope, drop `CLAUDE.md` template, initialise `.osengineer/state.yml` |
| Memory seeds | `osEngineer/memory/patterns/` and `retrospectives/` | New: 3 real reference-project patterns + 1 retrospective |
| ADR-001 | `osEngineer/docs/adr/ADR-001-gsd-merge.md` | New: records the get-shit-done merge with source SHA |

## 6. Data flow

### 6.1 Workbench init

`osengineer init <workbench-root>` (no `--single` flag) runs:
1. **Detect execution environment** — probe shell/IDE/Docker/gh/daemon, ASK USER to confirm, store to `<workbench>/.osengineer/environment-profile.yml`.
2. **Scan for `.git` directories** under workbench root (depth ≤ 2).
3. **Search for META repo** — probe each repo for: `README.md` containing "Source of Truth" OR existence of both `plans/` and `teams/` directories. If found, record path. If not, ask user (default: create `<workbench>-meta`).
4. **Write workbench `AGENTS.md`** with `scope: workbench` and the `repos:` list.
5. **For each repo:** invoke `osengineer init <repo-root>` (sub-flow below).
6. **Initialise** `<workbench>/.osengineer/init-progress.yml` for resumability — if init aborts mid-workbench, re-running picks up at the next uninitialised repo.

### 6.2 Single-repo init

`osengineer init <repo-root>` runs:
1. **Auto-detect folder→team mapping:**
   - Go modules (`go.mod` exists) → propose `coding` owns `internal/`, `cmd/`, `pkg/`
   - `ansible/` or `roles/` → propose `infra` owns those
   - `*_test.go` glob present → propose `testing` owns the glob (no separate folder)
   - `docs/` exists → propose `docs` team
   - `.github/codeql/` or `security/` exists → propose `security` team
   - Fallback for repos with `src/test/infra` literal folders: use them directly
2. **Generate proposed `<repo>/AGENTS.md`**, render diff, ASK USER to confirm or edit inline.
3. **Write final `<repo>/AGENTS.md`** plus per-team `<folder>/AGENTS.md` files (where folder is non-null).
4. **Copy** `osEngineer/agents/{mandatory}.md` → `<repo>/.claude/agents/*.md`. Optional agents are referenced in INDEX but not copied (loaded on demand).
5. **Install git hooks** into `<repo>/.git/hooks/` (symlinks, not copies, so updates propagate).
6. **Install Claude hooks** by merging into `<repo>/.claude/settings.json` — never overwrite, only add `osEngineer-*` entries; preserve any existing user-defined hooks.
7. **Drop `<repo>/CLAUDE.md`** from template if absent; if present, append an `## osEngineer` section if not already there.
8. **Initialise `<repo>/.osengineer/state.yml`** with `phase: idle`, `current_team: null`, `budget_used: 0`.
9. **Seed `<repo>/.osengineer/handoffs/.gitkeep`**.

### 6.3 Phase lifecycle (per repo)

State machine:
```
idle → discuss → plan → execute → verify → accepted
         ↑         ↓        ↓         ↓
         └─── blocked ←─────┴─────────┘
```

Each transition is gated by a runtime check in the `osengineer` CLI. The hooks enforce: `idle → discuss` requires a goal statement; `discuss → plan` requires a discuss-output artifact; `plan → execute` requires a `PHASE_PLAN.md` validated against `phase-plan.schema.json`; `execute → verify` requires a green test run on the active branch; `verify → accepted` requires `VERIFICATION.md` AND PR approval (CI status check). State persists in `.osengineer/state.yml`.

### 6.4 Cross-team handoffs (within a repo)

When team A needs team B to do something:
1. Team A creates `<repo>/.osengineer/handoffs/HO-<n>-<slug>.md` with frontmatter:
   ```yaml
   ---
   handoff_id: HO-007
   from_team: testing
   to_team: coding
   opened_at: 2026-05-20T14:32:00Z
   closes_when: "func ProcessMessage exposes context.Context as first arg"
   blocking_phase_transitions: [verify]
   ---
   ```
2. The architect agent inspects the handoffs directory on every UserPromptSubmit and routes the next prompt to the team that should act.
3. Runtime blocks `verify → accepted` transition while any handoff is open.
4. Closing: target team appends a `closed_at:` field and a one-line reason. File stays in `handoffs/` for audit; runtime ignores closed handoffs.

### 6.5 Cross-repo handoffs (within a workbench)

Same mechanism, but lives in `<workbench>/.osengineer/handoffs/XR-<n>-*.md` with `from_repo` and `to_repo` fields. The workbench architect routes to the target repo's architect.

## 7. The 10 enforcement hooks

All hook scripts are prefixed `osEngineer-`. No internal reference to `gsd-*` remains.

| # | Hook | Trigger | Action |
|---|---|---|---|
| 1 | `osEngineer-validate-commit.sh` | git `commit-msg` | Reject if not `(test\|feat\|refactor\|fix\|chore\|docs)(scope): subject` (Conventional Commits). Phase-aware: in `execute` phase, require `(test\|feat\|refactor)` only |
| 2 | `osEngineer-pre-commit.sh` | git `pre-commit` | (a) Reject if production file touched without matching test in same commit during `execute` phase. (b) Reject if schema file touched and fails JSON Schema 2020-12 validation. (c) Reject if any file outside current team's `owns_paths` was touched |
| 3 | `osEngineer-post-commit.sh` | git `post-commit` | Run `graphify update . --ast-only` (skip if only `graphify-out/*` changed). Increment `<repo>/.osengineer/evolution-counter.yml`. If counter hits 5, set `auto_nudge: true` for next session |
| 4 | `osEngineer-prompt-guard.js` | Claude `UserPromptSubmit` | Inject phase state, active team, budget-used, open handoffs into the prompt. Block `/osEngineer:execute` if no `PHASE_PLAN.md`. Block all when state is `blocked` |
| 5 | `osEngineer-pre-edit-guard.js` | Claude `PreToolUse` on Edit/Write | Block edits during `discuss`/`plan` phases (read-only). Block edits to paths outside current team's `owns_paths`. Block edits to the live system path. **Phased activation:** `owns_paths` check is no-op until P3 ships team contracts; phase-gate and live-system checks active from P1 |
| 6 | `osEngineer-pre-bash-guard.js` | Claude `PreToolUse` on Bash | Block destructive bash (`rm -rf`, `git push --force`, `docker rm`, `kubectl delete`) without an active 4-part plan in `.osengineer/current-plan.md` |
| 7 | `osEngineer-read-guard.js` | Claude `PreToolUse` on Read/Grep/Glob | Block reads outside repo root unless a cross-repo handoff names that repo |
| 8 | `osEngineer-post-tool.js` | Claude `PostToolUse` | Track token usage against phase budget. Trigger circuit-breaker at 150% by writing `BLOCKED.md` and setting state to `blocked` |
| 9 | `osEngineer-session-start.js` | Claude `SessionStart` | Load `.osengineer/state.yml`, show banner: phase / team / budget% / open handoffs / auto-nudge if due |
| 10 | `osEngineer-statusline.js` | Claude `statusLine` | Render `[phase] team / budget-used% / open-handoffs` |

**Slash command ↔ CLI mapping:** Each `commands/osEngineer-*.md` file is a thin wrapper that dispatches to the corresponding `osengineer` CLI subcommand (e.g. `/osEngineer:init <path>` → `osengineer init <path>`). The slash command file documents user-facing behaviour; the CLI does the work. This avoids duplicating state-machine logic between markdown and Node.

**Escape hatch:** All hooks honour `OSE_BYPASS=1` env var — bypasses are logged to `.osengineer/bypass-log.jsonl`, never silent.

**CI gate:** `.github/workflows/osengineer-gate.yml` (created at repo init) handles what hooks can't: PR review count, branch-protection rules, red-team-local SAST as a required status check.

## 8. File layout — osEngineer repo after this design lands

```
osEngineer/
├── VERSION                                    # NEW — starts at 0.2.0
├── CHANGELOG.md                               # NEW
├── README.md                                  # EDIT — update Quick Start
├── SKILL.md                                   # EDIT — version bump, no GSD references
├── install.sh                                 # HEAVY REFACTOR
├── uninstall.sh                               # MINOR EDIT
├── bin/
│   └── osengineer                             # NEW — Node CLI (ported from gsd-sdk.js)
├── hooks/
│   ├── osEngineer-validate-commit.sh          # NEW (port + rename)
│   ├── osEngineer-pre-commit.sh               # NEW
│   ├── osEngineer-post-commit.sh              # NEW (port + rename)
│   ├── osEngineer-prompt-guard.js             # NEW (port + rename)
│   ├── osEngineer-pre-edit-guard.js           # NEW
│   ├── osEngineer-pre-bash-guard.js           # NEW (port + rename of gsd-workflow-guard)
│   ├── osEngineer-read-guard.js               # NEW (port + rename)
│   ├── osEngineer-post-tool.js                # NEW (port + rename of gsd-context-monitor)
│   ├── osEngineer-session-start.js            # NEW (port + rename of gsd-update-banner)
│   └── osEngineer-statusline.js               # NEW (port + rename of gsd-statusline)
├── agents/
│   ├── INDEX.md                               # RENAMED from AGENTS.md (catalog)
│   ├── architect.md                           # NEW
│   ├── verifier.md                            # NEW
│   ├── developer.md                           # EXISTS
│   ├── ... (17 others)                        # EXIST
├── templates/                                 # NEW directory
│   ├── AGENTS.md.workbench.tmpl
│   ├── AGENTS.md.repo.tmpl
│   ├── AGENTS.md.team.tmpl
│   ├── team-coding.md
│   ├── team-testing.md
│   ├── team-infra.md
│   ├── team-docs.md
│   ├── team-security.md
│   └── CLAUDE.md.tmpl
├── planning/
│   ├── PROTOCOL.md                            # EXISTS — minor edit (rename hooks)
│   ├── TEMPLATES/
│   │   ├── PHASE_PLAN.md                      # EXISTS
│   │   ├── RESEARCH.md                        # EXISTS
│   │   ├── VERIFICATION.md                    # EXISTS
│   │   └── RETROSPECTIVE.md                   # NEW (if absent)
│   └── README.md                              # EXISTS
├── specs/
│   ├── PROTOCOL.md                            # EXISTS
│   ├── SCHEMAS/                               # POPULATE
│   │   ├── agents-md.schema.json              # NEW
│   │   ├── phase-plan.schema.json             # NEW
│   │   ├── service-manifest.schema.json       # NEW
│   │   └── message-contract.schema.json       # NEW
│   └── TEMPLATES/                             # POPULATE
│       ├── service-manifest.yml               # NEW
│       └── message-contract.yaml              # NEW
├── memory/
│   ├── PROTOCOL.md                            # EXISTS
│   ├── patterns/                              # SEED with 3 real patterns
│   │   ├── queue-declare-before-consume.md    # NEW
│   │   ├── dual-listen-migration.md           # NEW
│   │   └── fail-closed-on-tls-error.md        # NEW
│   ├── retrospectives/                        # SEED with 1
│   │   └── 2026-05-20-osEngineer-bootstrap.md # NEW
│   ├── environment-profile.yml                # EXISTS
│   └── evolution-counter.yml                  # EXISTS
├── trust/                                     # EXISTS — minor edits to reference hooks
├── discovery/                                 # EXISTS — minor edits
├── live-system/                               # EXISTS — unchanged
├── integrations/
│   ├── confluence-mcp.md                      # HEAVY EDIT — from 6 lines to full MCP config
│   ├── context7-integration.md → ../discovery/  # (already in discovery — no change)
│   ├── vault-mcp.md                           # EXISTS
│   ├── playwright-mcp.md                      # EXISTS
│   └── openspace-mcp.md                       # EXISTS
├── docs/
│   ├── adr/
│   │   └── ADR-001-gsd-merge.md               # NEW — records the merge
│   └── superpowers/
│       └── specs/
│           └── 2026-05-20-osEngineer-design.md # THIS FILE
└── commands/
    ├── osEngineer-init.md                     # EDIT — workbench support
    ├── osEngineer-plan.md                     # EDIT — wire to bin/osengineer
    ├── osEngineer-fix.md                      # HEAVY REFACTOR — real executor
    ├── osEngineer-feature.md                  # HEAVY REFACTOR
    ├── osEngineer-verify.md                   # HEAVY REFACTOR
    ├── osEngineer-investigate.md              # EXISTS
    ├── osEngineer-evolve.md                   # EXISTS
    └── osEngineer-explain.md                  # EXISTS
```

## 9. GSD merge protocol

1. **Source SHA captured** — current HEAD of `d:\Repositories\get-shit-done\` recorded in ADR-001.
2. **No submodule.** Files copied directly into osEngineer (under `bin/`, `hooks/`).
3. **Rename pass** — every `gsd-*` token, every `gsd:` slash command, every `GSD_*` env var, every internal reference to "GSD" or "get-shit-done" renamed to `osEngineer-*` / `osEngineer:` / `OSE_*` / "osEngineer". Done by a one-shot script (`scripts/rename-gsd-references.sh`) checked into osEngineer for repeatability. ADR-001 records the rename mapping.
4. **No external references** — `package.json` does not depend on `get-shit-done`; SKILL.md does not link to it; README does not mention it (except in ADR-001 as historical record).
5. **Future GSD upstream changes** are NOT auto-pulled. If a useful upstream patch lands, port it manually with a new ADR.

## 10. Phase breakdown (no calendar)

| Phase | Name | Coherent slice | Acceptance |
|---|---|---|---|
| **P1** | Real enforcement spine | Port `get-shit-done/bin/gsd-sdk.js` → `osEngineer/bin/osengineer`; port + rename relevant hooks; wire into refactored `install.sh`; add ADR-001 + rename script | `osengineer init <test-repo>` writes hooks + `AGENTS.md`; `git commit -m "broken"` fails with osEngineer error; statusline shows phase |
| **P2** | Markdown gap closure | Write 4 JSON schemas + 2 spec templates; seed 3 patterns + 1 retrospective; add `VERSION` + `CHANGELOG.md`; write `agents/verifier.md` + `agents/architect.md`; rename catalog `AGENTS.md` → `agents/INDEX.md`; populate `commands/osEngineer-fix.md` and `osEngineer-feature.md` with real orchestration logic | All `INDEX.md` references resolve; `osengineer explain` produces coherent dump; schema validation works on example files |
| **P3** | Team-folder model | Write 5 team templates + 3 AGENTS.md.tmpl variants; build auto-detect logic in `bin/osengineer init`; build handoff filesystem protocol; wire `owns_paths` validation into `osEngineer-pre-edit-guard.js` | Init on `<service-repo-a>` proposes correct team map; user-edited AGENTS.md is honoured; edit to a path outside active team's `owns_paths` is blocked with a clear error |
| **P4** | META + workbench mode | Add workbench scope to `bin/osengineer init`; META detection probe; cross-repo handoff protocol; ADR catalog read from META; Confluence MCP fleshed out from 6 lines to full config (reference project pattern) | `osengineer init D:\Repositories` discovers META, writes workbench AGENTS.md, initialises a sample of repos in one resumable pass |
| **P5** | Evolution loop | Wire post-commit counter increment; auto-nudge banner at 5 phases; `/osEngineer:evolve` HITL flow; RETROSPECTIVE.md auto-generation post-merge; pattern promotion from retrospectives | Counter ticks; auto-nudge fires at phase #5; accepted proposal lands in `memory/patterns/`; rejected proposal logged with reason |

Each phase = its own spec → plan → execute → verify cycle inside `osEngineer/planning/active/`. P1 starts immediately after this design is approved.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Hooks block productive work in unexpected scenarios | `OSE_BYPASS=1` env var, logged to `bypass-log.jsonl` (auditable, not silent) |
| Auto-detect proposes wrong folder mapping | Always render diff and ask user before writing AGENTS.md |
| Token-budget circuit-breaker aborts mid-task | Writes `BLOCKED.md` with resume instructions; state preserved; never destructive |
| Multi-repo init takes too long / loses progress on crash | `<workbench>/.osengineer/init-progress.yml` records per-repo status; re-running resumes |
| GSD merge loses upstream patches | ADR-001 records source SHA; future upstream patches ported manually with new ADR |
| Renaming breaks downstream users who installed osEngineer earlier | Not applicable — repo created today (2026-05-20), no downstream users yet |
| Three-level nesting (workbench → repo → team) confuses users | `osengineer explain layout` command shows the current scope tree |
| Per-repo `AGENTS.md` collides with existing user-authored AGENTS.md | Init detects existing file; appends osEngineer frontmatter if not present; never overwrites prose body |

## 12. Out of scope for this design (deferred)

- Cross-workbench coordination (multiple workbenches sharing one META)
- Web UI for state inspection
- Multi-language Node CLI (German error messages, etc.)
- Replacing the user's existing `~/.claude/skills/` superpowers — osEngineer is additive
- Automatic ADR creation from chat (the user authors ADRs manually for now)

## 13. Success criteria

After all 5 phases:
- `osengineer init D:\Repositories` initializes the entire workbench in one resumable command
- Every reference project repo has a per-repo `AGENTS.md` reflecting its real folder layout
- The 10 hooks fire and enforce TDD / circuit-breakers / phase gates without manual reminders
- The 7-layer spec from product screenshots is *substantively* covered, not merely *described*
- Calendar estimates are absent from all artifacts; only token budgets remain
- No reference to "gsd", "get-shit-done", or "GSD-Antigravity" exists in any osEngineer file other than ADR-001
