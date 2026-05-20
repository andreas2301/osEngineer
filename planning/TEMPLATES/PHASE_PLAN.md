# PHASE_PLAN.md Template

**Phase ID:** `phase-XXX-{short-desc}`  
**Goal:** One-sentence description.  
**Classification:** hotfix | feature | refactor | adr | security  
**Repos affected:** List of repos.  
**Estimated tokens:** Total + per-task breakdown.  
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

| # | Task | Owner | Deps | Acceptance Criteria | Token Est | Status |
|---|------|-------|------|---------------------|-----------|--------|
| T1 | Research current retry behaviour | researcher | — | Document all retry sites in the service | 2K | planned |
| T2 | Design backoff contract | tech-writer | T1 | `retry-policy-v1.yaml` exists and validates | 1.5K | planned |
| T3 | Implement backoff in executor core | developer | T2 | All tests green; no regression in spawn latency | 4K | planned |
| T4 | Add topology to ansible | developer | T2 | `configure_rabbitmq.yml` declares retry exchanges | 2K | planned |
| T5 | Write integration tests | developer | T3, T4 | Tracer-bullet: 3 retries with 1s, 2s, 4s backoff | 3K | planned |
| T6 | Security scan | red-team-local | T3 | No secrets in logs; no unbounded retry loops | 1K | planned |
| T7 | Review & merge | judge | T5, T6 | ADR-033 referenced; all criteria pass | 1K | planned |

**Total estimated tokens:** 14.5K  
**Circuit-breaker threshold:** 21.75K (150%)

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
- [ ] Cost: Actual tokens ≤ 150% of estimate
