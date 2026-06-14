---
name: osEngineer:investigate
description: >-
  Researcher-driven symptom investigation — queries graphify for
  related components, reads relevant ADRs, walks recent commits in
  affected repos, samples logs (journalctl, docker, app), forms a
  hypothesis, and appends to RESEARCH.md with recommended next steps.
  Use when an error or unknown behaviour appears and the root cause is
  not obvious. Don't use to write a PHASE_PLAN.md (use /osEngineer:plan
  once the symptom is understood), don't use to execute a fix (use
  /osEngineer:fix once a plan exists), and don't use for routine
  "how does X work" questions (use /osEngineer:explain).
phase_allowed: [idle, discuss]
---

# /osEngineer:investigate

**Syntax:** `/osEngineer:investigate <symptom>`  
**Role:** Researcher agent  
**Output:** `RESEARCH.md` (or appended to existing).

---

## Description

Investigate a symptom, error, or unknown behavior. Uses graph queries, logs, and code reads.

## Steps

1. Accept symptom (e.g., "strategist metrics not showing on /metrics").
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
Recommended: /osEngineer:plan "Fix strategist metrics test pattern"
```
