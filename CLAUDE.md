# osEngineer

## osEngineer

This repo is initialised with osEngineer. See `AGENTS.md` for the team layout
and `.osengineer/state.yml` for current phase state. Run `osengineer explain`
for the concept overview.

Key operational facts:
- **Conventional Commits** are enforced by the `commit-msg` git hook.
- **TDD** is enforced for production code: red → green → refactor, atomic commits.
  CI checks the order with `bin/ose-tdd-check`; only the architect may grant a
  `Risk-Exception: <class> — <reason>` trailer (see `docs/tdd-check.md`).
- **Destructive bash** is blocked without an active 4-part plan.
- **Override any rule** with `OSE_BYPASS=1` — every bypass logged.

## Baseline & Extended Agent Rules

Rules scale with task size. A trivial task (typo, comment, doc wording, version string: no new logic) needs no plan, test or ceremony. Anything with a branch, loop, parser, data change or security impact is not trivial.

### Baseline Rules
1. **Think Before Coding**: State assumptions explicitly. If an instruction is ambiguous, name what is confusing and ask instead of guessing. If it has several plausible interpretations, list them; do not pick one silently.
2. **Simplicity First**: Write the minimum code that solves the problem. No speculative abstractions or flexibility that wasn't explicitly requested. If a simpler approach exists, push back and propose it before building the complex one. After reading the code the change touches, take the first option that fully works: does it need to exist? already in the codebase? stdlib? an installed dependency? one line? only then minimal new code.
3. **Surgical Changes**: Touch only what the task requires. Do not "improve" adjacent code, reformat, or refactor things that aren't broken. Match the existing style. Remove only what your own change made unused. Every changed line must trace to the request.
4. **Goal-Driven Execution**: Turn vague instructions into verifiable targets. Create tests first to reproduce the issue, then loop until it passes.

**Never cut** input validation, error handling that prevents data loss, security or accessibility; neither rules 2-3 nor a Risk-Exception removes them.

### Extended Agent Rules
5. **Set Hard Token Budgets**: Stop runaway iterations by placing strict context limits.
6. **Expose Conflicts**: Don't blindly average contradictory patterns in the codebase.
7. **Read Before Writing**: Scan existing code before making edits to prevent duplication.
8. **Test Real Logic**: Ensure tests validate actual logic rather than just running to pass.
9. **Use Checkpoints**: Utilize checkpoints for long-running, multi-step tasks.
10. **Fail Explicitly**: Avoid silent failures that just appear successful. Fail loudly at real boundaries (input, I/O, external calls); add no defensive code for impossible states.

### Closing Convention
End every agent report with a **Skipped / risks** footer: what you did not do or check, and what could still be wrong. Write "none" only when that is true.
Mark a deliberate limit with a comment `# shortcut: <limit> — revisit when <trigger>` (any comment syntax). `osengineer debt` lists them and flags any without a trigger.
