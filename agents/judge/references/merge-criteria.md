# Merge Criteria

All of these must be true:

1. **Plan fidelity:** The PR implements what `PHASE_PLAN.md` promised. No scope creep.
2. **Verification pass:** `VERIFICATION.md` shows all acceptance criteria met.
3. **Red team clear:** No CRITICAL or HIGH findings from red-team-local.
4. **Architectural alignment:** No invariant violations from red-team-architect.
5. **Cost reasonable:** `budget_ratio_pct` < `budget.tripPct` (default 150%), i.e. tool calls and wall time within the PHASE_PLAN task budgets as metered by the circuit breaker (trust/circuit-breakers.md), or a human approved more budget.
6. **Tests green:** All CI checks pass.
7. **Docs complete:** ADR amended if needed; contracts updated if needed.
