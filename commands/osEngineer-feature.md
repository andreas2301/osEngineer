# /osEngineer:feature

**Syntax:** `/osEngineer:feature <ticket-id-or-phase-id>`
**Scope:** Repo (or cross-repo if the phase plan touches multiple repos)
**Primary agent:** Developer
**Co-agents:** Planner, Reviewer, Judge, Red-Team-Local, Red-Team-Architect, Tech-Writer, Verifier
**Output:** Branch + atomic commits + VERIFICATION.md + PR

---

## What it does

Executes a `feature`-classified phase end-to-end. Differs from `/osEngineer:fix`
by activating the full mandatory team plus the red-team-architect for
cross-cutting integrity checks. Use this for:
- New service capabilities
- New AMQP exchange / routing key
- New API surface (contract-first)
- Cross-repo coordinated changes
- Any change that requires an ADR amendment

## Pre-conditions (enforced by hooks)

Same as `/osEngineer:fix`, **plus**:
- If the phase touches a contract surface (`contracts/`, `api/`,
  `service-manifest.yml`), the contract YAML/schema MUST exist BEFORE any
  production code is written. If absent, the developer agent stops and
  hands off to **tech-writer** to author the contract.
- If the phase touches > 1 repo, the workbench architect routes per-repo
  handoffs in `<workbench>/.osengineer/handoffs/XR-*.md` before any repo's
  developer starts.

## Step protocol

For ticket `<TICK>` referencing phase plan `phase-NNN-<slug>`:

1. **Pre-execute contract check.** Tech-writer verifies that every
   contract surface the plan touches has an existing
   `contracts/{produced,consumed}/<name>.yaml` validating against
   `specs/SCHEMAS/message-contract.schema.json` or
   `specs/SCHEMAS/service-manifest.schema.json`. If any is missing, the
   tech-writer authors it FIRST; this becomes T0 in the execution sequence.
2. **Transition state.** `osengineer state set phase execute`. Architect
   routes to the lead team. If multiple teams are involved, opens
   handoffs upfront.
3. **Create branch.** `git switch -c feat/<TICK>-<slug>` off the default branch.
4. **Per task in PHASE_PLAN.md:**
   - **Red commit** — failing test. `test(<scope>): red — <behaviour>`.
   - **Green commit** — minimum production code. `feat(<scope>): green — <one-line>`.
   - **Refactor commit (optional).** `refactor(<scope>): <description>`.
   - Atomic. Each commit notes ADR references in its body.
5. **Cross-repo invariants.** If the phase touches > 1 repo,
   Red-Team-Architect runs after every cross-repo handoff closes to check
   for topology drift (an exchange producer/consumer mismatch, an
   ansible/code divergence, an ADR violation).
6. **Verification.** Verifier walks acceptance criteria, runs the
   tracer-bullet (an end-to-end real message flow), records evidence in
   VERIFICATION.md. Cost recalibration appended.
7. **Security scan.** Red-Team-Local on the branch; Red-Team-Architect on
   cross-cutting invariants.
8. **Judge pass.** Judge reviews PHASE_PLAN.md + VERIFICATION.md +
   ADR-conformance. Final architectural gate before human merge.
9. **PR open.** `gh pr create` with full attached artefacts. PR body
   includes the contract diff if any.

## Abort conditions (same as `/osEngineer:fix`, plus)

| Trigger | Action |
|---|---|
| Contract surface touched without prior contract | tech-writer T0 inserted; if author refuses, phase blocked |
| Cross-repo handoff deadlocks | architect escalates to user with the open handoff list |
| Red-Team-Architect finds topology drift | Judge writes BLOCKED.md; phase resumes only after the drift is reconciled (often a new ADR) |

## Example

```
/osEngineer:feature OSP-410
```

Assuming `planning/active/phase-019-strategist-decision-bus/PHASE_PLAN.md`
references OSP-410 with `classification: feature` and `acceptance_criteria`
including "MC-strategist-decision-created message contract is published and
consumed by scribe":
- Tech-writer first authors `contracts/produced/MC-strategist-decision-created.yaml`
  validating against `message-contract.schema.json` (T0).
- Branch `feat/OSP-410-strategist-decision-bus` is created.
- T1..T6 execute under TDD with full team.
- Tracer-bullet sends a real decision message from strategist, confirms
  receipt at scribe queue, records latency.
- Red-Team-Architect verifies the exchange/routing-key in the contract
  matches both the strategist's publish call and the scribe's consume
  binding — no drift.
- Judge confirms ADR-014 is honoured.
- PR opens with title `feat(strategist): publish decision bus (OSP-410)`.

## Related commands

- `/osEngineer:fix` — same shape but trimmer team for narrower scope.
- `/osEngineer:plan` — produce the PHASE_PLAN.md this command consumes.
- `/osEngineer:verify` — re-run verification on an already-executed phase.
- `/osEngineer:investigate` — exploratory pre-planning when scope is unclear.
