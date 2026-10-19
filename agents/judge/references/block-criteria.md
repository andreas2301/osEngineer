# Block Criteria

Block the merge if ANY of these are true:

- CRITICAL or HIGH red-team finding without mitigation.
- Architectural invariant violation without ADR amendment.
- Scope creep > 20% of original plan (requires re-planning).
- Budget ratio ≥ `budget.tripPct` (default 150%) — the larger of tool calls and wall time against the PHASE_PLAN task budgets, as enforced by the circuit breaker (requires retrospective). Token counts are informational only.
- No red commit in test history (TDD violation).
- Breaking change without migration plan.
