#!/usr/bin/env bash
# install.sh — Install osEngineer wiring into a target repo or workbench.
#
# Usage:
#   ./install.sh <repo-path>            Initialise a single repo
#   ./install.sh --workbench <path>     Initialise every .git repo under <path>
#   ./install.sh --workbench            Same, defaults workbench to parent of this skill
#   ./install.sh --all                  --workbench plus /opt/sovereign-shield if present
#   ./install.sh --global               Install osEngineer git hooks as global hooks
#
# Idempotent. Re-run safely after pulling an osEngineer update.
#
# What gets installed per repo:
#   1. .osengineer/state.yml            phase=idle, current_team=null, budget_used=0
#   2. .osengineer/evolution-counter.yml
#   3. .osengineer/handoffs/.gitkeep
#   4. .osengineer/bypass-log.jsonl (touched empty)
#   5. .git/hooks/{commit-msg,pre-commit,post-commit} ← copies of osEngineer-* scripts
#   6. .claude/agents/*.md              ← copies of mandatory agent role files
#   7. .claude/settings.json            ← merged (never overwritten); 6 Claude hooks wired
#   8. AGENTS.md (root)                 ← template dropped if absent (with osEngineer frontmatter)
#   9. CLAUDE.md (root)                 ← osEngineer section appended if absent

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_DIR="$SCRIPT_DIR/hooks"
AGENTS_DIR="$SCRIPT_DIR/agents"
VERSION="$(cat "$SCRIPT_DIR/VERSION" 2>/dev/null || echo "0.0.0-dev")"

# Mandatory agents — copied into every initialised repo's .claude/agents/
# Includes the two orchestration agents (architect, verifier) introduced in
# osEngineer 0.2.0 P2 alongside the 14 implementation roles.
MANDATORY_AGENTS=(
  architect.md verifier.md
  developer.md reviewer.md judge.md
  red-team-local.md red-team-architect.md
  tech-writer.md researcher.md planner.md
  live-system-operator.md metrics-onboarding.md
  topology-validator.md cert-monitor.md
  health-verifier.md scope-manager.md
)

# ── Helpers ────────────────────────────────────────────────────────────────

log() { printf '[osEngineer] %s\n' "$*"; }
warn() { printf '[osEngineer] WARNING: %s\n' "$*" >&2; }
fail() { printf '[osEngineer] ERROR: %s\n' "$*" >&2; exit 1; }

ensure_git() {
  command -v git >/dev/null 2>&1 || fail "git not found in PATH"
}

ensure_node() {
  command -v node >/dev/null 2>&1 || fail "node not found in PATH (required for osEngineer Claude hooks)"
}

# ── Core: per-repo init ────────────────────────────────────────────────────

init_repo() {
  local repo="$1"
  local repo_name
  repo_name="$(basename "$repo")"

  [ -d "$repo" ] || { warn "$repo does not exist — skipping"; return 0; }
  [ -d "$repo/.git" ] || { warn "$repo is not a git repo — skipping"; return 0; }

  log "── initialising $repo_name ──"

  # 1. .osengineer/ subdirs and files
  mkdir -p "$repo/.osengineer/handoffs"
  if [ ! -f "$repo/.osengineer/state.yml" ]; then
    cat > "$repo/.osengineer/state.yml" <<YAML
# osEngineer state — managed by bin/osengineer; safe to inspect, editing by hand discouraged.
phase: idle
current_team: null
budget_used: 0
osengineer_version: $VERSION
YAML
    log "  + .osengineer/state.yml"
  fi
  if [ ! -f "$repo/.osengineer/evolution-counter.yml" ]; then
    cat > "$repo/.osengineer/evolution-counter.yml" <<YAML
# Incremented by osEngineer-post-commit hook. Auto-nudge fires at >= 5.
phases_since_last_evolution: 0
total_evolutions_accepted: 0
YAML
    log "  + .osengineer/evolution-counter.yml"
  fi
  touch "$repo/.osengineer/handoffs/.gitkeep"
  touch "$repo/.osengineer/bypass-log.jsonl"

  # 2. Git hooks — copy (not symlink) for portability across OSes
  local ghooks="$repo/.git/hooks"
  if [ -d "$ghooks" ]; then
    install_git_hook "$HOOKS_DIR/osEngineer-validate-commit.sh" "$ghooks/commit-msg"
    install_git_hook "$HOOKS_DIR/osEngineer-pre-commit.sh"      "$ghooks/pre-commit"
    install_git_hook "$HOOKS_DIR/osEngineer-post-commit.sh"     "$ghooks/post-commit"
    log "  + git hooks: commit-msg, pre-commit, post-commit"
  else
    warn "$repo/.git/hooks does not exist — git hooks not installed"
  fi

  # 3. Agent files
  mkdir -p "$repo/.claude/agents"
  local copied=0
  for agent in "${MANDATORY_AGENTS[@]}"; do
    if [ -f "$AGENTS_DIR/$agent" ]; then
      cp "$AGENTS_DIR/$agent" "$repo/.claude/agents/$agent"
      copied=$((copied + 1))
    fi
  done
  log "  + $copied agent files → .claude/agents/"

  # 4. .claude/settings.json — merge (never overwrite)
  install_claude_settings "$repo"

  # 5. git safe.directory (idempotent)
  git config --global --add safe.directory "$repo" 2>/dev/null || true

  # 6. AGENTS.md — auto-detect teams + populate the frontmatter
  if [ ! -f "$repo/AGENTS.md" ]; then
    # Auto-detect folder→team mapping; this ALSO writes .osengineer/teams/*.json
    # as a side effect for the pre-edit guard to consume.
    local teams_yaml
    teams_yaml=$(node "$SCRIPT_DIR/bin/osengineer" detect-teams "$repo" 2>/dev/null || echo "")

    # Determine project classification (small/medium/large) heuristically
    local classification="medium"
    local loc
    loc=$(find "$repo" -type f \( -name "*.go" -o -name "*.py" -o -name "*.ts" -o -name "*.js" -o -name "*.rs" \) -not -path "*/node_modules/*" -not -path "*/.git/*" 2>/dev/null | head -200 | wc -l)
    if [ "$loc" -lt 20 ]; then classification="small"
    elif [ "$loc" -gt 100 ]; then classification="large"
    fi

    cat > "$repo/AGENTS.md" <<MD
---
scope: repo
schema_version: 1
architect: true
osengineer_version: $VERSION
project_classification: $classification
teams:
$teams_yaml
phase_state_file: ./.osengineer/state.yml
---

# $repo_name — osEngineer repo manifest

This file is the architect/orchestrator for $repo_name. The frontmatter is
machine-parseable by osEngineer hooks (validated against
\`specs/SCHEMAS/agents-md.schema.json\`); the prose below is for humans.

## Teams

The frontmatter \`teams:\` list above was auto-detected from the repo layout
(Go modules, ansible/, *_test.go globs, docs/, .github/codeql). Edit it to
correct mistakes — \`install.sh\` re-runs are idempotent and never overwrite
this file once it exists. If you change the teams list, also re-run
\`osengineer detect-teams .\` to refresh the JSON cache at
\`.osengineer/teams/<team>.json\` that the pre-edit guard consumes.

## How osEngineer works in this repo

- **Phase state** lives in \`.osengineer/state.yml\`. Inspect with
  \`osengineer state\`. The state machine flows
  \`idle → discuss → plan → execute → verify → accepted\`.
- **Cross-team handoffs** live in \`.osengineer/handoffs/HO-<n>-*.md\`.
  Open one with \`osengineer handoff open --from <a> --to <b> --slug <s>\`.
- **Phase-aware enforcement** — during \`discuss\` and \`plan\`, edits are
  read-only outside \`planning/\` and \`.osengineer/\`.
- **owns_paths enforcement** — during \`execute\` with a \`current_team\`
  set, edits to a path outside that team's \`owns_paths\` are blocked.
- **Conventional Commits** — the \`commit-msg\` git hook enforces format.
- **Destructive bash** (\`rm -rf\`, \`git push --force\`, etc.) is blocked
  without an active 4-part plan in \`.osengineer/current-plan.md\`.
- **Override any rule** with \`OSE_BYPASS=1\` — logged to
  \`.osengineer/bypass-log.jsonl\`.

Run \`osengineer explain hooks\` for the full enforcement layer summary.
MD
    log "  + AGENTS.md (repo manifest, classification=$classification)"
  else
    # AGENTS.md already exists — refresh just the JSON cache so the
    # pre-edit guard's owns_paths globs stay current with any user edits.
    if [ -d "$repo/.osengineer" ]; then
      node "$SCRIPT_DIR/bin/osengineer" detect-teams "$repo" >/dev/null 2>&1 || true
      log "  · AGENTS.md preserved; .osengineer/teams/*.json refreshed"
    fi
  fi

  # 7. CLAUDE.md osEngineer section
  if [ ! -f "$repo/CLAUDE.md" ]; then
    cat > "$repo/CLAUDE.md" <<MD
# $repo_name

## osEngineer

This repo is initialised with osEngineer. See \`AGENTS.md\` for the team layout
and \`.osengineer/state.yml\` for current phase state. Run \`osengineer explain\`
for the concept overview.

## graphify

If \`graphify-out/\` exists, read \`graphify-out/GRAPH_REPORT.md\` for god nodes
and community structure before grepping raw files. The \`osEngineer-post-commit\`
hook auto-rebuilds graphify (AST-only) on default-branch commits.
MD
    log "  + CLAUDE.md"
  elif ! grep -q '## osEngineer' "$repo/CLAUDE.md"; then
    cat >> "$repo/CLAUDE.md" <<MD

## osEngineer

This repo is initialised with osEngineer. See \`AGENTS.md\` for team layout and
\`.osengineer/state.yml\` for current phase state. Run \`osengineer explain\`.
MD
    log "  + osEngineer section appended to CLAUDE.md"
  fi
}

install_git_hook() {
  local src="$1"
  local dst="$2"
  [ -f "$src" ] || { warn "missing hook source $src"; return 0; }

  if [ -f "$dst" ] && ! head -3 "$dst" 2>/dev/null | grep -q 'osEngineer'; then
    # Preserve existing non-osEngineer hook by chaining
    mv "$dst" "$dst.pre-osengineer"
    cat > "$dst" <<EOF
#!/usr/bin/env bash
# osEngineer hook dispatcher — runs osEngineer-* then the pre-existing hook.
"$dst.pre-osengineer" "\$@" || exit \$?
EOF
    cat "$src" >> "$dst"
  else
    cp "$src" "$dst"
  fi
  chmod +x "$dst"
}

install_claude_settings() {
  local repo="$1"
  local cfg="$repo/.claude/settings.json"
  mkdir -p "$(dirname "$cfg")"

  # Inline Node script merges osEngineer hook entries without overwriting user config.
  OSE_HOOKS_DIR="$HOOKS_DIR" OSE_VERSION="$VERSION" OSE_SETTINGS_PATH="$cfg" node <<'NODE'
const fs = require('fs');
const path = require('path');

const hooksDir = process.env.OSE_HOOKS_DIR;
const settingsPath = process.env.OSE_SETTINGS_PATH;
const version = process.env.OSE_VERSION;

function cmd(file) {
  return `node "${path.join(hooksDir, file)}"`;
}

const oseEntries = {
  UserPromptSubmit: [{
    hooks: [{ type: 'command', command: cmd('osEngineer-prompt-guard.js'), description: 'osEngineer phase state injection' }],
  }],
  PreToolUse: [
    {
      matcher: 'Write|Edit|NotebookEdit',
      hooks: [
        { type: 'command', command: cmd('osEngineer-pre-edit-guard.js'), description: 'osEngineer phase-gate & owns_paths' },
        { type: 'command', command: cmd('osEngineer-read-guard.js'), description: 'osEngineer read-before-edit advisory' },
      ],
    },
    {
      matcher: 'Bash',
      hooks: [{ type: 'command', command: cmd('osEngineer-pre-bash-guard.js'), description: 'osEngineer destructive-bash guard' }],
    },
  ],
  PostToolUse: [{
    hooks: [{ type: 'command', command: cmd('osEngineer-post-tool.js'), description: 'osEngineer context monitor + budget tracker' }],
  }],
  SessionStart: [{
    hooks: [{ type: 'command', command: `node "${path.join(hooksDir, 'osEngineer-session-start.js')}"`, description: 'osEngineer banner' }],
  }],
};

let existing = {};
if (fs.existsSync(settingsPath)) {
  try { existing = JSON.parse(fs.readFileSync(settingsPath, 'utf8')); }
  catch (e) { console.error('osEngineer: settings.json malformed, leaving as-is'); process.exit(0); }
}

existing.hooks = existing.hooks || {};

function isOseEntry(entry) {
  if (!entry || !Array.isArray(entry.hooks)) return false;
  return entry.hooks.some(h => typeof h?.command === 'string' && h.command.includes('osEngineer-'));
}

for (const [event, oseList] of Object.entries(oseEntries)) {
  const existingList = (existing.hooks[event] || []).filter(e => !isOseEntry(e));
  existing.hooks[event] = [...existingList, ...oseList];
}

existing.statusLine = existing.statusLine || {
  type: 'command',
  command: `node "${path.join(hooksDir, 'osEngineer-statusline.js')}"`,
  padding: 0,
};
if (existing.statusLine?.command?.includes('osEngineer-statusline')) {
  // Already osEngineer's; refresh path in case of skill move
  existing.statusLine.command = `node "${path.join(hooksDir, 'osEngineer-statusline.js')}"`;
}

existing.env = existing.env || {};
existing.env.OSENGINEER_HOME = path.resolve(hooksDir, '..');
existing.env.OSENGINEER_VERSION = version;

fs.writeFileSync(settingsPath, JSON.stringify(existing, null, 2) + '\n');
console.log('  + .claude/settings.json merged');
NODE
}

# ── Workbench mode ─────────────────────────────────────────────────────────

init_workbench() {
  local root="${1:-$(dirname "$SCRIPT_DIR")}"
  [ -d "$root" ] || fail "workbench root $root does not exist"

  log "workbench root: $root"

  # META detection
  local meta_repo=""
  for candidate in "$root"/*; do
    [ -d "$candidate/.git" ] || continue
    local readme="$candidate/README.md"
    if [ -f "$readme" ] && grep -qiE 'source of truth' "$readme" 2>/dev/null; then
      meta_repo="$candidate"
      log "META repo detected: $(basename "$candidate")"
      break
    fi
    if [ -d "$candidate/plans" ] && [ -d "$candidate/teams" ]; then
      meta_repo="$candidate"
      log "META repo detected (by /plans+/teams): $(basename "$candidate")"
      break
    fi
  done

  # Workbench-level AGENTS.md
  if [ ! -f "$root/AGENTS.md" ]; then
    local meta_block=""
    [ -n "$meta_repo" ] && meta_block="meta_ref:
  path: ./$(basename "$meta_repo")
  role: codified-source-of-truth"
    cat > "$root/AGENTS.md" <<YAML
---
scope: workbench
schema_version: 1
osengineer_version: $VERSION
$meta_block
cross_repo_handoffs_dir: ./.osengineer/handoffs/
---

# Workbench — $(basename "$root")

osEngineer-initialised workbench. See \`.osengineer/\` for cross-repo state and
\`./<repo>/AGENTS.md\` for each repo's team manifest.
YAML
    log "+ workbench AGENTS.md"
  fi
  mkdir -p "$root/.osengineer/handoffs"
  touch "$root/.osengineer/handoffs/.gitkeep"

  # Iterate repos
  for repo in "$root"/*; do
    [ -d "$repo/.git" ] || continue
    init_repo "$repo"
  done

  log "workbench init complete"
}

# ── Global mode ────────────────────────────────────────────────────────────

init_global_hooks() {
  log "installing global git hooks"

  local gdir
  gdir="$(git config --global core.hooksPath 2>/dev/null || true)"
  if [ -z "$gdir" ]; then
    gdir="$HOME/.git-hooks"
    git config --global core.hooksPath "$gdir"
    log "set global hooks path: $gdir"
  fi
  mkdir -p "$gdir"

  cp "$HOOKS_DIR/osEngineer-validate-commit.sh" "$gdir/commit-msg"
  cp "$HOOKS_DIR/osEngineer-pre-commit.sh"      "$gdir/pre-commit"
  cp "$HOOKS_DIR/osEngineer-post-commit.sh"     "$gdir/post-commit"
  chmod +x "$gdir/commit-msg" "$gdir/pre-commit" "$gdir/post-commit"

  log "global hooks installed to $gdir"
}

# ── Dispatch ───────────────────────────────────────────────────────────────

ensure_git
ensure_node

if [ $# -eq 0 ]; then
  cat <<USAGE
osEngineer installer — version $VERSION

Usage:
  $0 <repo-path>                Initialise a single repo
  $0 --workbench [<path>]       Initialise every .git repo under <path>
  $0 --all                      --workbench plus /opt/sovereign-shield if present
  $0 --global                   Install osEngineer git hooks as global hooks

USAGE
  exit 1
fi

case "$1" in
  --workbench)
    init_workbench "${2:-}"
    ;;
  --global)
    init_global_hooks
    ;;
  --all)
    init_workbench
    init_global_hooks
    if [ -d "/opt/sovereign-shield" ]; then
      init_repo "/opt/sovereign-shield"
    fi
    ;;
  -h|--help)
    cat <<USAGE
osEngineer installer — version $VERSION
Usage: $0 <repo-path> | --workbench [<path>] | --all | --global
USAGE
    ;;
  *)
    init_repo "$1"
    ;;
esac

log "osEngineer install complete (version $VERSION)"
