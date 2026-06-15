# Changelog

All notable changes to osEngineer are tracked here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to semantic versioning.

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
