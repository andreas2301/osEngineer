---
{
  "phase_id": "phase-033-retry-backoff",
  "goal": "Add exponential backoff to the fleet executor retry path.",
  "classification": "feature",
  "rollback_path": "Revert the phase commits; re-run ansible tag rabbitmq.",
  "tasks": [
    {"id": "T1", "description": "Research current retry behaviour", "acceptance": "Document all retry sites in fleet executor",
     "budget": {"tool_calls": 30, "wall_minutes": 15, "tokens": 2000}},
    {"id": "T2", "description": "Design backoff contract", "depends_on": ["T1"], "acceptance": "retry-policy-v1.yaml exists and validates",
     "budget": {"tool_calls": 20, "wall_minutes": 10, "tokens": 1500}},
    {"id": "T3", "description": "Implement backoff in executor core", "depends_on": ["T2"], "acceptance": "All tests green; no regression in spawn latency",
     "budget": {"tool_calls": 60, "wall_minutes": 40, "tokens": 4000}}
  ]
}
---
# PHASE_PLAN.md Template

<!-- The --- JSON frontmatter above is machine-checked against
     specs/SCHEMAS/phase-plan.schema.json (fail closed). Every task needs a
     budget: tool_calls and wall_minutes are enforced by the circuit breaker
     (trust/circuit-breakers.md); tokens is recorded only. -->

**Phase ID:** `phase-XXX-{short-desc}`  
**Goal:** One-sentence description.  
**Classification:** hotfix | feature | refactor | adr | security  
**Repos affected:** List of repos.  
**Budget:** per task in the frontmatter (`tool_calls`, `wall_minutes`, optional `tokens`).  
**Risk level:** low | medium | high | critical  
**Created:** YYYY-MM-DD  
**Planner:** agent name / human name

---

## Context

<!-- Researcher agent fills this. Links to RESEARCH.md, ADRs, graph queries. -->
- Related ADRs: ADR-NNN, ADR-NNN
- Related issues: OSP-NNN, OSP-NNN
- Graph query results: (link or summary)
- Previous phase learnings: (link to retrospective)

---

## Tasks

| # | Task | Owner | Deps | Acceptance Criteria | Budget (calls / min) | Status |
|---|------|-------|------|---------------------|----------------------|--------|
| T1 | Research current retry behaviour | researcher | — | Document all retry sites in fleet executor | 30 / 15 | planned |
| T2 | Design backoff contract | tech-writer | T1 | `retry-policy-v1.yaml` exists and validates | 20 / 10 | planned |
| T3 | Implement backoff in executor core | developer | T2 | All tests green; no regression in spawn latency | 60 / 40 | planned |

<!-- Keep this table in step with the frontmatter tasks; the frontmatter is what is enforced. -->

**Phase budget (sum of tasks):** 110 tool calls, 65 wall minutes, 7.5K tokens (recorded only)  
**Circuit breaker:** warns at 100% and trips at 150% of the larger of the tool-call and wall-time ratios (`budget.warnPct` / `budget.tripPct` in `.osengineer/profile.json`)

---

## Rollback Path

<!-- If something goes wrong, how do we revert? -->
1. Revert commit hash `XXXX` in repo A.
2. Revert commit hash `YYYY` in repo B.
3. Re-run ansible tag `rabbitmq` to remove exchange.
4. Verify: `rabbitmqctl list_exchanges | grep retry` returns empty.

---

## Risk Flags & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Backoff delays hide real failures | medium | high | Max retry = 5; dead-letter after exhaustion |
| AMQP queue depth spikes | medium | medium | Monitor `rabbitmq_queue_messages_ready` |
| Executor persona certs expire mid-retry | low | high | ADR-021 cert renewal cron covers this |

---

## Verification Plan

<!-- How will we KNOW this phase succeeded? -->
- [ ] Unit tests: `go test ./...` passes in all affected repos
- [ ] Integration test: Tracer-bullet e2e with simulated failure
- [ ] Metrics: `executor_retries_total{status=success}` increments
- [ ] Topology: Ansible dry-run shows no drift
- [ ] Security: Red-team-local scan passes
- [ ] Cost: `budget_ratio_pct` in `osengineer state` ≤ 150 (the breaker trips at `budget.tripPct`)
