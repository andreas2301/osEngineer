---
name: osEngineer:verify
description: >-
  Runs the verification protocol against a completed phase. Executes tests,
  collects tracer-bullet evidence, recalibrates token cost (estimated vs.
  actual), and produces VERIFICATION.md. Use after execute phase completes
  and the PR is ready for the judge. Don't use mid-execute (tasks may still
  be in flight) and don't use to skip the judge — verify produces evidence,
  the judge makes the merge decision.
phase_allowed: [execute, verify]
phase_after: accepted
---

# /osEngineer:verify

**Syntax:** `/osEngineer:verify <phase-id>`  
**Role:** Developer agent (self-verify) + Reviewer spot-check  
**Output:** `VERIFICATION.md`

---

## Description

Run the verification protocol for a completed phase. Validates that acceptance criteria are met.

## Steps

1. Read `PHASE_PLAN.md` for the phase.
2. Run unit tests in all affected repos.
3. Run integration tests.
4. Run e2e tracer bullet or Dynamic Mission Sandbox simulation (e.g. `/osEngineer:sandbox start <path> --clean` for multi-repo / cross-service flows).
5. Check metrics (token cost, wall-clock time, coverage).
6. Write `VERIFICATION.md`.
7. If any criterion fails, mark phase as `partial` and recommend `/osEngineer:fix`.

## Example

```
/osEngineer:verify phase-033
```
