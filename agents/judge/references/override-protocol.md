# Override Protocol

If the judge blocks but the human wants to override:

1. Human writes `OVERRIDE.md` with:
   - Rule being overridden.
   - Risk accepted.
   - Mitigation plan.
   - Sign-off: human name + date.
2. Judge appends override to `memory/retrospectives/`.
3. Merge proceeds with `overridden-by: <human>` tag.
