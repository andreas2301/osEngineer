# /osEngineer:evolve

**Syntax:** `/osEngineer:evolve [status | propose | accept | reject]`
**Role:** Meta-agent — improves the skill itself via HITL self-improvement.
**Trigger:** Explicit user call, or auto-nudge when `phases_since_last_evolution ≥ 5`.
**Output:** Updated `memory/patterns/<slug>.md` (on accept) or
`.osengineer/evolution-rejections.jsonl` entry (on reject); counter reset to 0.

---

## Description

The evolve loop is osEngineer's self-improvement mechanism. The post-commit
hook ticks `.osengineer/evolution-counter.yml`. At counter ≥ 5 the session-start
banner nudges. The user (with optional architect-agent help) authors
improvement proposals, then accepts or rejects each. Accepted proposals are
promoted to patterns in the osEngineer skill repo's `memory/patterns/`,
making the learning durable across future installs and rollouts.

**This is a HITL gate. The CLI NEVER auto-applies evolution changes.** Proposals
require an explicit `accept` or `reject` subcommand.

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

**Accept** — promotes a pattern file into the osEngineer skill repo:

```
$ osengineer evolve accept EP-001 --pattern-slug queue-declare-before-bind  \
    --pattern-file /tmp/pattern.md
accepted EP-001 → memory/patterns/queue-declare-before-bind.md
counter reset to 0; total accepted = 4
```

If `--pattern-file` is omitted, a stub is created from the proposal body.

**Reject** — logs reason; counter still resets (rejection counts as "addressed"):

```
$ osengineer evolve reject EP-002 --reason "duplicate of existing dual-listen-migration pattern"
rejected EP-002 (reason logged); counter reset to 0
```

### 5. Pattern is now visible to all future osEngineer installs

Pattern lives in `<osEngineer-skill-repo>/memory/patterns/queue-declare-before-bind.md`
and ships with the next `install.sh` run on any repo.

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
| Accepted patterns | `<osEngineer-skill>/memory/patterns/<slug>.md` | shared learning |
| Rejection log | `<repo>/.osengineer/evolution-rejections.jsonl` | append-only rejection audit |

The skill-repo location lets one workbench worth of work feed improvements
back into the skill that gets reinstalled in the next workbench. The
per-repo locations let many parallel proposals coexist without conflict.

---

## Hard rules

- **CLI never modifies osEngineer's own files** outside `memory/patterns/`.
  Code/template/agent edits are out of scope — they require a real phase
  in the osEngineer repo itself with TDD + reviewer.
- **Reject still resets the counter.** Rejecting a proposal is also a
  decision the user "addressed" — it's not punished.
- **No anonymous proposals.** Every proposal records `opened_in_repo` so
  the trail back to context is preserved.
- **No silent overwrites.** If `memory/patterns/<slug>.md` already exists,
  `--pattern-slug` collisions are caller error; user must pick a unique slug
  or update the existing pattern manually.

---

## Related commands

- `/osEngineer:explain evolution` — concept overview
- `/osEngineer:verify` — produces VERIFICATION.md which informs future proposals
- `osengineer state` — see current phase and budget; useful pre-evolve context
