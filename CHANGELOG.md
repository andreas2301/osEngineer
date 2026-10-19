# Changelog

All notable changes to osEngineer are tracked here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to semantic versioning.

## [Unreleased]

## [0.6.0] — 2026-10-19

0.5.0 was never tagged. This release ships both: loop 2 (enforced controls) first, then
the 0.5.0 content under "Included from the untagged 0.5.0".

**Breaking:** PHASE_PLAN frontmatter is now JSON (validated against its schema); convert
existing YAML plans. Phase changes need the human-run `osengineer approve`.

### Added

#### Ponytail rules: reuse ladder, never-cut list, review order, shortcut ledger

- **Reuse ladder in rule 2.** After reading the touched code, take the first
  option that works: not needed, already in the codebase, stdlib, an installed
  dependency, one line, and only then minimal new code. The reviewer checks it.
- **Never-cut list.** Input validation, data-loss error handling, security and
  accessibility are never simplified away, not even under a Risk-Exception.
- **Fixed review order** for the reviewer (and judge code findings): correct →
  safe → holds under load → tested → fast → lean. Each finding is numbered and
  has where / what fails / failing case / fix; at most 20; ends with
  "Not checked".
- **`osengineer debt [--json] [--check]`** lists `shortcut: <limit> — revisit
  when <trigger>` comments in tracked files and flags entries without a
  trigger; `--check` exits 1 on one. The injected rules text grew by about
  530 bytes (1974 → 2501).

#### Budget circuit breaker (it was documented but not implemented)

- **Per-task budgets in PHASE_PLAN.md.** The frontmatter is now a JSON object
  (YAML 1.2 flow syntax) validated by `repo_profile/phase_plan.py` against
  `specs/SCHEMAS/phase-plan.schema.json`. The schema is closed, and every task
  needs a `budget`: `tool_calls` and `wall_minutes` are enforced, `tokens` is
  optional and only recorded. `token_budget` and `token_estimate` are removed.
  Breaking: existing plans need the new frontmatter.
- **The plan is validated where it is used, and invalid plans are refused.**
  This covers headless `osengineer run`, plan-gated slash commands
  (prompt-guard), non-plan edits in `execute` (pre-edit-guard) and the
  post-tool meter. More than one active plan is an error.
- **Metering** (`hooks/lib/osengineer_budget.py`). While the phase is
  execute, micro or hotfix, post-tool counts tool calls and wall time (gaps
  between calls up to `budget.idleSeconds`) per `phase_id`. It also adds
  tokens from the Claude Code transcript. The counters are stored as
  `budget_*` in `runtime.yml`. `osengineer run` adds the run's wall time for
  every harness and writes a `usage` block to `RUN.json`: tool calls, wall
  time, tokens, the estimate, the ratio, the timeout and the breaker result.
- **The breaker.** It warns once at `budget.warnPct` (default 100). At
  `budget.tripPct` (default 150) it:
  - writes `.osengineer/BLOCKED.md` with the evidence;
  - logs `by: circuit-breaker` to `approvals.jsonl`;
  - sets `phase: blocked`.
  Edits, every Bash call and `osengineer run` are then refused. Only a human
  can leave `blocked`, by running `osengineer approve`. Headless runs are
  given at most the wall time left before `tripPct`.
- **The judge's cost rule and the docs now match what is enforced.** The old
  rules were "tokens > 200%" for BLOCK and "≤ 150%" for MERGE. Both now use the
  measured ratio against `budget.tripPct`. Tokens are informational only. The
  updated docs are `trust/circuit-breakers.md`, the hook headers and README,
  and the planner, verifier and budget-tracker references.

#### Human phase gate

- **`osengineer approve <phase> [--reason "<t>"]`** is now the only way to
  change the phase (`hooks/lib/phase_gate.py`). It checks:
  - an explicit transition table: Discuss → Plan → Execute → Verify → Accepted,
    plus Blocked and the micro/hotfix Micro-Phase;
  - the prerequisite artifact for the target phase: `PHASE_PLAN.md` before
    `execute`, `VERIFICATION.md` or `MICRO_PLAN.md` before closing.

  It records `phase_approved_by`/`phase_approved_at` in `state.yml` and appends
  each approval to `.osengineer/approvals.jsonl`. Headless runs refuse it.
  See `planning/PROTOCOL.md` "Phase Gate".

#### Tooling and agent rules

- **SubagentStart hook** (`hooks/osEngineer-subagent-start.py`): SessionStart
  context never reaches subagents, so every subagent now gets the session-start
  state banner (shared via `osengineer_common.state_banner`) plus the agent
  rules. Wired for Claude Code (`.claude/settings.json`) and Codex
  (`.codex/hooks.json`). Kimi runs SubagentStart hooks but drops their output,
  so it is not wired there; this gap is documented.
- **Agent rules from one source** (`templates/agent-rules.md`): install.sh
  writes it into CLAUDE.md, and the prompt guard's re-injection and the
  subagent-start hook read it. The inline copies in install.sh, the prompt
  guard and the developer agent are gone. New rules: push back with a simpler
  approach, surface multiple interpretations, remove only what your own change
  made unused, match the existing style, trace every changed line to the
  request (also a reviewer checklist item), a trivial-task exception, fail
  loudly at real boundaries with no defensive code for impossible states, and a
  **Skipped / risks** footer closing every agent report.
- `test/test_docs_drift.py`: SKILL.md paths, hook names in live docs, commands
  named by hooks, and the judge verdict set must match the tree.
- **`bin/ose-tdd-check`**: checks test-first ordering on a commit range. Each
  production commit needs a preceding `test(...)` commit, or an
  architect-granted `Risk-Exception: <class> — <reason>` trailer (docs, config,
  rename, trivial, revert, generated). Every exception is listed. CI runs it on
  PR ranges and writes the report to the job summary. `--verify-red` (opt-in)
  confirms the test commit fails. See `docs/tdd-check.md`.

### Changed

#### Evolve: the loop proposes, the owner decides

- **`osengineer evolve accept` no longer writes into the shared skill home.**
  It used to write `memory/patterns/<slug>.md` straight into the skill
  checkout from any target repo, with no review and no commit. Now it writes
  a change proposal to the target repo's `.osengineer/evolve/proposals/<id>.md`.
  The proposal has sections for what changes, why, risk, how to revert,
  evidence and the pattern. New flags: `--why`, `--risk`, `--evidence`.
  `--pattern-slug` must be lowercase letters, digits and dashes.
- **New `osengineer evolve promote <id> [--pr]`**, run by a human. It commits
  the pattern as `docs(patterns): add <slug>` on a new `evolve/<id>-<slug>`
  branch of the skill home git checkout. The working tree and the
  checked-out branch are left as they were. With `--pr` and `gh`, it pushes
  the branch and opens a PR. It refuses in headless runs (`OSE_HEADLESS=1`),
  on a non-git or dirty skill home, on a proposal with missing fields, and on
  an existing pattern or branch. Nothing is ever merged automatically.
- **`evolve promote` closes the loop on the original proposal.** The
  `EP-NNN` file in `.osengineer/evolution-proposals/` gets `status: promoted`,
  `promoted_at`, `promoted_branch`, a `skill_proposal` link and, with `--pr`,
  `promoted_pr` (also written to the skill proposal). `evolve status` counts it
  as closed.

#### Human phase gate

- `osengineer state set phase <p>` routes through `approve`, so `idle → execute`
  in one step is no longer accepted. Other keys work as before, except that the
  `phase_approved_*` record fields are refused.
- The guards refuse the agent every route to a phase change, in every phase and
  on all three harnesses:
  - `pre-edit-guard` blocks any edit of `state.yml` or `approvals.jsonl`;
  - `pre-bash-guard` blocks `approve`, `state set phase` and best-effort shell
    writes to those files.

  `OSE_BYPASS` does not lift these blocks; the refused bypass is logged.
- The discuss/plan edit block now asks the human to approve the move to
  execute; it no longer tells the agent to run `state set phase execute`.
  `/osEngineer:feature`, `fix` and `hotfix` and the verifier protocol now ask
  the human to approve as well.

### Fixed

- SKILL.md listed flat `agents/<name>.md` paths; it now lists `agents/<name>/AGENT.md`.
- Live docs (`docs/premortem_analysis.md`, `trust/denylist.md`, `agents/INDEX.md`)
  named Node-era `.js` hooks; they now name the `.py` hooks.
- The post-tool critical warning pointed to `/osEngineer:pause-work`, which never
  existed; it now advises a checkpoint commit.
- The judge frontmatter promised BLOCK / FLAG / PASS while the body, merge
  criteria and override protocol use MERGE / BLOCK; it is MERGE / BLOCK throughout.
- The agent could rewrite `.osengineer/runtime.yml` before a breaker trip and
  reset its own `budget_*` counters. The edit and bash guards (Codex
  `apply_patch` included) now refuse it like `state.yml`; hooks still write it
  in code. While the phase is `blocked`, `.osengineer/BLOCKED.md` is refused
  the same way, `OSE_BYPASS` included. BLOCKED.md stays tracked, not
  gitignored, so the human sees it.

### Included from the untagged 0.5.0

#### Added — evaluation harness for detectors, classifiers and scanners

- **`/osEngineer:recipe-eval-harness`** (`commands/osEngineer-recipe-eval-harness.md`):
  a nine-step recipe that sets up a measured keep/revert improvement loop for a
  detector repo. It covers:
  - dataset research and verification (license, gated status, pinned revision,
    sha256, benign negatives, overlap and contamination);
  - group-split dev/holdout/sealed sets with roles (PRIMARY, RECALL-ONLY,
    GUARD-ONLY, REPORT-ONLY, SEALED);
  - a deterministic fetch script and per-set P/R/F1/latency;
  - the karpathy/autoresearch-style loop;
  - process reviews, with one report branch per round;
  - a premortem and an honest assessment.
- **`eval-harness-engineer` agent** (`agents/eval-harness-engineer/`) with
  references for dataset intake, set roles, the metrics format and the
  assessment template. Hard rules:
  - never design from holdout, GUARD-ONLY, REPORT-ONLY or SEALED
    misclassifications;
  - never re-implement decision rules in a prompt;
  - verify research citations before use.
  It is installed with the other agents.
- **`specs/SCHEMAS/eval-policy.schema.json`**: decision rules as data. It
  defines the set roles and these gates:
  - per-set non-regression;
  - single-sample tolerance;
  - recall-only TP loss;
  - a generalization ratio (`holdout_gain ≥ k × dev_gain`);
  - a paired-bootstrap CI lower bound;
  - a latency budget and latency-only accept;
  - sealed-set cadence;
  - measurement hygiene.
  `min_dev_f1_gain` defaults to 0, so no threshold can exist without being
  written down.
- **`bin/ose-eval-gate`**: a stdlib-only reference evaluator. It reads a
  policy plus baseline and candidate metrics and returns ACCEPT or REVERT with
  reasons (exit 0/1, or 2 on input errors). Regression fixtures in
  `test/fixtures/eval-gate/` reproduce real loop defects under generic set
  names (`primary-a`, `small-subset`, ...), one fixture per defect:
  - `summed-holdout`: the summed-holdout check;
  - `undocumented-threshold`: the undocumented 0.01 threshold;
  - `single-sample-tolerance`: the single-sample tolerance precedent;
  - `small-set-overfit`: dev +0.43 F1 vs holdout +0.14 on a 52-positive set.
- **Eval content stays generic.** osEngineer ships no domain eval sets. The
  consuming repo supplies its own `EVAL_POLICY.json`, labeled cases and eval
  command; the recipe, agent and gate only read them.
- **`docs/eval-harness-lessons.md`**: a lessons-learned checklist. It covers
  holdout reuse and sealed sets (arXiv:1506.02629, arXiv:1502.04585), dataset
  artifacts, template-dominated and contaminated sets, dirty-tree and
  version-label hygiene, latency creep, report-branch sprawl, citation
  verification, and the regex ceiling (arXiv:2510.01529).

#### Added — repo profile (scoped coding skill and portable task runtime)

- **Repo-profile mode in the hooks.** A repository opts in with
  `.osengineer/profile.json` (`"profile": "repo"`) or
  `validation_profile: repo` in `workbench-config.yml`. In that mode the
  hooks use the configured plan directory (`planDirectory`, default `.plans`)
  instead of `planning/`, route prompts from the repository's skill registry
  (`skillRegistry`, frontmatter only, at most two hints), report the
  configured policy file, and leave edit scope to the repository's own
  policy/dispatch contract instead of the team cache.
- **Portable task runtime** (`repo_runtime/`): validate, preflight, run,
  verify and handoff for a JSON task contract (`profiles/repo/task.schema.json`)
  with base-SHA binding, path-scope checks, argv-only acceptance commands,
  hashed evidence under `<planDirectory>/osengineer/`, and an explicit runner
  (`codex` or any executable implementing the runner protocol). No runner
  means nothing executes.
- **Bounded read-only integration readers** (`repo_integrations/`) for GitHub
  (`gh`), Linear and Notion, with allowlisted scopes, page/item/text limits,
  credential redaction and an offline `doctor`. Configuration lives in
  `profiles/repo/integrations.json`; all providers are disabled by default.
- **Installer, skill and CLI verb**: `osengineer profile
  install|uninstall|runtime|integrations|learn` and
  `install.sh --profile repo <path>` install one owned skill
  (`.claude/skills/osengineer-repo-profile` plus a `.agents/skills` projection)
  with a hash manifest, and refuse to overwrite modified or unowned assets.
- **Usage learning receipts** (`repo_profile/learning.py`): record, summarize
  and compare sanitized task receipts.

#### Added — Codex CLI as a supported harness

- **`RUNTIMES=codex`** (menu option 3) wires the per-repo `.codex/hooks.json`
  with the session-start, prompt, edit and Bash guards, installs the commands
  as `.agents/skills/<verb>/SKILL.md`, and relies on the root `AGENTS.md`,
  which Codex reads natively. Re-install replaces stale osEngineer handlers.
  `uninstall.sh` removes only osEngineer handlers and unchanged skill copies.
  This reverses the earlier removal of Codex from the runtime menu.
- **`hooks/lib/codex_hook.py`** runs the unmodified guards for Codex. It
  splits `apply_patch` into one edit check per touched file and normalises
  shell tool aliases to `Bash`. It turns a block into exit 2 with the reason
  on stderr, because Codex lets an action continue when a hook prints fields
  it does not support.
- Install warns that Codex runs project hooks only after `/hooks` trust.
  Until then, the git hooks and the CI gate are the only enforcement.
- **`codexRunner`** in `.osengineer/profile.json` (default `codex`) names the
  runner executable that gets the `codex exec` protocol in `repo_runtime`.
  Before, this name was hard-coded.

#### Added — one profile configuration with fact detection

- **`repo_profile/config.py`** is the single loader for
  `.osengineer/profile.json`, shared by the hooks, `bin/osengineer`,
  `repo_runtime` and the installer. It replaces three copies of the
  policy / plan-directory / registry defaults. The rules are documented in
  `specs/SCHEMAS/repo-profile.schema.json`, and a test keeps them in step.
- **New keys**, all optional, with the previous literals as defaults:
  - `context.warnPct` / `criticalPct` / `reinjectPct` / `staleSeconds`
    (35 / 25 / 40 / 60);
  - `routing.excludeNamePattern` / `dispatchWords` / `minSignalTerms` /
    `maxHints` / `projection`;
  - `eval.policy` (`EVAL_POLICY.json`);
  - `handlers` (fact -> handler map);
  - `codexRunner`, which is now validated by the loader.
- **`osengineer profile detect --repo <path> [--write]`** runs offline file
  and PATH detectors: policy, registry, eval policy, GitHub Actions,
  Claude/Kimi/Codex harnesses, `gh`/`op`, and package managers. It prints the
  facts and a proposed `profile.json`. Only `--write` writes, and it writes
  only facts that have a known handler (for example `eval-policy` ->
  `eval.gate`).
- **`osengineer profile doctor --repo <path>`** exits 1 while a fact is
  `unhandled` (no handler exists) or `unconfigured` (a handler exists but
  has no entry). Unknown facts are never enabled. `{"enabled": false}`
  acknowledges a fact.
- **`integrations.json`** can now set `providers.github.host` (GHES),
  `providers.linear.endpoint`, `providers.notion.endpoint` and `apiVersion`,
  and `providers.secrets.schemes` (`op`, `vault`; the default is `op` only).

#### Changed

- **Migrated the entire enforcement layer from Node.js to Python 3.** All
  Claude/Kimi hooks (`osEngineer-prompt-guard`, `-pre-edit-guard`,
  `-read-guard`, `-pre-bash-guard`, `-post-tool`, `-session-start`,
  `-statusline`) plus the shared library (`hooks/lib/osengineer_common.py`,
  `osengineer_git_cmd.py`, `parse_agents_frontmatter.py`,
  `validate_agents_frontmatter.py`) are now Python 3 (stdlib only); the `.js`
  equivalents are removed. `bin/osengineer` and the inline settings/frontmatter
  logic in `install.sh`, `uninstall.sh`, `osEngineer-pre-commit.sh`, and
  `osEngineer-post-commit.sh` no longer shell out to `node`. This drops the
  Node.js runtime from the supply-chain surface — osEngineer now needs only
  Python 3, git, and bash.
- Test suite ported from Node to `unittest` (`test/test_osengineer.py`,
  `test/test_git_cmd.py`); `npm test` now runs `python3 -m unittest discover`.

- **Breaking for invalid profiles:** an invalid `.osengineer/profile.json`
  value now fails closed everywhere. Hooks block with exit 2, the runtime
  returns `needs-human`, and the installer and CLI fail. Before, an absolute
  `planDirectory`, an unknown key or a non-bare `codexRunner` silently fell
  back to the default.
- Repo-profile prompt-guard now warns at 35% context remaining, the same
  point as post-tool. Before, it warned at 40%. The thresholds are a single
  `context` setting.
- The installer records the osEngineer `VERSION` as `profileVersion`
  instead of the literal `0.1.1`. It no longer digest-owns `profile.json`:
  it merges its keys into an existing file and refuses a conflicting
  `policy` or `planDirectory`. Uninstall keeps user keys and removes only the
  repo-profile switch.

#### Fixed

- The PostToolUse hook now records the statusline bridge value as
  `context_used_pct` (context-window occupancy) instead of `budget_used`
  (which it is not), in the gitignored `runtime.yml`. The stale header comment
  promising a budget circuit-breaker is removed; none was implemented.
- `state.yml` values `null` and `~` now read as unset. Before, a
  `current_team: null` line read as a team literally named "null".
- Hooks are strict: a payload that is not a JSON object, or any hook fault,
  fails closed with a stderr diagnosis (`invalid hook input or data`) and
  exit 2. PreToolUse and UserPromptSubmit guards also print the dual-dialect
  block, so the action is blocked on Claude Code and Kimi Code. PostToolUse,
  SessionStart and the statusline cannot stop anything and fail loudly.
  Before, a bad payload exited 0 (or 1), which let the action proceed.
- Repo profile: the PostToolUse hook no longer writes
  `<planDirectory>/osengineer/context.json`, which the task runtime reported
  as an out-of-scope change on every tool call (preflight and verify
  returned needs-human). Context telemetry now goes to `.osengineer/runtime.yml`
  as in the generic profile, and the runtime ignores the hooks' volatile files.
- The pre-edit guard blocks a team whose cached `owns_paths` is missing or
  invalid instead of treating it as unrestricted, and the bypass audit log
  write now reports its failure on stderr instead of being swallowed.
- The `/osEngineer:recipe-eval-harness` description is shortened to fit the
  1024-character skill limit, so the command also loads as a skill.
- `find_osengineer_root` walks up to the home directory or filesystem root
  instead of stopping after eight levels.
- Re-running `install.sh` on an installed repo no longer appends a second copy
  of every agent under `## osEngineer Additions`. The reference-link rewrite
  made installed agents differ from their source, so each re-run took the
  append path. The installer now compares against the rendered agent, records
  pure copies in `.osengineer/agents.sha256` so an upgrade replaces them
  instead of appending, writes the Additions block in one byte-stable format
  (user content kept, osEngineer body exactly once), and collapses agent files
  that a previous re-run duplicated onto themselves.
- Commits in an installed repo no longer leave the working tree dirty.
  `install.sh` now gitignores `evolution-counter.yml` and `.state.lock` in
  `.osengineer/.gitignore` and `graphify-out/` in the repo `.gitignore`
  (creating it if absent, idempotent on re-run); the post-commit hook rewrites
  the first and the graphify rebuild writes the last on every commit, which
  broke clean-tree preconditions (`git status --porcelain`). Repos that already
  track `evolution-counter.yml` need a one-time
  `git rm --cached .osengineer/evolution-counter.yml`.
- The PostToolUse hook no longer rewrites the tracked `.osengineer/state.yml`
  on every tool call. Volatile counters (`budget_used`) are written to a new
  gitignored `.osengineer/runtime.yml`; `read_state_map` merges it over
  `state.yml`, so the statusline, banner, prompt guard and `osengineer state`
  are unchanged. `state.yml` stays tracked (the CI gate requires it) and keeps
  only phase/team/version fields that change on deliberate transitions.
- `install.sh` no longer half-installs on repos with >200 source files
  (SIGPIPE from `find | head` under `set -euo pipefail`).
- `osEngineer-post-commit.sh` dropped the `--ast-only` flag removed in
  graphify ≥0.9, so the post-commit graph refresh runs again.
- `uninstall.sh` now removes dir-style agent files (`agents/<role>/AGENT.md`);
  the previous flat-only glob left every installed agent file behind.

## [0.4.0] — 2026-06-15

### Added — P7 (closes spec-vs-reality gaps from P6 analysis)

- **`specs/SCHEMAS/agents-md.schema.json`** — JSON Schema 2020-12 validating
  workbench, repo, and team-scope `AGENTS.md` frontmatter. Three discriminated
  branches via `oneOf` keyed on `scope:`; `$defs` shared between scopes
  (semver, slug, pathArray, metaRef, teamEntry, repoEntry). `additionalProperties:
  true` on every scope so repos can extend the contract without false rejections.
- **`hooks/osEngineer-pre-commit.sh`** — now extracts YAML frontmatter from
  every staged `AGENTS.md`, converts it to JSON inline via Node, and validates
  against `agents-md.schema.json`. Missing `scope:` discriminator is a hard
  error (blocks commit); structural-shape mismatches are warnings (the schema
  is still maturing and we don't want to thrash existing repos). Validation
  uses `check-jsonschema` if available, else a Node-based fallback that
  presence-checks the discriminator and basic array typing.
- **`hooks/osEngineer-prompt-guard.js`** — frontmatter-driven skill routing.
  Reads all `agents/<role>/AGENT.md` + `commands/osEngineer-*.md` frontmatter
  from `$OSENGINEER_HOME`, scores each against the user's prompt (token
  overlap against the "Use when …" sentence, name substring bonus, "Don't
  use when" penalty), and appends the top 3 matches with score > 0.15 as
  `osEngineer routing hints` to `additionalContext`. State injection, amnesia
  guard, debouncing, and execute-blocking preserved. ~50ms added latency.
- **Per-team denylist overrides** in `hooks/osEngineer-pre-bash-guard.js`.
  Reads `<repo>/.osengineer/denylist-overrides.json` and
  `<repo>/.osengineer/teams/<current_team>/denylist-overrides.json` if
  present; team-level merges on top of repo-level. Three operations:
  `disabled` (skip a global pattern silently), `downgraded_to_warning`
  (still emit advisory `additionalContext` but allow), `added` (extend
  with team-specific patterns). Every effective override is logged to
  `.osengineer/override-log.jsonl` for auditability. Malformed override
  files are treated as missing — global denylist always remains enforced.
- **`trust/denylist.md`** — new "Per-team overrides" section documenting
  the schema, resolution rules, and audit-trail entries.
- **`templates/denylist-overrides.json.tmpl`** — starter file with one
  `disabled`, one `downgraded_to_warning`, and one `added` example.

### Verified

- 21/21 tests pass.
- Schema validates 3 well-formed sample frontmatters (one per scope) and
  rejects 4 deliberately bad samples (wrong scope, missing scope, wrong
  schema_version, capitalised team_id) with clear errors.
- Prompt-guard smoke test on `"I need to write a failing test for execute
  phase task"` returns 3 routing hints (qa, topology-validator, reviewer).
- Pre-bash-guard smoke test with a `denylist-overrides.json` containing
  `{"disabled": ["docker rm / volume rm / system prune"]}` correctly allows
  `docker volume rm test-vol` and logs `disabled_applied` to
  `override-log.jsonl`.

## [0.3.0] — 2026-06-14

### Added — P6 (inspired by google/skills analysis)

- **`trust/denylist.md`** — human-readable contract listing every Bash pattern
  blocked by `osEngineer-pre-bash-guard.js`. The hook now reads the JSON block
  from this file at runtime (with a hardcoded fallback). Edit the file, no
  rebuild needed. Patterns expanded to cover `npm install` of arbitrary
  packages, `pip install`, `curl|sh`, `kubectl apply -f remote-url`, `mkfs`,
  `dd of=/dev/*`, `chmod 777`, and the existing filesystem/git/container/k8s
  baseline.
- **Frontmatter convention** documented in `templates/frontmatter-pattern.md`.
  Applied to anchor files (`architect.md`, `developer.md`, `judge.md`,
  `red-team-local.md`, `osEngineer-init.md`, `osEngineer-plan.md`,
  `osEngineer-fix.md`, `osEngineer-verify.md`) following the
  `google/skills` "Use when … Don't use when …" grammar. Remaining 15 agents
  + 7 commands follow the same pattern in subsequent commits.
- **Three recipe commands** for multi-step linear workflows with single-question
  policy and check-before-mutate audits:
  - `/osEngineer:recipe-onboard-repo`
  - `/osEngineer:recipe-spin-up-sandbox`
  - `/osEngineer:recipe-cut-release`
- **`osengineer scaffold (agent|command) <name>`** subcommand — materialises
  new agent or command files from `templates/agent.md.tmpl` and
  `templates/command.md.tmpl`. Refuses to overwrite existing files. Wired into
  `osengineer explain scaffold`.

### Changed

- `SKILL.md` — replaced the "External Skill Integrations" table (which listed
  GSD as an external dependency) with a "Standalone — no external skill
  dependencies" section that surfaces the zero-npm-dependency property and
  records historical provenance via ADR-001.
- `planning/PROTOCOL.md` — removed the "adapted from get-shit-done" prose
  marker in favour of an ADR-001 reference.
- `hooks/osEngineer-pre-bash-guard.js` — now loads patterns from
  `trust/denylist.md`; hardcoded array retained only as fallback.
- All `OSE_BYPASS=1` invocations are now logged consistently to
  `.osengineer/bypass-log.jsonl` with timestamp, hook name, reason, and
  truncated command.

### Added — P6.2 (agent-dir-split)

- Refactored all 22 agents from flat `agents/<role>.md` into
  `agents/<role>/{AGENT.md, references/*.md}` following the
  `google/skills` per-product layout. Each `AGENT.md` keeps the frontmatter,
  mandate, protocol overview, and escalation rules; heavy reference material
  (domain specifics, command catalogs, code patterns) moved into the
  `references/` subdirectory.
- 17 agents got split with references (architect: 5, cert-monitor: 5,
  developer: 6, health-verifier: 3, judge: 4, live-system-operator: 4,
  metrics-onboarding: 4, planner: 2, red-team-architect: 4,
  red-team-local: 3, researcher: 4, reviewer: 3, sandbox-provisioner: 3,
  scope-manager: 5, tech-writer: 4, topology-validator: 3, verifier: 4).
- 5 small agents kept whole (budget-tracker, dba, qa, sync-agent,
  ui-ux-designer) — their entire body fits cleanly in `AGENT.md` and a
  `references/` subdirectory would add ceremony without value.
- `install.sh` MANDATORY_AGENTS copy loop now sources from
  `agents/<role>/AGENT.md` (falls back to flat `agents/<role>.md` for
  backward compatibility with older skill checkouts) and writes a flat
  `<repo>/.claude/agents/<role>.md` per Claude Code's expectations. Per-
  repo footprint stays flat-and-lean; the rich `references/` material
  remains in the osEngineer skill home and is loaded on demand.
- Updated `agents/INDEX.md` to reflect the new layout convention.

Net effect: smaller AGENT.md token cost on every activation, while
heavyweight references are reachable via relative links from inside the
AGENT.md body.

### Security / supply-chain

- Verified `package.json` declares zero `dependencies` and zero
  `devDependencies`. Tests use Node's built-in `node:test`. Hooks and CLI
  use only Node built-ins (`fs`, `path`, `os`, `child_process`). The
  `npx` reference in `install.sh` is a presence-check diagnostic only —
  no install ever runs.
- New denylist patterns block accidental `npm install <pkg>`, `pip install`,
  and `curl|sh` invocations without an active 4-part plan, raising the bar
  for unsanctioned supply-chain inflows on osEngineer-initialised repos.

## [0.2.0] — 2026-05-20

### Added — P1 of multi-phase design

- **10 enforcement hooks** under `hooks/osEngineer-*` covering Conventional
  Commits, schema validation, graphify auto-rebuild, phase/state injection,
  destructive-command blocking, read-before-edit advisory, context monitoring,
  session-start banner, and statusline rendering.
- **`hooks/lib/osengineer-git-cmd.js`** — token-walk git command classifier
  for accurate `git commit` detection (env-prefix, `-C path`, full-path forms).
- **`bin/osengineer`** — Node CLI with `init`, `state`, `version`, `explain`
  subcommands.
- **`VERSION`** — semver source of truth at the repo root (`0.2.0`).
- **`docs/adr/ADR-001-gsd-merge.md`** — records the get-shit-done hook
  port with source SHA `40a442b21f8b7a0df252efdf4b6ac4defd9d3a1f`.
- **`docs/superpowers/specs/2026-05-20-osEngineer-design.md`** — full design
  spec for the 7-layer real-enforcement, multi-repo, per-team model.

### Changed

- **`install.sh`** — refactored to deliver agents into target `.claude/agents/`,
  symlink all 10 osEngineer hooks into `.git/hooks/`, merge Claude hook entries
  into `.claude/settings.json` (no overwrite), drop a `CLAUDE.md` template if
  absent, and initialise `.osengineer/state.yml`.
- Old `hooks/post-commit-graphify.sh` and `hooks/pre-commit-schema-lint.sh`
  removed — superseded by `osEngineer-post-commit.sh` and
  `osEngineer-pre-commit.sh` respectively.

### Removed

- All external references to `gsd-*`, `get-shit-done`, and `GSD-Antigravity`
  except in `ADR-001` (historical record).

## [0.1.0] — 2026-05-20

Initial scaffold: 19 agents, 7 slash commands, planning / discovery / specs /
memory / trust / live-system / hooks / integrations directories with PROTOCOL
and TEMPLATES files, basic `install.sh` and `uninstall.sh`.
