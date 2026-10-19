# Review Checklist

Review in this order: correct → safe → holds under load → tested → fast → lean.
A finding needs a concrete failing case (an input, state or sequence that breaks);
without one it is not a finding, and style taste is not one either. Write each
finding as four parts: **where** (`file:line`), **what fails**, **failing case**,
**fix**. Number findings so they can be cited ("fix 2 and 5"), report at most 20
(the most severe), and end with **Not checked:** what you did not review.

## Correctness
- [ ] Logic matches the task description in `PHASE_PLAN.md`.
- [ ] Every changed line traces to the request (task, plan item or bug); flag unrelated edits as scope creep.
- [ ] Error paths are handled (no naked panics, no silent failures).
- [ ] Race conditions: shared state uses sync primitives.
- [ ] Resource leaks: files closed, connections released, contexts cancelled.

## Safe
- [ ] Input validation at trust boundaries, data-loss error handling, security and accessibility are intact (never cut).

## Holds under load
- [ ] No unbounded loops, queries, memory or retries at the expected volume.

## Tests
- [ ] Every production change has a corresponding test change.
- [ ] Tests fail before the fix (red commit exists).
- [ ] Tests pass after the fix (green commit exists).
- [ ] Coverage did not decrease (or decrease is justified in PR body).

## Fast
- [ ] No needless work on the hot path (repeated I/O, N+1 calls).

## Lean
- [ ] New code passed the reuse ladder: it needs to exist, is not already in the codebase, the stdlib or an installed dependency, and is not one line.
- [ ] Deliberate limits carry `shortcut: <limit> — revisit when <trigger>`.

## Style
- [ ] Follows repo conventions (read 3 nearby files).
- [ ] Naming is clear (no `tmp`, `data`, `handler2`).
- [ ] Comments explain WHY, not WHAT.
- [ ] No commented-out code.

## Commit Quality
- [ ] Commits are atomic.
- [ ] Commit messages follow Conventional Commits.
- [ ] ADR refs and issue refs are present.
