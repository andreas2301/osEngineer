# osEngineer

## osEngineer

This repo is initialised with osEngineer. See `AGENTS.md` for the team layout
and `.osengineer/state.yml` for current phase state. Run `osengineer explain`
for the concept overview.

Key operational facts:
- **Conventional Commits** are enforced by the `commit-msg` git hook.
- **TDD** is enforced for production code: red → green → refactor, atomic commits.
- **Destructive bash** is blocked without an active 4-part plan.
- **Override any rule** with `OSE_BYPASS=1` — every bypass logged.

## Baseline & Extended Agent Rules

### Baseline Rules
1. **Think Before Coding**: State assumptions explicitly. If an instruction is ambiguous, name what is confusing and ask instead of guessing.
2. **Simplicity First**: Write the minimum code that solves the problem. No speculative abstractions or flexibility that wasn't explicitly requested.
3. **Surgical Changes**: Touch only what the task requires. Do not "improve" adjacent code, reformat, or refactor things that aren't broken.
4. **Goal-Driven Execution**: Turn vague instructions into verifiable targets. Create tests first to reproduce the issue, then loop until it passes.

### Extended Agent Rules
5. **Set Hard Token Budgets**: Stop runaway iterations by placing strict context limits.
6. **Expose Conflicts**: Don't blindly average contradictory patterns in the codebase.
7. **Read Before Writing**: Scan existing code before making edits to prevent duplication.
8. **Test Real Logic**: Ensure tests validate actual logic rather than just running to pass.
9. **Use Checkpoints**: Utilize checkpoints for long-running, multi-step tasks.
10. **Fail Explicitly**: Avoid silent failures that just appear successful.
