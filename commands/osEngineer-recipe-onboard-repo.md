---
name: osEngineer:recipe-onboard-repo
description: >-
  Linear recipe for onboarding a new repo into an existing osEngineer
  workbench. Detects folder→team mapping, drafts AGENTS.md, installs hooks,
  copies agents, seeds .osengineer/, registers the repo in the workbench
  AGENTS.md, and runs a smoke verify. Single-question policy: asks at most
  one question per step; defaults to recommended choices. Check-before-mutate:
  every filesystem mutation requires either user confirmation (interactive)
  or a `--yes` flag (CI). Use when adding a freshly-cloned repo to a
  workbench. Don't use to re-initialise an already-onboarded repo (run
  /osEngineer:init instead — recipes assume greenfield state).
phase_allowed: [idle]
phase_after: idle
recipe_steps: 7
---

# /osEngineer:recipe-onboard-repo

Linear workflow for adding a new repo to an existing osEngineer workbench. Inspired by `google/skills/google-cloud-recipe-onboarding`'s staged approach with single-question and check-before-mutate policies.

**Syntax:** `/osEngineer:recipe-onboard-repo <repo-path> [--yes]`

## Preconditions

- The target directory exists, contains a `.git` directory, and the working tree is clean.
- The workbench root (the parent directory) has its own `AGENTS.md` with `scope: workbench`.
- osEngineer is installed (`bin/osengineer` is on PATH or in a known location).

If any precondition fails, the recipe stops at step 1 and reports which one. Don't auto-fix preconditions — that's outside this recipe's scope.

## Single-Question Policy

Each step asks **at most one question** of the user. Default values are pre-filled from heuristics (current `pwd`, workbench config, repo content). The user can accept the default with Enter or override. With `--yes`, every question accepts the default.

## Check-Before-Mutate Audits

Before any filesystem write, the recipe prints:
1. The exact file path to be created or modified
2. A unified diff against existing content (or the full content if new)
3. A confirmation prompt unless `--yes` is set

No silent mutations. Bypassing this check is forbidden in the recipe and would not survive review.

## Steps

### Step 1 — Verify preconditions
Check `.git/` exists, `git status --porcelain` is empty, workbench `AGENTS.md` has `scope: workbench`. Report status; abort on any failure.

### Step 2 — Detect folder→team mapping
Run `osengineer detect-teams <repo-path>` to produce a proposed `teams:` block. Probes Go modules (→ coding), `ansible/`, `roles/` (→ infra), `*_test.go` (→ testing), `docs/` (→ docs), `.github/codeql/` or `security/` (→ security).
**Question (1 of recipe):** "Proposed team map looks like {...}. Edit before writing? (y/N)" — default N. If yes, drop the user into `$EDITOR`.

### Step 3 — Draft AGENTS.md
Render `templates/AGENTS.md.repo.tmpl` with the detected teams. Print the unified diff (full content, since file is new). Confirm write unless `--yes`.

### Step 4 — Install enforcement
Run `bash install.sh <repo-path>` non-interactively. Captures stdout to `.osengineer/install.log` in the repo. Verifies that:
- `.osengineer/state.yml` exists with `phase: idle`
- Three git hooks are present and executable
- `.claude/settings.json` has `osEngineer-*` hook entries
- `.claude/agents/` contains the 17 mandatory agent files

### Step 5 — Register in workbench
Append the new repo to the workbench `AGENTS.md` frontmatter `repos:` list. Print diff. Confirm.

### Step 6 — Smoke verify
- Run `osengineer state` from the repo root → must print `phase: idle`.
- Run a no-op `git commit --allow-empty -m "chore: osEngineer onboarding marker"` → commit-msg hook must accept.
- Run `git commit --allow-empty -m "broken"` (immediately reverted with `git reset --soft HEAD~1`) → commit-msg hook must reject.
- Confirm `.osengineer/bypass-log.jsonl` exists (empty is fine).

### Step 7 — Report
Print:
- Path to the new `AGENTS.md`
- Path to `.osengineer/state.yml`
- Suggested next command (`/osEngineer:discuss` or `/osEngineer:plan`)
- Any warnings from install.log

## Failure handling

Each step has an independent rollback. If step 4 (install) fails, steps 1–3 artifacts (AGENTS.md, no-op state) stay on disk for the user to inspect; the workbench `AGENTS.md` is NOT modified. The recipe never partially mutates beyond the step that failed.

## What this recipe deliberately does not do

- Does not edit hooks
- Does not write team manifests per folder (P3 already handles auto-detection at install time; per-team `AGENTS.md` files inside each team folder are scaffolded by `osengineer scaffold-team` — different command)
- Does not create the workbench itself (use `/osEngineer:init --workbench` for that)
- Does not run any tests in the repo (use `/osEngineer:verify` after planning)
