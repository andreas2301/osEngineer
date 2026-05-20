# /osEngineer:fix

**Syntax:** `/osEngineer:fix <ticket-id-or-phase-id>`
**Scope:** Repo
**Primary agent:** Developer
**Co-agents:** Reviewer, Red-Team-Local, Verifier
**Output:** Branch + atomic commits + VERIFICATION.md + PR

---

## What it does

Executes a `fix`-classified phase end-to-end:
1. Architect routes the work to the right team (typically `coding`).
2. Developer implements the tasks from `PHASE_PLAN.md` using strict TDD.
3. Verifier independently re-proves each acceptance criterion.
4. Red-Team-Local runs SAST + secret scan on the branch.
5. Reviewer signs off on the diff.
6. A PR is opened with PHASE_PLAN.md + VERIFICATION.md attached.

A `fix` is smaller than a `feature` — it touches ≤3 files in a single team,
has no new ADR, and does not change a contract surface. If the work grows
mid-stream, the developer agent should abort and re-route to `/osEngineer:feature`.

## Pre-conditions (enforced by hooks)

1. `.osengineer/state.yml` exists and reports `phase` in `idle | plan` state.
   If `phase = execute` already, this command refuses — finish the active
   phase first.
2. A `planning/active/<phase>/PHASE_PLAN.md` exists and validates against
   `specs/SCHEMAS/phase-plan.schema.json`. If missing, the
   `osEngineer-prompt-guard.js` hook blocks the prompt with a "run
   /osEngineer:plan first" message.
3. Working tree is clean (no unstaged changes). The developer agent will
   abort if it isn't.

## Step protocol

For ticket `<TICK>` referencing phase plan `phase-NNN-<slug>`:

1. **Transition state.** `osengineer state set phase execute`. Architect
   routes to the team that owns the affected paths (per repo `AGENTS.md`).
2. **Create branch.** `git switch -c fix/<TICK>-<slug>` off the default branch.
3. **Per task in PHASE_PLAN.md:**
   - **Red commit** — write the failing test first. The
     `osEngineer-validate-commit` hook enforces the `test(<scope>): red —
     <behaviour>` message format.
   - **Green commit** — write the minimum production code to pass.
     Message: `fix(<scope>): green — <one-line>`.
   - **Refactor commit (optional)** — clean up while keeping tests green.
     Message: `refactor(<scope>): <description>`.
   - Each commit notes a rollback hint in its body (`Refs: ADR-NNN`).
4. **Run full test suite** on the branch. Capture output for VERIFICATION.md.
5. **Transition to verify.** `osengineer state set phase verify`.
   Architect dispatches the **verifier** agent, which re-walks each
   acceptance criterion (independent of the developer's claims) and
   writes `planning/active/<phase>/VERIFICATION.md`.
6. **Security scan.** Red-Team-Local runs on the branch. Produces a
   pass/fail verdict appended to VERIFICATION.md.
7. **Reviewer pass.** Inspects diff, commit hygiene, test coverage.
8. **PR open.** `gh pr create` with body that includes both
   PHASE_PLAN.md and VERIFICATION.md links.

## Abort conditions (auto-handled, not user-action)

| Trigger | Action |
|---|---|
| Token spend exceeds 150% of estimate | post-tool hook flips phase to `blocked`; developer writes `.osengineer/BLOCKED.md`; user resumes via `/osEngineer:fix --resume` |
| A new ADR is required mid-execute | developer routes to tech-writer; this phase is marked blocked pending ADR |
| External dependency missing (Vault secret, queue) | blocked + BLOCKED.md |
| Destructive bash needed without 4-part plan | `osEngineer-pre-bash-guard.js` blocks; user writes plan or sets OSE_BYPASS=1 |

## Example

```
/osEngineer:fix OSP-123
```

Assuming `planning/active/phase-072-fix-strategist-headers/PHASE_PLAN.md`
references OSP-123:
- Branch `fix/OSP-123-strategist-headers` is created off `master`.
- Tasks T1..T4 execute under TDD discipline.
- Verifier writes VERIFICATION.md proving each acceptance criterion.
- Red-team-local scan attaches its result.
- PR opens with title `fix(strategist): correct response headers (OSP-123)`.

## Related commands

- `/osEngineer:feature` — same shape but with full team for larger scope.
- `/osEngineer:plan` — produce the PHASE_PLAN.md this command consumes.
- `/osEngineer:verify` — re-run verification on an already-executed phase.
