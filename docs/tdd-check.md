# Test-first ordering check (`bin/ose-tdd-check`)

CI runs `bin/ose-tdd-check BASE..HEAD` on every PR range. It checks commit
ordering, not coverage.

- **Production commit**: changes a file under `bin/`, `hooks/`, `repo_runtime/`,
  `repo_profile/`, `repo_integrations/`, `profiles/*/scripts/`,
  `live-system/*.sh`, `install.sh` or `uninstall.sh`. Markdown never counts.
  Override with `--prod GLOB` (repeatable, replaces the defaults).
- **Test commit**: subject type `test(...)` and changes `test/*`
  (`--tests GLOB` to override).
- **Rule**: each production commit needs a test commit on its first-parent
  chain after the previous production commit. One test commit covers one
  production commit. Merge commits are skipped.
- **Risk exception**: otherwise the commit must end with a trailer granted by
  the architect agent (no other role may grant one):

  ```
  Risk-Exception: <class> — <reason>
  ```

  `<class>` is one of `docs`, `config`, `rename`, `trivial`, `revert`,
  `generated`. Following ponytail's proportional-test rule, trivial changes
  need no test, but risky logic (branches, loops, parsers, money, security)
  always needs one and never gets an exception. Every exception in the range
  is printed and appended to the CI job summary for human review.
- **`--verify-red`** (opt-in, off in CI): checks out each covering test commit
  in a temporary worktree and requires `--test-cmd` to fail there. It runs the
  suite once per test commit (over 2 minutes each for this repo), so it is a
  local tool.

Exit codes: 0 PASS, 1 FAIL, 2 input error.
