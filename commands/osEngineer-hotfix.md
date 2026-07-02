---
name: osEngineer:hotfix
description: >-
  Runs a lightweight Micro-Phase for small/quick changes (simple bug fixes, single-line edits, doc updates).
  Transitions phase to `micro` (or `hotfix`). Creates a combined `MICRO_PLAN.md` template in planning/active/phase-XXX/
  which serves as both a minimized plan and verification. Allowed to edit files directly.
  Use when a task is small, touches ≤3 files, and doesn't need complex design decisions.
  Don't use for large features, database schema changes, or cross-repo work.
phase_allowed: [idle, discuss, plan, micro, hotfix]
phase_after: micro
---

# /osEngineer:hotfix

**Syntax:** `/osEngineer:hotfix <bug/change-description>`  
**Role:** Developer agent + Verifier agent (combined lightweight workflow)  
**Output:** `MICRO_PLAN.md` in `planning/active/phase-XXX/`

---

## Description

Run a Micro-Phase (lightweight hotfix/feature execution) for a small change to bypass the overhead of separate plan, execute, and verify phases.

## Steps

1. **Initiate Micro-Phase:** Set state field `phase: micro` (or `hotfix`).
2. **Create Combined Artifact:** Write `planning/active/phase-XXX/MICRO_PLAN.md` using the combined template.
3. **Execute and Commit:**
   - Write failing test (if code change).
   - Write code to fix.
   - Commit with Conventional Commit tags.
4. **Verify:** Check off the verification criteria inside `MICRO_PLAN.md`.
5. **Accept:** Complete the change and transition the state back to `idle`.

## Example

```
/osEngineer:hotfix "Fix prompt-guard hook environment detection crash"
```

## Constraints

- Only touches ≤3 files.
- No database schema migrations or security-critical changes.
- If scope creep occurs, upgrade to a full plan via `/osEngineer:plan`.
