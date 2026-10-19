# hooks/ INDEX

osEngineer enforcement layer. Installed by `install.sh`. All hooks honour
`OSE_BYPASS=1` and log bypasses to `.osengineer/bypass-log.jsonl`.

## Git hooks (copied into `.git/hooks/`)

- [osEngineer-validate-commit.sh](osEngineer-validate-commit.sh) — `commit-msg`: enforce Conventional Commits
- [osEngineer-pre-commit.sh](osEngineer-pre-commit.sh) — `pre-commit`: validate JSON Schema docs touched in commit
- [osEngineer-post-commit.sh](osEngineer-post-commit.sh) — `post-commit`: auto-rebuild graphify (AST-only); increment evolution counter

## Claude Code hooks (referenced from `.claude/settings.json`)

- [osEngineer-prompt-guard.py](osEngineer-prompt-guard.py) — `UserPromptSubmit`: inject phase/team/budget state; block `/osEngineer:execute` when no PHASE_PLAN.md exists
- [osEngineer-pre-edit-guard.py](osEngineer-pre-edit-guard.py) — `PreToolUse` on Write/Edit/NotebookEdit: block edits during discuss/plan phases; block `/opt/sovereign-shield/` writes; team `owns_paths` validation (P3+)
- [osEngineer-pre-bash-guard.py](osEngineer-pre-bash-guard.py) — `PreToolUse` on Bash: block destructive commands (`rm -rf`, `git push --force`, `docker rm`, `kubectl delete`, `git reset --hard`) without an active 4-part plan
- [osEngineer-read-guard.py](osEngineer-read-guard.py) — `PreToolUse` on Write/Edit: advisory "read before edit" reminder (no-op on Claude Code itself which enforces natively)
- [osEngineer-post-tool.py](osEngineer-post-tool.py) — `PostToolUse`: track context window; mirror used_pct into `state.yml`; emit warnings at `context.warnPct` / `criticalPct` remaining (default 35% / 25%)
- [osEngineer-session-start.py](osEngineer-session-start.py) — `SessionStart`: emit banner with phase / team / budget / open handoffs / auto-nudge

## Statusline

- [osEngineer-statusline.py](osEngineer-statusline.py) — renders `model · phase:X · team:Y · b:N% · HO:K · dirname [context bar]`; also writes context metrics to `/tmp/claude-ctx-{session_id}.json` for the PostToolUse hook to consume

## Library

- [lib/osengineer-git-cmd.py](lib/osengineer-git-cmd.py) — token-walk git command classifier (handles `git -C path`, `VAR=x git`, `/usr/bin/git` forms)
