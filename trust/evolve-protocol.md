# Evolve Protocol

**Purpose:** HITL-based continuous improvement of osEngineer itself.  
**Trigger:** `/osEngineer:evolve` or auto-nudge at 5 phases.  
**Output:** `EVOLUTION_PROPOSAL.md` with user-selectable options.

---

## Core Principle

**The skill evolves through human choice, not autonomous mutation.**

Every change to osEngineer's templates, agents, or protocols is:
1. Proposed by the evolve agent based on evidence.
2. Presented to the user as options.
3. Applied ONLY after user selection.
4. Committed to the osEngineer git repo.

## Auto-Nudge Mechanism

After each completed phase:
1. Increment `memory/evolution-counter.yml:phases_since_last_evolution`.
2. If counter == 5, display nudge:
   ```
   [osEngineer] 5 phases completed. Consider running /osEngineer:evolve
   to review and improve the skill. Skip with --skip.
   ```
3. If counter >= 10, display stronger nudge:
   ```
   [osEngineer] 10 phases without evolution. Skill may be stale.
   Run /osEngineer:evolve or disable nudges with auto_evolve: false.
   ```

## Evidence Sources

The evolve agent analyzes:
- `VERIFICATION.md` — token variance, test results, coverage
- `RETROSPECTIVE.md` — pain points, pattern extractions
- `BLOCKED.md` — blockers that could be prevented by skill improvement
- `HEALTH_REPORT.md` — post-deploy issues
- `TOPOLOGY_DRIFT_REPORT.md` — recurring infrastructure mismatches

## Option Generation Rules

Options must be:
- **Specific:** "Add 50% buffer to Docker SDK estimates" not "improve estimates"
- **Measurable:** Can verify if applied successfully
- **Low cost:** Each option < 2K tokens to implement
- **Independent:** Can apply A without B

## Override

If the user has `auto_evolve: false` in their environment profile:
- No nudges are displayed.
- `/osEngineer:evolve` still works on demand.
