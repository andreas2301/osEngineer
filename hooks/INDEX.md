# hooks/ INDEX

osEngineer enforcement layer. Installed by `install.sh`. All hooks honour
`OSE_BYPASS=1` and log bypasses to `.osengineer/bypass-log.jsonl`.

## Git hooks (copied into `.git/hooks/`)

- [osEngineer-validate-commit.sh](osEngineer-validate-commit.sh) — `commit-msg`: enforce Conventional Commits
- [osEngineer-pre-commit.sh](osEngineer-pre-commit.sh) — `pre-commit`: validate JSON Schema docs touched in commit
- [osEngineer-post-commit.sh](osEngineer-post-commit.sh) — `post-commit`: auto-rebuild graphify (AST-only); increment evolution counter

## Claude Code hooks (referenced from `.claude/settings.json`)

- [osEngineer-prompt-guard.js](osEngineer-prompt-guard.js) — `UserPromptSubmit`: inject phase/team/budget state; block `/osEngineer:execute` when no PHASE_PLAN.md exists
- [osEngineer-pre-edit-guard.js](osEngineer-pre-edit-guard.js) — `PreToolUse` on Write/Edit/NotebookEdit: block edits during discuss/plan phases; block `/opt/sovereign-shield/` writes; team `owns_paths` validation (P3+)
- [osEngineer-pre-bash-guard.js](osEngineer-pre-bash-guard.js) — `PreToolUse` on Bash: block destructive commands (`rm -rf`, `git push --force`, `docker rm`, `kubectl delete`, `git reset --hard`) without an active 4-part plan
- [osEngineer-read-guard.js](osEngineer-read-guard.js) — `PreToolUse` on Write/Edit: advisory "read before edit" reminder (no-op on Claude Code itself which enforces natively)
- [osEngineer-post-tool.js](osEngineer-post-tool.js) — `PostToolUse`: track context window; mirror used_pct into `state.yml`; emit warnings at 35% / 25% remaining
- [osEngineer-session-start.js](osEngineer-session-start.js) — `SessionStart`: emit banner with phase / team / budget / open handoffs / auto-nudge

## Statusline

- [osEngineer-statusline.js](osEngineer-statusline.js) — renders `model · phase:X · team:Y · b:N% · HO:K · dirname [context bar]`; also writes context metrics to `/tmp/claude-ctx-{session_id}.json` for the PostToolUse hook to consume

## Library

- [lib/osengineer-git-cmd.js](lib/osengineer-git-cmd.js) — token-walk git command classifier (handles `git -C path`, `VAR=x git`, `/usr/bin/git` forms)
