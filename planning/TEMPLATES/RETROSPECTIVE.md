# RETROSPECTIVE.md Template

**Phase ID:** `phase-XXX-{short-desc}`  
**Date:** YYYY-MM-DD  
**Facilitator:** agent name

---

## What Went Well?

<!-- Concrete wins. Link to commits, tests, or metrics. -->
1. Graphify saved ~2K tokens on discovery (see RESEARCH.md).
2. Atomic commits made rollback trivial when T4 failed first attempt.
3. Tech-writer caught missing contract BEFORE developer wrote code.

## What Went Wrong?

<!-- Honest failures. No blame. -->
1. Token estimate for T3 was 30% low. Docker SDK spawn latency was underestimated.
2. Red-Team-Architect found a topology drift in ansible AFTER T4 merged. Fixed in follow-up commit.
3. One integration test was flaky (race condition in queue declaration). Fixed by adding `QueueDeclare` before `Consume`.

## What Should We Change?

<!-- Actionable improvements to the skill, templates, or process. -->
1. **Template update:** Add "Docker SDK latency" to risk flag examples in PHASE_PLAN.md.
2. **Pattern library:** Add "queue-declare-before-consume" as a validated RabbitMQ pattern.
3. **Token budgets:** Increase Docker SDK tasks by 50% by default.

## Pattern Extraction

<!-- If a new reusable pattern emerged, document it here. -->
**Pattern:** Dual-listen migration (AMQP old + new queue during transition)
**Context:** Phase v3.6-S used this to migrate from direct Operator to Supervisor bus.
**Cost:** 8K tokens (including tests).
**Reusability:** High — any AMQP topology migration.
**Location:** `memory/patterns/dual-listen-migration.md`
