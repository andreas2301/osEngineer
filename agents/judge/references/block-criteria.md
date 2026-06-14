# Block Criteria

Block the merge if ANY of these are true:

- CRITICAL or HIGH red-team finding without mitigation.
- Architectural invariant violation without ADR amendment.
- Scope creep > 20% of original plan (requires re-planning).
- Token cost > 200% of estimate (requires retrospective).
- No red commit in test history (TDD violation).
- Breaking change without migration plan.
