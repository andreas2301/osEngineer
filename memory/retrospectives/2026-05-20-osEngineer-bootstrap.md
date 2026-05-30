# Retrospective: osEngineer bootstrap (Phases P1 + P2)

**Date:** 2026-05-20
**Phases covered:** P1 (real-enforcement spine) and P2 (markdown gap closure)
**Token budget:** TBD vs actual at end of session

## What we built

- **P1:** ported 10 enforcement hooks from get-shit-done with full rename
  to `osEngineer-*`, dropped a Node CLI at `bin/osengineer`, refactored
  `install.sh` to deliver agents + git hooks + Claude settings, wrote
  ADR-001 documenting the merge protocol with source SHA. Smoke-tested
  end-to-end: bad commits rejected, good commits accepted, state.yml
  populated.
- **P2:** wrote 4 JSON Schemas (agents-md, phase-plan, service-manifest,
  message-contract) + 2 spec templates, seeded 3 real reference-project
  patterns + this retrospective, wrote `agents/architect.md` and
  `agents/verifier.md`, merged the root `AGENTS.md` catalog into
  `agents/INDEX.md`, populated `/osEngineer:fix` and `:feature` command
  files with real orchestration logic.

## What went well

- **Reading get-shit-done's hooks before porting saved time** — the
  token-walk git classifier (`hooks/lib/osengineer-git-cmd.js`) was
  ported verbatim and immediately worked. Would have wasted hours
  rewriting it from scratch.
- **Smoke-testing inside a tmp git repo before committing** — caught
  zero issues, but the practice would have caught any. Cheap insurance.
- **Brainstorm-first flow** (per the user's superpowers skill) produced
  a written spec at `docs/superpowers/specs/2026-05-20-osEngineer-design.md`
  that anchored every subsequent decision. Re-reading the spec table of
  10 hooks made the porting mechanical.
- **The user's "no calendar estimates" directive** kept the work pace
  natural — no artificial deadline pressure, no padding for "buffer."

## What we'd do differently

- **The validate-commit hook was initially shaped as a Claude PreToolUse
  hook**, but the spec said "git commit-msg." Caught and rewrote before
  shipping. Next time: read the spec's trigger column carefully before
  writing.
- **The hooks/lib path resolution** initially used `dirname "$0"` which
  doesn't follow symlinks. Sidestepped by switching install.sh from
  symlinks to copies, but this means hook updates require re-running
  `install.sh`. Future fix: substitute `OSENGINEER_HOME` at install time.

## Patterns surfaced (promoted to memory/patterns/)

- `queue-declare-before-consume` — AMQP consumer-side queue declaration (moved to `examples/sovereign-shield/patterns/`)
- `dual-listen-migration` — three-deploy-cycle routing key migration (moved to `examples/sovereign-shield/patterns/`)
- `fail-closed-on-tls-error` — degrade-not-panic on TLS init failure (moved to `examples/sovereign-shield/patterns/`)

## Open follow-ups (carried into P3+)

- P3: team-folder model — auto-detect Go/Ansible/test layouts; cross-team
  handoff filesystem protocol; activate `owns_paths` in the pre-edit
  guard.
- P4: workbench mode polish — META detection refinement, Confluence MCP
  fleshing out to a real config (currently 6 lines in
  `integrations/confluence-mcp.md`).
- P5: evolution loop — wire the auto-nudge banner to actually fire at
  counter ≥ 5, build `/osEngineer:evolve` HITL flow, RETROSPECTIVE.md
  auto-generation post-merge.
- The `osEngineer-pre-commit` hook's AGENTS.md frontmatter validation
  fires only when `OSENGINEER_HOME` env is set; install.sh now sets it
  in `.claude/settings.json` env block, but git hooks run outside Claude
  so the schema validation skips. Acceptable for P2 (schemas exist but
  schema-against-AGENTS.md isn't a blocking gate yet).

## Cost recalibration

- Filed for end of bootstrap session.
- Future osEngineer phases inside this skill repo: budget assumes
  `discuss + plan` together cost ~6K tokens; `execute` cost scales with
  the size of the spec section being implemented.
