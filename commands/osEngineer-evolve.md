# /osEngineer:evolve

**Syntax:** `/osEngineer:evolve [focus-area]`  
**Role:** Meta-agent — improves the skill itself based on usage.  
**Trigger:** Explicit user call, or auto-nudge after 5 completed phases.  
**Output:** `EVOLUTION_PROPOSAL.md` with user-selectable options.

---

## Description

The evolve command is osEngineer's self-improvement mechanism. It analyzes completed phases, identifies pain points, and presents the user with improvement options. The user selects which improvements to apply.

**This is a HITL gate. The agent NEVER auto-applies evolution changes.**

## Steps

### 1. Gather Evidence

Read from `memory/`:
- Last 5 `VERIFICATION.md` files (token variance, test results)
- Last 5 `RETROSPECTIVE.md` files (what went wrong, patterns)
- `memory/environment-profile.yml` (current capabilities)
- `memory/evolution-counter.yml` (phase count since last evolution)

### 2. Analyze Pain Points

Look for recurring themes:
- **Token overruns:** Same task type consistently underestimated?
- **Topology drift:** Repeated AMQP mismatches?
- **Missing metrics:** New services lack metrics?
- **Test flakiness:** Same integration test fails intermittently?
- **Context overflow:** Scope too wide, too many repos loaded?

### 3. Generate Options

Present 3–5 improvement options to the user:

```
[osEngineer] Evolution Proposal — 5 phases analyzed

Pain Points Detected:
  1. Token estimates for Docker SDK tasks are 40% low (3/5 phases)
  2. AMQP topology drift detected in 2 phases
  3. New service <service>-X lacks metrics onboarding

Improvement Options:

  [A] Refine token estimates
      Update planning/TEMPLATES/PHASE_PLAN.md to add 50% buffer
      for Docker SDK tasks. Update planner.md agent instructions.
      Cost: ~500 tokens to implement.

  [B] Add topology validator to CI
      Wire topology-validator agent into pre-commit hook.
      Auto-run on AMQP changes. Cost: ~1K tokens.

  [C] Onboard metrics for <service>-X
      Run metrics-onboarding agent on the new service.
      Cost: ~2K tokens.

  [D] Add flaky-test tracker
      New agent that marks intermittent test failures.
      Cost: ~1.5K tokens.

  [E] Shrink default scope
      Reduce scope-manager default from 5 repos to 3.
      Cost: ~200 tokens.

Select options to apply (e.g., "A, B, E"):
```

### 4. Apply Selected Options

For each selected option:
1. Create a mini-phase: `evolve/YYYY-MM-DD-<option>`.
2. Apply the change (update template, add agent, etc.).
3. Write `EVOLUTION_PROPOSAL.md` documenting what changed and why.
4. Commit to osEngineer repo.

### 5. Reset Counter

```yaml
# memory/evolution-counter.yml
phases_since_last_evolution: 0
last_evolution_date: 2026-05-20
applied_options: [A, B, E]
```

## Auto-Nudge

After every phase completion, increment the counter:
```yaml
phases_since_last_evolution: +1
```

When counter reaches 5:
```
[osEngineer] You've completed 5 phases since the last skill evolution.
  Run /osEngineer:evolve to review and improve the skill.
  (You can skip this nudge with /osEngineer:evolve --skip)
```

## Skip Rules

User can skip evolution nudges:
- `/osEngineer:evolve --skip` — Skip this nudge, reset counter to 0.
- Set `auto_evolve: false` in `memory/environment-profile.yml` — Disable nudges entirely.
