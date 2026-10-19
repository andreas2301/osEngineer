# Cost Recalibration

Read `budget_tool_calls`, `budget_wall_seconds`, `budget_tokens` and `budget_ratio_pct` with `osengineer state` (stored in the gitignored `.osengineer/runtime.yml`, merged over `state.yml`), and the `usage` block of each `.osengineer/runs/<id>/RUN.json`. Compare to the summed task `budget`s in the `PHASE_PLAN.md` frontmatter. `budget_used` is not task spend.

- Under estimate: note "phase delivered on budget."
- Over estimate but under `budget.tripPct` (default 150%): note "phase over by X% — consider revising estimate model."
- At or over `budget.tripPct`: the phase should ALREADY be `blocked`, with `.osengineer/BLOCKED.md` and a `by: circuit-breaker` entry in `.osengineer/approvals.jsonl`. If it's not, the breaker failed. Flag this as a process bug.
- Tokens are recorded only (Claude Code transcripts); report them, do not gate on them.
