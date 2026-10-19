# osEngineer Phase Lifecycle Protocol

Cross-repo, multi-session phase lifecycle. State persists in `.osengineer/state.yml` per repo and workbench; transitions are gated by the runtime hooks listed in `hooks/INDEX.md`. Historical provenance of the underlying state-machine pattern is recorded in `docs/adr/ADR-001-gsd-merge.md`.

---

## Phase States

```
[Discuss] → [Plan] → [Execute] → [Verify] → [Accepted]
               ↑         ↓            ↓
               └──── [Blocked] ←──────┘
```

### 1. Discuss
- **Input:** Goal statement, symptom, or ticket (e.g., OSP-123).
- **Output:** Clarified scope, risk flags, classification (hotfix / feature / refactor / adr).
- **Token budget:** 2K–4K (hard cap).
- **HITL gate:** Human confirms scope before planning begins (`osengineer approve plan`).

### 2. Plan
- **Input:** Discuss output.
- **Output:** `PHASE_PLAN.md` with:
  - Numbered tasks (T1, T2, …)
  - Dependencies (T3 depends on T2)
  - Acceptance criteria per task
  - Token estimates per task
  - Rollback path
  - Risk flags & mitigations
- **Token budget:** 3K–6K (hard cap).
- **Rule:** No execution begins until `PHASE_PLAN.md` exists and is validated, and the human has run `osengineer approve execute`.

### 3. Execute
- **Input:** `PHASE_PLAN.md`
- **Process:**
  1. Create branch: `feat/{phase-id}-{short-desc}`
  2. For each task:
     - Write contract/schema first (if touching a contract surface)
     - Write failing test (`test(scope): red — <behaviour>`)
     - Write code (`feat(scope): green — <one-line>`)
     - Refactor (`refactor(scope): <description>`)
  3. Atomic commits only. No squashing until merge.
- **Budget:** Per-task `budget` (`tool_calls`, `wall_minutes`, optional `tokens`) in the PHASE_PLAN frontmatter.
- **Abort rule:** The circuit breaker (trust/circuit-breakers.md) trips at `budget.tripPct` (150%) of the phase budget: it writes `.osengineer/BLOCKED.md`, sets phase `blocked`, and the guards stop edits and Bash until a human approves.

### 4. Verify
- **Input:** Executed branch.
- **Output:** `VERIFICATION.md` with:
  - Test results (unit, integration, e2e)
  - Tracer-bullet run evidence
  - Token cost actual vs planned
  - Lessons learned
- **Token budget:** 2K–3K.
- **Gate:** All acceptance criteria must pass before merge.

### 5. Accepted
- Judge agent reviews `PHASE_PLAN.md` + `VERIFICATION.md`.
- Red-Team-Local runs security scan.
- Human does final PR merge (HITL gate).
- Post-merge: append retrospective to `memory/retrospectives/`.
- Patterns the retrospective surfaces are not written to `memory/patterns/` by
  the judge or the retro. They become evolution proposals
  (`osengineer evolve propose`, then `evolve accept`, which writes only
  `.osengineer/evolve/proposals/<id>.md` in the target repo). A human runs
  `osengineer evolve promote <id> --pr`, which commits the pattern on an
  `evolve/<id>-<slug>` branch of the skill home and opens a PR; the pattern lands
  in `memory/patterns/` only when that PR is merged. See
  `commands/osEngineer-evolve.md`.

---

## Blocked State

A phase enters **Blocked** when:
- Token budget exceeded (circuit-breaker)
- Acceptance criteria cannot be met with current architecture
- New ADR required (cross-cutting decision discovered mid-phase)
- External dependency unavailable (upstream API, broker queue, Vault secret)

**Recovery:**
1. Write `BLOCKED.md` with root cause, options, and recommendation.
2. Return to Discuss or Plan with new constraints.
3. Do NOT hack around the blocker.

`.osengineer/BLOCKED.md` (written by the circuit breaker) is deliberately not
gitignored: it stays tracked and visible in `git status` so the human sees it.
While the phase is `blocked` the agent cannot edit or delete it.

---

## Micro-Phase (Lightweight Hotfix/Feature)

For small changes (e.g. simple bug fixes, single-line modifications, minor documentation edits) that do not warrant the cognitive overhead of the full 5-stage lifecycle, osEngineer supports a **Micro-Phase**.

### 1. State: `micro` or `hotfix`
- Transitions directly to an active execution state without blocking code edits.
- Allows immediate, surgical file edits.

### 2. Lifecycle Flow
Instead of `Discuss → Plan → Execute → Verify → Accepted`, the workflow is collapsed:
```
[Combined Discuss/Plan] → [Immediate Execute/Verify] → [Accepted]
```

### 3. Single Unified Artifact: `MICRO_PLAN.md`
- No separate `PHASE_PLAN.md`, `RESEARCH.md`, and `VERIFICATION.md` are required.
- A single `MICRO_PLAN.md` (instantiated from `templates/MICRO_PLAN.md` or `planning/TEMPLATES/MICRO_PLAN.md`) acts as both the lightweight plan and the verification record.
- **Content:** Minimized target spec/plan, TDD commit list, and a verification checkbox (testing evidence).

### 4. Upgrade Gate
- If the micro-phase exceeds its scope (e.g., touches >3 files, requires cross-team handoffs, or introduces complex design decisions), it must immediately upgrade to a full phase by transitioning to `plan` state and drafting a complete `PHASE_PLAN.md`.

---

## Phase Gate (human approval)

Only a human changes the phase. The human runs, in their own terminal or as a
`!` shell command in Claude Code:

```
osengineer approve <phase> [--reason "<text>"]
```

`osengineer state set phase <p>` is the same command. Every other state key is
still set with `osengineer state set <key> <value>`.

| From | May approve |
|------|-------------|
| `idle` | `discuss`, `micro`, `hotfix` |
| `discuss` | `plan`, `micro`, `hotfix`, `blocked` |
| `plan` | `execute`, `discuss`, `micro`, `hotfix`, `blocked` |
| `execute` | `verify`, `blocked` |
| `verify` | `accepted`, `execute` (rework via `/osEngineer:fix`), `blocked` |
| `accepted` | `idle`, `discuss`, `micro`, `hotfix` |
| `blocked`, `suspended` | `discuss`, `plan` |
| `micro`, `hotfix` | `accepted`, `idle`, `plan` (upgrade gate), `blocked` |

Prerequisites. These are checked for presence only; schema validation is a separate step.

- `→ execute` needs `planning/active/<phase>/PHASE_PLAN.md`.
- `verify → accepted` needs `planning/active/<phase>/VERIFICATION.md`.
- `micro`/`hotfix → accepted`/`idle` needs `planning/active/<phase>/MICRO_PLAN.md`.

The repo profile uses its `planDirectory` instead of `planning/`. A state that
is not in the table, such as a hand-written `verified`, is refused. Fix
`state.yml` by hand in that case.

Each approval sets `phase`, `phase_approved_by` (git `user.email`, else the
OS user) and `phase_approved_at` in `.osengineer/state.yml`. It also appends
`{ts, from, to, by[, reason]}` to `.osengineer/approvals.jsonl`, which is
tracked and append-only. `state set` refuses the two record fields.

**The agent cannot approve.** The guards refuse it in every phase, under Claude
Code, Kimi Code and Codex:

- `osEngineer-pre-edit-guard` refuses any Write/Edit/MultiEdit/NotebookEdit, or
  Codex `apply_patch`, that targets `.osengineer/state.yml`, `approvals.jsonl`
  or `runtime.yml` (the breaker's `budget_*` counters and context telemetry;
  hooks write it in code, which the guards do not see). While the phase is
  `blocked` it also refuses `.osengineer/BLOCKED.md`.
- `osEngineer-pre-bash-guard` refuses `osengineer approve` and `osengineer state
  set phase*`, including through a path, an interpreter, `bash -c`, `$(...)` or
  env prefixes. It also refuses any command that names `write_state_field`, and
  any command that names `state.yml`/`approvals.jsonl`/`runtime.yml` (and
  `BLOCKED.md` while blocked) while redirecting into
  them or running a writer (`sed -i`, `tee`, `cp`/`mv`/`rm`, `python`/`node`/
  `perl`/`awk`, `git checkout`/`restore`, …). Reads such as `cat`, `grep` and
  `git add`/`diff` still pass.
- `OSE_BYPASS=1` does not lift either refusal. The refused bypass is logged to
  `bypass-log.jsonl` as `not honoured for phase approval`.
- `OSE_HEADLESS=1` (`osengineer run`) makes `approve` and `state set phase`
  refuse outright.

**Why `!` works.** Claude Code runs `!` shell-mode commands "directly without
going through Claude". PreToolUse "runs only when Claude calls a tool", so the
guards never see a `!` command
([interactive mode](https://code.claude.com/docs/en/interactive-mode),
[hooks](https://code.claude.com/docs/en/hooks)). Kimi and Codex have no
equivalent that we have verified, so run `approve` in your own terminal there.

**Limits.** The shell check is best-effort pattern matching, not a sandbox. It
does not catch:

- a script the agent writes to a file and then runs;
- encoded or assembled commands (`base64 -d | sh`, `$x$y`);
- a symlink created under another name;
- an editor or interpreter the list does not name.

The CLI cannot tell a human from the agent, because both run in the same
environment. The gate therefore rests on the hooks. The approvals log and
`git diff .osengineer/state.yml` are the audit trail: a phase change with no
matching log entry is a red flag.

---

## Planning Directory Conventions

```
planning/
├── active/
│   └── phase-033-retry-backoff/
│       ├── PHASE_PLAN.md
│       ├── RESEARCH.md
│       ├── VERIFICATION.md
│       └── BLOCKED.md (if applicable)
├── completed/
│   └── phase-032-amqp-management-bus/
│       ├── PHASE_PLAN.md
│       ├── VERIFICATION.md
│       └── RETROSPECTIVE.md
└── templates/
    ├── PHASE_PLAN.md
    ├── RESEARCH.md
    ├── VERIFICATION.md
    └── RETROSPECTIVE.md
```

**Rule:** `active/` contains at most 3 phases. Excess phases are queued in `backlog/`.
