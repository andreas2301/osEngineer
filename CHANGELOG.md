# Changelog

All notable changes to osEngineer are tracked here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to semantic versioning.

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
