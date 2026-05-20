# /osEngineer:fix

**Syntax:** `/osEngineer:fix <ticket-id>`  
**Role:** Developer agent (+ Reviewer + Red-Team-Local)  
**Output:** PR with atomic commits.

---

## Description

Execute a fix from an existing `PHASE_PLAN.md`. Dispatches the developer agent to implement tasks.

## Steps

1. Read `planning/active/phase-XXX/PHASE_PLAN.md` matching the ticket.
2. Create branch: `fix/{ticket-id}-{short-desc}`.
3. For each task:
   - Follow TDD protocol (red → green → refactor).
   - Atomic commits only.
   - Note rollback path in commit body.
4. When all tasks complete, run verification tests.
5. Create PR with `PHASE_PLAN.md` and `VERIFICATION.md`.
6. Dispatch reviewer and red-team-local.

## Abort Conditions

- Token budget exceeded → write `BLOCKED.md`, stop.
- New ADR needed → route to tech-writer, stop.
- External dependency missing → write `BLOCKED.md`, stop.

## Example

```
/osEngineer:fix OSP-123
```
