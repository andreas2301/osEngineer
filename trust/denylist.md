# osEngineer denylist (machine-readable contract)

This file is the **single source of truth** for which Bash commands `hooks/osEngineer-pre-bash-guard.js` blocks when no active 4-part plan exists at `.osengineer/current-plan.md`. The hook reads the JSON block below at runtime — edit this file to change enforcement; no codegen step required.

The JSON block must remain parseable JSON inside a single \`\`\`json … \`\`\` fence. The hook tolerates whitespace and comments outside the fence but treats the JSON itself strictly.

## Patterns

```json
[
  {
    "name": "rm -rf",
    "regex": "\\brm\\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)",
    "category": "filesystem",
    "rationale": "Recursive force-delete trivially destroys uncommitted work or unrelated trees."
  },
  {
    "name": "git push --force",
    "regex": "\\bgit\\s+(?:\\S+\\s+)*push\\s+(?:[^|;&]*\\s)?(?:--force\\b|-f\\b|--force-with-lease\\b)",
    "category": "git",
    "rationale": "Rewrites remote history; can erase shared work irreversibly."
  },
  {
    "name": "git reset --hard",
    "regex": "\\bgit\\s+(?:\\S+\\s+)*reset\\s+--hard",
    "category": "git",
    "rationale": "Discards uncommitted local changes without recovery path."
  },
  {
    "name": "git branch -D",
    "regex": "\\bgit\\s+(?:\\S+\\s+)*branch\\s+(?:\\S+\\s+)*-D\\b",
    "category": "git",
    "rationale": "Force-deletes an unmerged local branch."
  },
  {
    "name": "git clean -fd",
    "regex": "\\bgit\\s+(?:\\S+\\s+)*clean\\s+(?:-[a-zA-Z]*[fd][a-zA-Z]*|-[fd])",
    "category": "git",
    "rationale": "Removes untracked files; can delete in-progress work that wasn't yet staged."
  },
  {
    "name": "docker rm / volume rm / system prune",
    "regex": "\\bdocker\\s+(rm\\b|volume\\s+rm\\b|system\\s+prune\\b|network\\s+rm\\b)",
    "category": "container",
    "rationale": "Removes containers, volumes, or networks; volume removal destroys persisted data."
  },
  {
    "name": "kubectl delete",
    "regex": "\\bkubectl\\s+(?:\\S+\\s+)*delete\\b",
    "category": "kubernetes",
    "rationale": "Cluster-level destructive op; without a plan, blast radius is unknowable."
  },
  {
    "name": "kubectl apply -f remote-url",
    "regex": "\\bkubectl\\s+apply\\s+(?:\\S+\\s+)*-f\\s+https?://",
    "category": "kubernetes",
    "rationale": "Applies a manifest fetched from a remote URL — supply-chain inflow."
  },
  {
    "name": "npm install (arbitrary package)",
    "regex": "\\bnpm\\s+(install|i)\\s+(?!--?save|--?dev|--?global|$)[a-zA-Z@][^\\s]*",
    "category": "package",
    "rationale": "Pulls a package from the npm registry — supply-chain inflow. osEngineer itself has zero npm dependencies and runs on Node built-ins only; an unplanned npm install indicates an unsanctioned dependency is being introduced."
  },
  {
    "name": "pip install (arbitrary package)",
    "regex": "\\bpip3?\\s+install\\s+(?!-r\\b|--?requirement\\b)[a-zA-Z][^\\s]*",
    "category": "package",
    "rationale": "Pulls a package from PyPI — supply-chain inflow. Requires explicit plan."
  },
  {
    "name": "curl | sh / wget | sh",
    "regex": "\\b(curl|wget)\\b[^|]*\\|\\s*(sh|bash|zsh)\\b",
    "category": "package",
    "rationale": "Pipes a remote payload directly into a shell — classic supply-chain attack pattern."
  },
  {
    "name": "chmod 777",
    "regex": "\\bchmod\\s+(?:-R\\s+)?777\\b",
    "category": "filesystem",
    "rationale": "Makes a file or tree world-writable; almost always a bypass for a real permissions problem."
  },
  {
    "name": "dd of=/dev/...",
    "regex": "\\bdd\\b.*\\bof=/dev/",
    "category": "filesystem",
    "rationale": "Raw block-device write — bricks the device if the path is wrong."
  },
  {
    "name": "mkfs",
    "regex": "\\bmkfs(\\.[a-z0-9]+)?\\s",
    "category": "filesystem",
    "rationale": "Formats a filesystem — irreversible data loss if the device is wrong."
  },
  {
    "name": "shutdown / reboot / halt",
    "regex": "\\b(shutdown|reboot|halt|poweroff)\\b",
    "category": "system",
    "rationale": "Takes the host down — disrupts the user's session and any running services."
  }
]
```

## Categories

- **filesystem** — destructive file or device ops
- **git** — history rewrites or shared-state mutations
- **container** — destructive container/volume/network ops
- **kubernetes** — cluster-level destructive ops
- **package** — supply-chain inflows (npm / pypi / piped shell)
- **system** — host-level lifecycle ops

## Bypassing

Two ways, both auditable:

1. **Write a 4-part plan** to `.osengineer/current-plan.md` with required sections `Touch` / `Change` / `Impact` / `Rollback`. The hook checks for all four headings (case-insensitive) and unblocks any patterned command while the file is present. Delete or rename the file when the plan is no longer active.
2. **Set `OSE_BYPASS=1`** in env for the single invocation — every bypass is logged to `.osengineer/bypass-log.jsonl` with timestamp, command, hook name, and the reason `OSE_BYPASS=1`. This trail is auditable after the fact.

The 4-part plan path is preferred for any change that lasts more than one command; the env-var bypass is for emergencies (rolling back a broken deploy, etc.).

## Per-team overrides

Teams can soften, stiffen, or disable individual patterns without forking this file. The hook composes the effective denylist at runtime from two optional override files, in order (later wins):

1. `<repo>/.osengineer/denylist-overrides.json` — repo-level overrides
2. `<repo>/.osengineer/teams/<current_team>/denylist-overrides.json` — team-level overrides (only consulted when `state.yml`'s `current_team` is set)

If neither file exists, enforcement is identical to the global denylist above. Missing or malformed override files are caught, a `parse_failure` entry is appended to `.osengineer/override-log.jsonl`, and the hook falls back to the global denylist alone — a broken override never silently disables global enforcement.

### Schema (`schema_version: 1`)

```json
{
  "schema_version": 1,
  "team_id": "coding",
  "disabled": ["docker rm / volume rm / system prune"],
  "downgraded_to_warning": ["rm -rf"],
  "added": [
    {
      "name": "go vet -tags=internal",
      "regex": "\\bgo\\s+vet\\s+-tags=internal\\b",
      "category": "tooling",
      "rationale": "Internal-tag vet runs leak experimental code paths into static analysis output."
    }
  ]
}
```

### Resolution rules

- **`disabled`** — names matching one of these are treated as not-in-the-denylist for this command. The hook emits nothing and the command runs. Match is by exact string against the global pattern's `name` field. A team-level `disabled` may also remove a `repo`-level `added` pattern of the same name.
- **`downgraded_to_warning`** — pattern still matches and the command still runs, but the hook emits an advisory `hookSpecificOutput.additionalContext` warning instead of a `block` decision. Use when a team is the legitimate owner of an otherwise risky operation (e.g. `rm -rf` in test-fixture teardown).
- **`added`** — extra patterns appended to the effective denylist. Block (or downgrade-warn if also listed in `downgraded_to_warning` of the same file) like any other pattern. Use double-escaped backslashes in regex strings, same as the global block.

Composition: repo-level loads first; team-level merges on top. `disabled` and `added` lists extend across layers; `downgraded_to_warning` likewise unions across layers.

### Audit trail

Every effective override is appended to `.osengineer/override-log.jsonl`:

- `disabled_applied` — a global pattern that would have matched was skipped by a `disabled` entry
- `downgraded_to_warning` — a matched pattern was emitted as a warning instead of a block
- `added_pattern_matched` — a team-`added` pattern matched the command
- `override_parse_failure` — an override file could not be read or parsed; global denylist used alone

### Starter file

See [`templates/denylist-overrides.json.tmpl`](../templates/denylist-overrides.json.tmpl) for a worked example covering all three override kinds.

## How to add a pattern

Append an object to the JSON array. Use double-escaped backslashes in regex strings (`\\b` for word boundary, `\\s+` for whitespace) — the block is parsed as JSON, so single `\` must be `\\` inside string literals. Set `category` to one of the existing values or add a new one (no schema enforcement). After editing, no rebuild is needed — the hook re-reads this file on every invocation.

## How to remove a pattern

Delete its object from the JSON array. Consider whether to add it to a per-team override in `.osengineer/denylist-overrides.json` instead (see the "Per-team overrides" section above) so the change is local to the repo and doesn't weaken global enforcement for everyone else.

## Provenance

This contract pattern is inspired by `google/skills`'s `gcloud/SKILL.md` (which publishes its dangerous-op denylist as readable markdown) combined with osEngineer's existing runtime-enforcement model. The original hardcoded regex array from the get-shit-done port has been migrated into this file.
