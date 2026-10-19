---
name: osEngineer:evolve
description: >-
  Meta-command for skill self-improvement — surfaces, accepts, or
  rejects improvement proposals authored after at least 5 phases have
  landed. On accept, writes a reviewable change proposal into the
  target repo (`.osengineer/evolve/proposals/<id>.md`); a human then
  runs `promote` to open a skill-home branch/PR. On reject, appends to
  `.osengineer/evolution-rejections.jsonl`. Use when the
  session-start banner nudges or when you have a pattern worth
  durable across installs. Don't use as an auto-apply path — evolve
  is HITL only; don't use to revise PHASE_PLAN.md (use /osEngineer:fix
  to amend) and don't use mid-phase (transition to idle first).
phase_allowed: [idle]
---

# /osEngineer:evolve

**Syntax:** `/osEngineer:evolve [status | propose | accept | promote | reject]`
**Role:** Meta-agent — improves the skill itself via HITL self-improvement.
**Trigger:** Explicit user call, or auto-nudge when `phases_since_last_evolution ≥ 5`.
**Output:** `.osengineer/evolve/proposals/<id>.md` in the target repo (on accept),
a branch + optional PR in the skill home (on a human-run promote), or an
`.osengineer/evolution-rejections.jsonl` entry (on reject); counter reset to 0.

---

## Description

The evolve loop is osEngineer's self-improvement mechanism. The post-commit
hook ticks `.osengineer/evolution-counter.yml`. At counter ≥ 5 the session-start
banner nudges. The user (with optional architect-agent help) authors
improvement proposals, then accepts or rejects each. An accepted proposal
becomes a change proposal in the target repo. A human then promotes it into
the osEngineer skill repo's `memory/patterns/` as a branch and pull request,
so the learning is reviewed before it reaches future installs.

**The loop proposes, the owner decides.** The proposer is never the approver:
`accept` never touches the shared skill home, `promote` refuses in headless
runs (`OSE_HEADLESS=1`), and nothing is ever merged automatically.

---

## The flow

### 1. Auto-nudge fires (passive)

After 5 phases land via Conventional Commits, the post-commit hook ticks the
counter to 5. The next session-start hook surfaces a banner:

```
osEngineer state
- phase: idle
- ⚙ 5 phases since last /osEngineer:evolve — consider running it to surface improvement proposals.
```

### 2. User runs status

```
$ osengineer evolve
phases_since_last_evolution: 5
total_evolutions_accepted: 3
⚙ counter ≥ 5 — consider proposing improvements
open proposals: 0
closed proposals: 0
```

### 3. User (with architect help) proposes improvements

The architect agent inspects:
- the last few `planning/active/*/RETROSPECTIVE.md` files
- the recent entries in `.osengineer/bypass-log.jsonl` (where rules were bypassed)
- the recent entries in `.osengineer/handoffs/` (which teams deadlocked)
- `memory/patterns/` (what's already documented)

and surfaces 1–3 improvement candidates. The user opens proposals via:

```
$ osengineer evolve propose --title "Add queue-declare-before-bind to RabbitMQ pattern"  \
    --category amqp \
    --body-file /tmp/proposal-body.md
opened EP-001 → .osengineer/evolution-proposals/EP-001-add-queue-declare-before-bind.md
```

### 4. User accepts or rejects each proposal

**Accept** — writes a change proposal into the target repo. The skill home is
not touched:

```
$ osengineer evolve accept EP-001 --pattern-slug queue-declare-before-bind  \
    --pattern-file /tmp/pattern.md \
    --why "Two retros hit the same bind-before-declare race" \
    --risk "Low: one new docs-only pattern file" \
    --evidence "planning/active/03-amqp/RETROSPECTIVE.md"
accepted EP-001 → .osengineer/evolve/proposals/EP-001.md (proposal only; skill home untouched)
review it, then run: osengineer evolve promote EP-001 [--pr]
counter reset to 0; total accepted = 4
```

The proposal has plain-language sections: **What changes**, **Why**, **Risk**,
**How to revert**, **Evidence** (the source proposal, run or retro) and the
**Pattern** itself. If `--pattern-file` is omitted, the pattern is a stub
built from the proposal body. `--why` defaults to the title and `--evidence`
to the source proposal. `--risk` has no default: fill it in, by flag or by
editing the file, before promoting. `--pattern-slug` must be lowercase
letters, digits and dashes.

**Reject** — logs reason; counter still resets (rejection counts as "addressed"):

```
$ osengineer evolve reject EP-002 --reason "duplicate of existing dual-listen-migration pattern"
rejected EP-002 (reason logged); counter reset to 0
```

### 5. A human promotes the proposal as a PR

```
$ osengineer evolve promote EP-001 --pr
promoted EP-001 → branch evolve/ep-001-queue-declare-before-bind in <skill-home> (commit 1a2b3c4d5e6f); nothing merged
opened PR for review: https://github.com/<owner>/osEngineer/pull/42
```

`promote` commits `memory/patterns/<slug>.md` on a new branch of the skill
home git checkout. The commit subject is `docs(patterns): add <slug>` and the
change summary is the commit body. It uses a scratch index, so the skill
home's working tree and checked-out branch stay as they were. With `--pr`
and `gh` on PATH, it pushes the branch and opens a PR. Without `--pr`, it
prints the push and PR commands. It refuses when:

- the run is headless (`OSE_HEADLESS=1`);
- the skill home (`$OSENGINEER_HOME`, else the CLI's own checkout) is not a
  git checkout, or has uncommitted changes;
- the proposal is missing a field (an empty section, or no pattern);
- the pattern file or the branch already exists.

### 6. Pattern ships after the PR is merged

Once the owner reviews and merges the PR, the pattern lives in
`<osEngineer-skill-repo>/memory/patterns/queue-declare-before-bind.md`
and ships with the next `install.sh` run on any repo. To undo it, close
the PR unmerged, or `git revert` the promote commit.

---

## Auto-nudge tuning

To change the nudge threshold or disable auto-nudge:

- Edit `memory/environment-profile.yml` in your osEngineer skill repo:
  ```yaml
  auto_evolve: true
  evolve_nudge_threshold: 5
  ```
- Or set `OSE_NO_NUDGE=1` env var in your `.claude/settings.json` env block
  to suppress the banner specifically (does not affect counter increment).

---

## What gets stored where

| Artifact | Location | Purpose |
|---|---|---|
| Counter | `<repo>/.osengineer/evolution-counter.yml` | per-repo nudge timing |
| Proposals (open) | `<repo>/.osengineer/evolution-proposals/EP-NNN-*.md` | proposal documents pending decision |
| Proposals (closed) | same path, status field flipped | audit trail |
| Change proposals (accepted) | `<repo>/.osengineer/evolve/proposals/<id>.md` | reviewable change summary + pattern awaiting promote |
| Promoted patterns | branch `evolve/<id>-<slug>` in `<osEngineer-skill>`, then `memory/patterns/<slug>.md` after PR merge | shared learning |
| Rejection log | `<repo>/.osengineer/evolution-rejections.jsonl` | append-only rejection audit |

The skill-repo location lets one workbench worth of work feed improvements
back into the skill that gets reinstalled in the next workbench. The
per-repo locations let many parallel proposals coexist without conflict.

---

## Hard rules

- **The loop proposes, the owner decides.** `accept` never writes to the
  skill home. `promote` is human-only (refused headless), only creates a
  branch (and a PR with `--pr`), and never merges.
- **CLI never modifies osEngineer's own files** outside `memory/patterns/`.
  Code/template/agent edits are out of scope — they require a real phase
  in the osEngineer repo itself with TDD + reviewer.
- **Reject still resets the counter.** Rejecting a proposal is also a
  decision the user "addressed" — it's not punished.
- **No anonymous proposals.** Every proposal records `opened_in_repo` so
  the trail back to context is preserved.
- **No silent overwrites.** If `memory/patterns/<slug>.md` already exists,
  `promote` refuses; pick a unique slug or update the existing pattern
  manually.

---

## Related commands

- `/osEngineer:explain evolution` — concept overview
- `/osEngineer:verify` — produces VERIFICATION.md which informs future proposals
- `osengineer state` — see current phase and budget; useful pre-evolve context
