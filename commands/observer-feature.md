# /observer:feature

**Syntax:** `/observer:feature <ticket-id>`  
**Role:** Developer agent (+ Planner + Reviewer + Judge)  
**Output:** PR with atomic commits.

---

## Description

Execute a feature from an existing `PHASE_PLAN.md`. Similar to `/observer:fix` but with full mandatory team for cross-cutting changes.

## Steps

1. Read `PHASE_PLAN.md`.
2. Create branch: `feat/{ticket-id}-{short-desc}`.
3. For each task, follow TDD protocol.
4. If PR touches >1 repo, red-team-architect activates automatically.
5. When complete, run full verification (unit + integration + e2e tracer bullet).
6. Create PR. Dispatch reviewer, red-team-local, red-team-architect.
7. Judge gates merge.

## Example

```
/observer:feature OSP-124
```
