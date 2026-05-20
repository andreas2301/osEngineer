# ADR-001 — get-shit-done hook merge into osEngineer

**Status:** Accepted — 2026-05-20
**Decision-makers:** Andreas
**Supersedes:** None

## Context

osEngineer (this repo, scaffolded 2026-05-20) needs a runtime-enforcement
layer. Markdown protocols alone cannot guarantee TDD, conventional commits,
phase gates, or budget circuit-breakers — only code can. The
`get-shit-done` project at `d:\Repositories\get-shit-done\` already ships a
mature enforcement layer: a Node SDK, 14 git/Claude hooks, and a statusline.

Two paths were considered:

1. **Build osEngineer's enforcement from scratch.** Maximum control, but
   slow and risks reinventing edge-case handling that GSD has already
   accumulated (token-walk git classifiers, hook stdin timeouts, debounce
   logic, context-bridge files).
2. **Port the relevant hooks from get-shit-done and rename them.** Faster
   path to a working enforcement spine; clean copy means no live coupling
   to upstream; rename ensures osEngineer has no external skill references.

## Decision

Adopted **path 2**: copy relevant hooks, rename `gsd-*` → `osEngineer-*`,
adapt config paths from `.planning/` → `.osengineer/`, drop GSD-specific
features that don't apply (GSD update banner, npm package check), retain
the algorithmic core (Conventional Commits regex, token-walk git
classifier, graphify gate ordering, debounce + escalation logic).

## Merge protocol

- **Source repository:** `d:\Repositories\get-shit-done\`
- **Source SHA:** `40a442b21f8b7a0df252efdf4b6ac4defd9d3a1f` (HEAD at port time)
- **Form of merge:** clean copy, NOT a git submodule. The two repos diverge
  from this point on. No upstream auto-pull.
- **Future upstream patches:** if a useful upstream change lands later,
  port it manually with a new ADR (ADR-002 etc.) referencing the new SHA.

## Rename mapping

| From (get-shit-done) | To (osEngineer) |
|---|---|
| `bin/gsd-sdk.js` | `bin/osengineer` (rebuilt fresh, not a port — see below) |
| `hooks/gsd-validate-commit.sh` | `hooks/osEngineer-validate-commit.sh` |
| `hooks/gsd-graphify-update.sh` | `hooks/osEngineer-post-commit.sh` (merged with prior osEngineer post-commit) |
| `hooks/gsd-prompt-guard.js` | `hooks/osEngineer-prompt-guard.js` (repurposed: state injection rather than injection scanning) |
| `hooks/gsd-read-guard.js` | `hooks/osEngineer-read-guard.js` |
| `hooks/gsd-workflow-guard.js` | `hooks/osEngineer-pre-bash-guard.js` (repurposed for destructive bash blocking) |
| `hooks/gsd-context-monitor.js` | `hooks/osEngineer-post-tool.js` |
| `hooks/gsd-update-banner.js` | `hooks/osEngineer-session-start.js` (repurposed: reads `.osengineer/state.yml` instead of npm cache) |
| `hooks/gsd-statusline.js` | `hooks/osEngineer-statusline.js` |
| `hooks/lib/git-cmd.js` | `hooks/lib/osengineer-git-cmd.js` (verbatim port) |
| `.planning/config.json` | `.osengineer/state.yml` (YAML, not JSON) |
| `.planning/STATE.md` | `.osengineer/state.yml` |
| `{{GSD_VERSION}}` placeholder | `{{OSENGINEER_VERSION}}` placeholder (substituted by install.sh) |

### NOT ported

- `bin/install.js` — 11.5K-line GSD installer; osEngineer ships its own
  `install.sh` shaped for the three-level workbench/repo/team model.
- `sdk/dist/cli.js` — compiled GSD CLI; osEngineer's `bin/osengineer` is a
  fresh ~150-line Node script with subcommands specific to osEngineer.
- `hooks/gsd-check-update.js` and `gsd-check-update-worker.js` — npm
  update checker; not applicable until osEngineer is published.
- `hooks/gsd-read-injection-scanner.js` — defer to P5 (evolution layer).
- `hooks/gsd-session-state.sh` — replaced by `osEngineer-session-start.js`
  which reads the new state schema.
- `hooks/gsd-phase-boundary.sh` — phase transition validation moves into
  `bin/osengineer` directly.

## Consequences

**Positive**
- osEngineer has a working enforcement spine without months of original
  hook engineering.
- ADR-001 makes the merge auditable: a single commit and a single SHA
  reference, easy to revisit if a regression appears.
- Clean rename means no external "GSD" identifiers leak into agents,
  prompts, or settings files.

**Negative**
- Drift risk: upstream get-shit-done improvements will not flow back
  automatically. Manual port discipline required.
- Some GSD-specific edge cases (issue numbers like #2974, #2520) are
  embedded in the original code logic; the port stripped issue references
  but kept the algorithmic behaviour. Future debuggers won't have the
  upstream issue trail.

**Neutral**
- License: get-shit-done is MIT. osEngineer is MIT. No conflict.
- No npm dependency on `get-shit-done-cc` is introduced — copies are
  in-tree.
