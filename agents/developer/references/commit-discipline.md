# Commit Discipline

- **Atomic:** One logical change per commit. No "and also fixed typo" bundling.
- **Message format:** `type(scope): subject` (Conventional Commits).
- **Scope:** Use the repo name or module name (e.g., `feat(strategist):`, `fix(guardian/bridge):`).
- **Body:** If the change touches >3 files or is non-obvious, add a body explaining WHY.
- **Refs:** Cite ADRs and issues: `Refs: ADR-018, OSP-123`.
- **Non-Interactive Execution:** Always enforce non-interactive commits/rebases. If using amends, rebases, or pulls that may spawn text editors, append `--no-edit` or prefix/configure with `git -c core.editor=true` to prevent terminal freezes in background processes.
