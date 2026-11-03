# Circuit Breakers

**Purpose:** Prevent runaway iterations: every phase runs on a fixed, measured budget.

---

## Per-Task Budget

Every task in the `PHASE_PLAN.md` frontmatter declares a `budget`
(`specs/SCHEMAS/phase-plan.schema.json`, validated by `repo_profile/phase_plan.py`):

| Key | Required | Measured by | Enforced |
|-----|----------|-------------|----------|
| `tool_calls` | yes | post-tool hook, +1 per tool call (Claude Code) | yes |
| `wall_minutes` | yes | post-tool hook (gaps between tool calls, up to `budget.idleSeconds`) and `osengineer run` (the run's wall time for every harness) | yes |
| `tokens` | no | post-tool hook, from the Claude Code `transcript_path` JSONL (input + cache creation + cache read + output tokens of each assistant message, counted once) | **no**, recorded only |

Tokens are not enforced because no harness gives them reliably: Claude Code
hook payloads carry no usage, and the transcript format is undocumented and
may lag the session. Kimi and Codex get no PostToolUse hook, so their
interactive sessions record nothing; headless `osengineer run` meters their
wall time.

The **phase budget** is the sum of its task budgets when a human approves the
phase: `osengineer approve` records it in `phase_approved_budget`, and it holds
until the next approval, so editing `PHASE_PLAN.md` during execution changes
nothing here. Usage is kept per approved `phase_id` in the gitignored
`.osengineer/runtime.yml` (`budget_tool_calls`, `budget_wall_seconds`,
`budget_tokens`, `budget_ratio_pct`) and resets when a new approval brings a new
`phase_id`. It is counted while the phase is `execute`, `micro` or `hotfix` and
a budget was recorded, or exactly one valid `<planning>/active/*/PHASE_PLAN.md`
exists. Repo-profile repositories are not metered.

Hooks alone write the counters. `osengineer state set` refuses them, and
`planning/PROTOCOL.md` lists what the guards refuse. Those guards match commands,
so they stop the plain routes and not an agent writing code to evade them:
`runtime.yml` is an ordinary file in the agent's reach. A meter that must hold
against that needs the file outside the agent's OS user.

**Ratio** = the larger of `tool_calls used / estimate` and
`wall seconds used / (wall_minutes × 60)`, in percent.

Sizing guide for task budgets (calibrate from `osengineer state` and the
`usage` block of `.osengineer/runs/<id>/RUN.json`):

| Task type | tool_calls | wall_minutes |
|-----------|------------|--------------|
| Hotfix | 10–30 | 5–15 |
| Small change (<3 files) | 20–60 | 10–30 |
| Medium feature | 60–150 | 30–90 |
| Large / cross-repo | split into phases | split into phases |

## Thresholds

`.osengineer/profile.json` (`repo_profile/config.py`):

| Key | Default | Effect |
|-----|---------|--------|
| `budget.warnPct` | 100 | One warning to the agent (`osEngineer BUDGET WARNING`) |
| `budget.tripPct` | 150 | The breaker trips |
| `budget.idleSeconds` | 900 | A gap between tool calls longer than this counts as idle, not wall time |

## When the Breaker Trips

The trip is code, not an instruction to the agent. At `ratio >= tripPct` the
post-tool hook, or `osengineer run` after a run:

1. Writes `.osengineer/BLOCKED.md`: phase, plan, source, threshold, usage
   against the estimate per measure, and the options (raise the budget,
   split the task, abandon).
2. Appends `{"from": <phase>, "to": "blocked", "by": "circuit-breaker",
   "reason": ..., "evidence": {...}}` to `.osengineer/approvals.jsonl`, the
   same log as human approvals.
3. Sets `phase: blocked` (and `blocked_from: <phase>`) in `.osengineer/state.yml`.
   This is the one automatic transition; it only ever moves *into* `blocked`.
4. From then on the pre-edit guard refuses edits and the pre-bash guard
   refuses every Bash call; `osengineer run` refuses to start.

Headless runs are also capped: `osengineer run` gives the harness at most the
wall time left before `tripPct` (and never more than `OSE_RUN_TIMEOUT`). A run
that hits the cap is recorded as `timeout` and trips the breaker.

## Leaving `blocked`

Only a human leaves `blocked`, with `osengineer approve plan` (or `discuss`)
in their own terminal (`hooks/lib/phase_gate.py`), then raises the task
budgets in `PHASE_PLAN.md` or splits the phase before `osengineer approve
execute`, which records the new budget. Usage is not reset: if the ratio is
still at or above `tripPct`, the next metered tool call trips the breaker again.
To raise a budget before it trips, `osengineer approve blocked`, then the same steps.

## Retry Limits

These are agent conventions, not enforced by code.

- **API calls:** Max 3 retries with exponential backoff.
- **Graph queries:** Max 2 retries (graph is static).
- **Git operations:** Max 3 retries (network issues).
- **Docker operations:** Max 2 retries (resource contention).

## Project-Specific Conventions

- Prometheus scrape timeout: 10s (circuit breaker on slow metrics).
- AMQP connection retry: Max 5 attempts, then disable consumer.
- Vault unseal retry: Max 3 attempts, then alert operator.
