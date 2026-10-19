# hooks/

Python hooks adapt local assistant events; shell hooks implement Git checks.
Python guards read JSON payloads from stdin. Hooks are strict: a payload that is
not a JSON object, or any unexpected hook error, is reported on stderr and exits 2
(Claude Code's block signal). The PreToolUse guards (edit, Bash, read) and the
UserPromptSubmit guard also print the dual-dialect block that Kimi Code honours.
PostToolUse (the tool already ran), SessionStart, SubagentStart and the statusline cannot block,
so they fail loudly with exit 2 and stderr only. A parseable object without the
fields a hook acts on is a no-op. Runners must treat guard failures as failed
checks rather than assuming that a failed hook granted permission. `OSE_BYPASS=1` is an explicit,
audited bypass in the edit, Bash and prompt guards.

## Codex CLI

Codex runs each guard through `lib/codex_hook.py <guard>` from `.codex/hooks.json`.
The adapter turns each file in an `apply_patch` into one `Edit` payload, with paths
resolved against the payload `cwd`. It also normalises shell tool aliases and argv
commands to `Bash`. A guard block becomes exit 2 with the reason on stderr. Context
becomes `hookSpecificOutput.additionalContext` only. If a guard exits non-zero, the
adapter passes that exit code through unchanged. `post-tool`, `read-guard` and
`statusline` are not wired on Codex.

## Repo profile

Activate with `.osengineer/profile.json` containing `{"profile":"repo"}`,
or `validation_profile: repo` in `.osengineer/workbench-config.yml`.
The prompt hook routes through the skill registry (`skillRegistry` in `.osengineer/profile.json`, default `.osengineer/skill-registry.json`) using registry
`skills[].name`, `canonical` and `projections.codex`. It reads at most 8 KiB of
frontmatter per available skill and emits at most `routing.maxHints` (default two) matching paths, including
aliases for the configured dispatch skill (`dispatchSkill`, default `dispatch`; `routing.dispatchWords`). Skill names
matching `routing.excludeNamePattern` (default reviewer/verifier/judge) are excluded. It never loads complete skill bodies into the prompt.
Repo profile plans are referenced under the configured plan directory (`planDirectory`, default `.plans/`); no planning directory is
created by these hooks. The generic profile keeps its `planning/` namespace.

Prompt summaries are emitted only on phase, route or context-level changes for a
valid session. Low context causes a compact checkpoint reminder, not repeated
policy text. Context warnings occur on warning/critical transitions and rearm
after recovery. Thresholds are percent remaining from `context` in
`.osengineer/profile.json`: warning at `warnPct` (35), critical at `criticalPct` (25),
shared by post-tool and prompt-guard; the generic prompt-guard re-injects the plan
at `reinjectPct` (40). Temporary metrics expire after `staleSeconds` (60). Telemetry records
`context_used_pct`, which is context-window occupancy, **not task token spend**.
Both profiles store it in the gitignored `.osengineer/runtime.yml`; repo profile
does not create an independent `.osengineer/state.yml`, and nothing is written to
the runtime's `<planDirectory>/osengineer/` evidence namespace. Repo profile execution
scope comes from repository policy and the dispatch contract, not legacy team
`owns_paths` caches. Generic profiles deny execution edits if the active team
cache has missing or malformed ownership configuration.
Post-tool also runs the budget circuit breaker (trust/circuit-breakers.md): in
`execute`/`micro`/`hotfix` with one valid active PHASE_PLAN.md it counts tool
calls and wall time against the summed task budgets (`budget_*` in runtime.yml,
tokens from the transcript recorded only), warns at `budget.warnPct` (100) and at
`budget.tripPct` (150) writes `.osengineer/BLOCKED.md`, logs `by: circuit-breaker`
to approvals.jsonl and sets phase `blocked`. `budget.idleSeconds` (900) caps the
wall time credited per gap. Claude Code only: Kimi and Codex have no PostToolUse
wiring. The bash guard refuses every command while the phase is `blocked`.

The edit guard denies edits during `blocked` and `suspended` until explicit
resume, and checks team ownership during execution. Nested working directories
resolve the repository configuration before destructive-command checks.
These local hooks are defense in depth; a headless runner must enforce its own
permissions and contract checks. They do not provide a complete shell sandbox.

Run payload regressions with:

```sh
python3 -m unittest discover -s test -p test_repo_profile_hooks.py -v
```
