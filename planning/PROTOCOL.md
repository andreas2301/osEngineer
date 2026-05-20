# osEngineer Phase Lifecycle Protocol

Phase lifecycle adapted from [get-shit-done] (GSD)(https://github.com/gsd-build/get-shit-done). Integrated into osEngineer for cross-repo, multi-session engineering.

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
- **HITL gate:** Human confirms scope before planning begins.

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
- **Rule:** No execution begins until `PHASE_PLAN.md` exists and is validated.

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
- **Token budget:** Per-task estimate × 1.5 (circuit-breaker).
- **Abort rule:** If a task exceeds 150% of estimate, stop, write `BLOCKED.md`, and hand off.

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
