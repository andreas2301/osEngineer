# Dynamic Scope Expansion

If mid-phase a new dependency is discovered:

1. Pause execution.
2. Re-run scope determination with new info.
3. If expansion adds >1 repo, check token budget. May need to split phase.
