# /osEngineer:investigate

**Syntax:** `/osEngineer:investigate <symptom>`  
**Role:** Researcher agent  
**Output:** `RESEARCH.md` (or appended to existing).

---

## Description

Investigate a symptom, error, or unknown behavior. Uses graph queries, logs, and code reads.

## Steps

1. Accept symptom (e.g., "<service> metrics not showing on /metrics").
2. Query graphify for related components (if available).
3. Read relevant ADRs.
4. Check recent commits in affected repos.
5. Read logs (journalctl, docker logs, application logs).
6. Form hypothesis.
7. Write `RESEARCH.md` with findings and recommended next steps.

## Example

```
/osEngineer:investigate "duplicate metrics collector registration attempted"
```

Output:
```
Hypothesis: promauto registers on DefaultRegisterer at init-time.
Test creates custom registry and tries to re-register → duplicate error.
Fix: Test should verify via Gather() or testutil, not re-register.
Recommended: /osEngineer:plan "Fix <service> metrics test pattern"
```
