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
