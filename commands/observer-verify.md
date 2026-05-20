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
4. Run e2e tracer bullet (if defined in plan).
5. Check metrics (token cost, wall-clock time, coverage).
6. Write `VERIFICATION.md`.
7. If any criterion fails, mark phase as `partial` and recommend `/osEngineer:fix`.

## Example

```
/osEngineer:verify phase-033
```
