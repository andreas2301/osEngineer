# RESEARCH.md Template

**Phase ID:** `phase-XXX-{short-desc}`  
**Researcher:** agent name  
**Date:** YYYY-MM-DD  
**Method:** graph query | grep | ADR read | code read | e2e probe

---

## Repo Topology

```
repo-name-1/
  branch: master
  last commit: abc123 (2 days ago)
  size: ~12K LOC
  classification: large (orchestrator + amqp + docker)
  key files:
    - internal/orchestrator/orchestrator.go
    - internal/service/service.go
  dependencies: repo-name-2, repo-name-3

repo-name-2/
  branch: main
  ...
```

## Graph Findings

<!-- If graphify-out/ exists, paste key queries and results. -->
- **Query:** "What calls SpawnContainer?"
- **Result:** 3 call sites: orchestrator.go:142, workers/provisioner.go:89, tests/e2e_spawn_test.go:45
- **Community:** SpawnContainer lives in cluster C4 (docker lifecycle)

## ADR Relevance

| ADR | Status | Relevance to this phase |
|-----|--------|------------------------|
| ADR-018 | Accepted | Defines AMQP retry semantics — this phase extends it |
| ADR-021 | Accepted | Cert TTL — retry must not outlive cert renewal |

## Code Findings

<!-- Key code snippets or patterns discovered. -->
- Current retry is hardcoded in `internal/amqp/broker.go:78` — `RetryCount: 3, Interval: 1s`
- No exponential backoff. No jitter. No DLQ on exhaustion.

## Open Questions

1. Should backoff be configurable per persona type?
2. Does the fleet broker have different retry needs than the host broker?
3. Are there existing tests that assume instant retry?
