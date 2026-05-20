# Circuit Breakers

**Purpose:** Prevent runaway token consumption and infinite loops.

---

## Per-Task Token Budget

| Phase Type | Base Estimate | Circuit Breaker (150%) |
|------------|---------------|------------------------|
| Hotfix | 2K–5K | 1.5× |
| Small feature (<3 files) | 5K–10K | 1.5× |
| Medium feature | 10K–20K | 1.5× |
| Large feature / Cross-repo | 20K–40K | 1.5× |
| Epic (multi-phase) | Per-phase | 1.5× per phase |

## Abort Rules

When circuit breaker trips:

1. **STOP immediately.** No more code generation.
2. **Write `BLOCKED.md`** with:
   - Task that exceeded budget.
   - Current state (what was done, what remains).
   - Options (continue with more budget, split task, abandon).
3. **Hand off** to human or planner agent.

## Retry Limits

- **API calls:** Max 3 retries with exponential backoff.
- **Graph queries:** Max 2 retries (graph is static).
- **Git operations:** Max 3 retries (network issues).
- **Docker operations:** Max 2 retries (resource contention).

## Sovereign Shield Specifics

- Prometheus scrape timeout: 10s (circuit breaker on slow metrics).
- AMQP connection retry: Max 5 attempts, then disable consumer.
- Vault unseal retry: Max 3 attempts, then alert operator.
