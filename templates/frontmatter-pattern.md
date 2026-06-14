# osEngineer frontmatter convention

All `agents/*.md` and `commands/osEngineer-*.md` files SHOULD start with a YAML frontmatter block. The frontmatter is machine-parseable; the body below it is human prose. Inspired by `google/skills`'s SKILL.md convention.

## Why frontmatter

The `osEngineer-prompt-guard.js` hook can route incoming prompts to the right agent or command by matching the user's intent against the `description` field — specifically the `Use when …` and `Don't use when …` verbs. This replaces hardcoded routing tables with discoverable, file-local declarations.

Frontmatter also enables:
- `bin/osengineer scaffold-agent <role>` to generate consistent new files
- Static lint of agent / command files against this schema (P7 candidate)
- Documentation generators that produce a catalog from the corpus

## Agent frontmatter

```yaml
---
name: <agent-slug>             # required, lowercase-with-hyphens, matches filename
role: <one-word-role>          # implementer | reviewer | merge-gate | security-scanner | orchestrator | etc.
scope: <where it operates>     # team | repo | workbench | repo,workbench | etc. (comma list allowed)
description: >-                # multi-line; MUST contain "Use when" and "Don't use when"
  <one paragraph>. Use when <conditions>. Don't use when <conditions>.
escalates_to: <agent-list>     # optional; comma list of agents or "user"
---
```

## Command frontmatter

```yaml
---
name: osEngineer:<command>     # required, includes the namespace
description: >-                # MUST contain "Use when" and "Don't use when"
  <one paragraph>. Use when <conditions>. Don't use when <conditions>.
phase_allowed: [<phase>...]    # optional; phases where the command can fire
phase_after: <phase>           # optional; phase transition the command causes on success
---
```

`phase_allowed` enforcement is read by `osEngineer-prompt-guard.js` — invoking a command outside its allowed phases is blocked with a clear reason.

## "Use when" / "Don't use when" grammar

The two verbs are not optional. Each one is the discriminator for routing:

- **Use when** — concrete conditions the agent/command is designed for. Be specific: cite phase, file types, team membership, presence of artifacts.
- **Don't use when** — concrete conditions where another agent or command is the better choice. Cite the alternative by name.

Bad:
> Use when you need to fix a bug.

Good:
> Use when a PHASE_PLAN.md exists and is classified as a bugfix (single root cause, additive change). Don't use for new features (use /osEngineer:feature) or refactors (use /osEngineer:refactor); don't use without a PHASE_PLAN.md — the prompt-guard will block.

## Rollout status

| File | Frontmatter present |
|---|---|
| agents/architect.md | ✅ |
| agents/developer.md | ✅ |
| agents/judge.md | ✅ |
| agents/red-team-local.md | ✅ |
| commands/osEngineer-init.md | ✅ |
| commands/osEngineer-plan.md | ✅ |
| commands/osEngineer-fix.md | ✅ |
| commands/osEngineer-verify.md | ✅ |
| Remaining 15 agents + 7 commands | Pending — follow the patterns above |

When all files have frontmatter, the prompt-guard's matching logic activates fully and the routing table currently hardcoded in JavaScript can be deleted.
