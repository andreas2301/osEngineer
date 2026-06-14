---
name: osEngineer:recipe-cut-release
description: >-
  Linear recipe for cutting a release across one or more repos in a workbench.
  Verifies VERIFICATION.md exists, bumps VERSION files (semver), updates
  CHANGELOG.md, creates an annotated git tag, pushes (with explicit user
  confirmation), and triggers any post-release hooks declared in
  workbench-config.yml. Use when a phase is in `accepted` state and the
  release is ready to publish. Don't use to bypass the judge or verifier —
  this recipe assumes those gates have already passed; don't use for
  cross-workbench coordinated releases (P7 feature).
phase_allowed: [accepted]
phase_after: idle
recipe_steps: 8
---

# /osEngineer:recipe-cut-release

Cut a coordinated release across one or more repos. Multi-step, multi-repo, **destructive at the push step** — every mutation outside the local working tree requires explicit confirmation.

**Syntax:** `/osEngineer:recipe-cut-release <bump-type> [--repos a,b,c] [--yes]`

Where `<bump-type>` is `major | minor | patch`.

## Preconditions

- One or more repos are listed in `--repos`, or the recipe runs on every repo in the workbench that has `phase: accepted`.
- Every target repo has:
  - `phase: accepted` in `.osengineer/state.yml`
  - `VERIFICATION.md` in its latest `planning/active/<phase>/` directory
  - `VERSION` file at the repo root (semver)
  - `CHANGELOG.md` at the repo root
  - Clean working tree (`git status --porcelain` empty)
- Current user has push permissions to the remote(s).

## Single-Question Policy

At most **one question per step**; the push step (step 7) asks one explicit "y/N to push" regardless of `--yes` because it crosses the local↔remote boundary. The `--yes` flag accepts every other default but does NOT auto-confirm the push.

## Check-Before-Mutate Audits

Every VERSION bump, CHANGELOG edit, and tag creation prints a diff before applying. The push step prints the exact `git push` commands that will run, awaits explicit confirmation, and only then pushes.

## Steps

### Step 1 — Resolve target repo set
Parse `--repos` (comma-separated) or query each repo in the workbench for `phase: accepted`. Report the resolved set. Abort if empty.

### Step 2 — Verify preconditions per repo
For each target: check clean working tree, presence of `VERIFICATION.md`, `VERSION`, `CHANGELOG.md`. Report ✅/❌ per repo. Abort on any ❌.

### Step 3 — Compute next versions
Read each repo's `VERSION`, apply `<bump-type>`, print the resulting next version. Example:
```
ola-management-strategist  0.4.2 → 0.5.0  (minor)
OS-MDashboard              1.1.7 → 1.1.8  (patch — overridden via per-repo .osengineer/release.yml)
```

**Question (1 of recipe):** "Apply these version bumps? (Y/n)" — default Y.

### Step 4 — Bump VERSION files
For each repo, write the new `VERSION`. Print the unified diff. No global confirmation here (the bump was approved at step 3) but each write is logged.

### Step 5 — Update CHANGELOG.md per repo
For each repo, prepend a new section using `templates/CHANGELOG-entry.tmpl`:
```markdown
## [<new-version>] — <today's date>

### Added / Changed / Fixed
<contents of the most recent VERIFICATION.md's "What shipped" section>
```

Print diff per repo. Awaits no per-repo confirmation if `--yes`; otherwise per-repo y/N.

### Step 6 — Create commit + annotated tag per repo
For each repo:
```
git add VERSION CHANGELOG.md
git commit -m "chore(release): v<new-version>"
git tag -a v<new-version> -m "Release v<new-version>" -m "<summary from CHANGELOG>"
```

The commit-msg hook validates the commit format (Conventional Commits). The tag is created **locally only** — nothing pushed yet.

### Step 7 — Push (explicit confirmation, regardless of --yes)
Print exact commands that will run, one per repo:
```
git -C ola-management-strategist push origin master v0.5.0
git -C OS-MDashboard push origin master v1.1.8
```

**Question (mandatory, --yes does not override):** "Push these N tags + commits? Type 'push' to confirm: "

User must type literally `push` (not Y, not yes — explicit consent for cross-boundary action). Any other input aborts. Local commits + tags remain on disk for the user to push manually later.

### Step 8 — Post-release hooks
If `workbench-config.yml` defines `post_release_hooks:` (e.g. Jira ticket transition, Confluence page update, Slack notification), execute each in order with check-before-mutate prompts. Each hook's failure is reported but does not roll back the release (release is already pushed).

Print final report: tagged versions, push status per repo, post-release hook outcomes, suggested next phase (`idle` after a release is the natural state).

## Failure handling

- Steps 1–6 are reversible: deleted by `git reset --hard HEAD~1` per repo (the recipe prints the exact rollback commands on failure).
- Step 7 is **irreversible after the push command runs**. The recipe's mandatory confirmation is the last gate.
- Step 8 hook failures are reported but treated as informational — the release itself has already shipped.

## What this recipe deliberately does not do

- Does not run tests (verification was supposed to happen in `verify` phase)
- Does not transition phase back to `idle` automatically — that's manual to let the user inspect the post-release state first
- Does not create GitHub Releases (write the tag; the GH release workflow can pick up from there if wired in CI)
- Does not coordinate across multiple workbenches (P7 feature)
