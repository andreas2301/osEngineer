# Changelog

All notable changes to osEngineer are tracked here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to semantic versioning.

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
