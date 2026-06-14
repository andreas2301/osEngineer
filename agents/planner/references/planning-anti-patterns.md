# Planning Anti-Patterns

- **Vague tasks:** "Fix the bug" → BAD. "Fix race condition in queue declaration" → GOOD.
- **Missing deps:** T3 depends on T2 but T2 is not listed.
- **No rollback:** "Revert if broken" → BAD. "Revert commits X, Y, Z; re-run ansible tag T" → GOOD.
- **Ignoring research:** Planning without reading ADRs or graph → BAD.
