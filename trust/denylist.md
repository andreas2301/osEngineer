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

## How to add a pattern

Append an object to the JSON array. Use double-escaped backslashes in regex strings (`\\b` for word boundary, `\\s+` for whitespace) — the block is parsed as JSON, so single `\` must be `\\` inside string literals. Set `category` to one of the existing values or add a new one (no schema enforcement). After editing, no rebuild is needed — the hook re-reads this file on every invocation.

## How to remove a pattern

Delete its object from the JSON array. Consider whether to add it to a per-team override in `.osengineer/denylist-overrides.json` instead (P7 feature, not yet implemented) so the change is local to the repo and doesn't weaken global enforcement.

## Provenance

This contract pattern is inspired by `google/skills`'s `gcloud/SKILL.md` (which publishes its dangerous-op denylist as readable markdown) combined with osEngineer's existing runtime-enforcement model. The original hardcoded regex array from the get-shit-done port has been migrated into this file.
