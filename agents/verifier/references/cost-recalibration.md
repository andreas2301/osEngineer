# Cost Recalibration

Read `.osengineer/state.yml` `budget_used`. Compare to `PHASE_PLAN.md` `token_budget.estimate`.

- Under estimate: note "phase delivered on budget."
- Over estimate but under circuit-breaker (1.5×): note "phase over by X% — consider revising estimate model."
- Over circuit-breaker: the phase should ALREADY be in `blocked` state. If it's not, the post-tool hook failed. Flag this as a process bug.
