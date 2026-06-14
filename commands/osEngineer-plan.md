---
name: osEngineer:plan
description: >-
  Creates a PHASE_PLAN.md with numbered tasks, dependencies, acceptance
  criteria, token estimates, rollback path, and risk flags. Transitions
  phase from `discuss` to `plan`. Use when discuss-phase output is
  complete and scope is clarified. Don't use to revise an in-flight plan
  (use /osEngineer:fix to amend during execute), and don't use without a
  goal statement — the planner agent will refuse an unscoped invocation.
phase_allowed: [discuss, plan]
phase_after: plan
---

# /osEngineer:plan

**Syntax:** `/osEngineer:plan <goal-description>`  
**Role:** Planner agent (+ Researcher for context)  
**Output:** `PHASE_PLAN.md` in `planning/active/phase-XXX/`

---

## Description

Generate a `PHASE_PLAN.md` for a given goal. This is the planning phase of osEngineer.

## Steps

1. **Classify** the goal (hotfix/feature/refactor/adr/security).
2. **Research** (delegate to researcher): affected repos, ADRs, graph queries.
3. **Break down** into tasks T1, T2, … with deps, acceptance criteria, token estimates.
4. **Validate** plan against constraints (total ≤ 20K, no circular deps, rollback path exists).
5. **Write** `planning/active/phase-XXX/PHASE_PLAN.md`.

## Example

```
/osEngineer:plan "Implement ADR-033 retry-with-backoff for fleet executor"
```

## Constraints

- No execution begins until plan is validated.
- If total estimate > 20K, split into multiple phases.
- Human HITL gate: plan must be confirmed before execution.
