# Review Checklist

## Correctness
- [ ] Logic matches the task description in `PHASE_PLAN.md`.
- [ ] Error paths are handled (no naked panics, no silent failures).
- [ ] Race conditions: shared state uses sync primitives.
- [ ] Resource leaks: files closed, connections released, contexts cancelled.

## Tests
- [ ] Every production change has a corresponding test change.
- [ ] Tests fail before the fix (red commit exists).
- [ ] Tests pass after the fix (green commit exists).
- [ ] Coverage did not decrease (or decrease is justified in PR body).

## Style
- [ ] Follows repo conventions (read 3 nearby files).
- [ ] Naming is clear (no `tmp`, `data`, `handler2`).
- [ ] Comments explain WHY, not WHAT.
- [ ] No commented-out code.

## Commit Quality
- [ ] Commits are atomic.
- [ ] Commit messages follow Conventional Commits.
- [ ] ADR refs and issue refs are present.
