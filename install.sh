#!/usr/bin/env bash
# install.sh — Install osEngineer wiring into a target repo or workbench.
#
# Usage:
#   ./install.sh <repo-path>            Initialise a single repo
#   ./install.sh --workbench <path>     Initialise every .git repo under <path>
#   ./install.sh --workbench            Same, defaults workbench to parent of this skill
#   ./install.sh --all                  --workbench plus any extra repos specified interactively
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
  sandbox-provisioner.md
)

# Global variables for interactive setup
RUNTIMES="claude"
ATLASSIAN_CLOUD_ID=""
ATLASSIAN_SITE_URL=""
ATLASSIAN_KEYS=""
VAULT_ADDR=""
VAULT_TOKEN=""
LIVE_SYSTEM_PATH=""
IS_MULTI_HARNESS="n"
ORCHESTRATOR_MODEL=""
WORKER_MODEL=""
VALIDATOR_MODEL=""
VALIDATION_PROFILE=""

collect_interactive_inputs() {
  # If not in an interactive terminal or inside a non-interactive/CI run, skip prompting
  if [ ! -t 0 ] || [ -n "${CI:-}" ] || [ "${OSE_NONINTERACTIVE:-}" = "1" ]; then
    RUNTIMES="claude"
    ATLASSIAN_CLOUD_ID="${ATLASSIAN_CLOUD_ID:-}"
    ATLASSIAN_SITE_URL="${ATLASSIAN_SITE_URL:-https://your-site.atlassian.net}"
    ATLASSIAN_KEYS="${ATLASSIAN_KEYS:-PROJ}"
    VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
    VAULT_TOKEN="${VAULT_TOKEN:-}"
    LIVE_SYSTEM_PATH="${LIVE_SYSTEM_PATH:-}"
    IS_MULTI_HARNESS="${IS_MULTI_HARNESS:-n}"
    ORCHESTRATOR_MODEL="${ORCHESTRATOR_MODEL:-gemini-3.5-pro}"
    WORKER_MODEL="${WORKER_MODEL:-gemini-3.5-flash}"
    VALIDATOR_MODEL="${VALIDATOR_MODEL:-gemini-3.5-flash}"
    VALIDATION_PROFILE="${VALIDATION_PROFILE:-backend}"
    return 0
  fi

  echo "=========================================================="
  echo "        osEngineer Skill Setup & Initialization"
  echo "=========================================================="
  echo ""
  
  printf "Is this a multi-harness setup? (e.g. using multiple runtimes like Claude Code, Kimi, Codex) [y/N]: "
  read -r IS_MULTI_HARNESS
  IS_MULTI_HARNESS="${IS_MULTI_HARNESS:-n}"
  
  if [[ "$IS_MULTI_HARNESS" =~ ^[Yy]$ ]]; then
    echo "For which AI assistant runtimes do you want to configure osEngineer hooks and MCPs?"
    echo "Choose by entering the numbers separated by spaces (e.g., 1 2 3):"
    echo "  [1] Claude Code (wires .claude/settings.json)"
    echo "  [2] Kimi CLI (wires .kimi/settings.json)"
    echo "  [3] Codex CLI (wires .codex/settings.json)"
    printf "Selections [default: 1]: "
    
    local selections
    read -r selections
    selections="${selections:-1}"
    
    RUNTIMES=""
    for choice in $selections; do
      case "$choice" in
        1) RUNTIMES="$RUNTIMES claude" ;;
        2) RUNTIMES="$RUNTIMES kimi" ;;
        3) RUNTIMES="$RUNTIMES codex" ;;
      esac
    done
    RUNTIMES="${RUNTIMES#"${RUNTIMES%%[! ]*}"}" # trim leading whitespace
    RUNTIMES="${RUNTIMES:-claude}"
  else
    RUNTIMES="claude"
  fi

  echo ""
  echo "── Droid Whispering (Model Allocation Routing) ──"
  echo "Configure which models to allocate to each core osEngineer role."
  echo ""
  printf "Enter Orchestrator model [default: gemini-3.5-pro]: "
  read -r ORCHESTRATOR_MODEL
  ORCHESTRATOR_MODEL="${ORCHESTRATOR_MODEL:-gemini-3.5-pro}"

  printf "Enter Worker model [default: gemini-3.5-flash]: "
  read -r WORKER_MODEL
  WORKER_MODEL="${WORKER_MODEL:-gemini-3.5-flash}"

  printf "Enter Validator model (unbiased instruction follower) [default: gemini-3.5-flash]: "
  read -r VALIDATOR_MODEL
  VALIDATOR_MODEL="${VALIDATOR_MODEL:-gemini-3.5-flash}"

  # Test connections
  echo ""
  echo "── Connection testing ──"
  for runtime in $RUNTIMES; do
    log "Testing connection to runtime: $runtime..."
    if command -v "$runtime" >/dev/null 2>&1; then
      log "  + $runtime CLI detected in PATH."
    elif [ "$runtime" = "claude" ] && command -v npx >/dev/null 2>&1; then
      log "  + claude command not directly found, but npx is available to trigger @anthropic-ai/claude-code."
    else
      warn "  - $runtime CLI not found in PATH. You may need to install it later."
    fi
  done

  echo ""
  echo "── Validation Discovery Session ──"
  echo "Choose the primary validation workload profile for this project:"
  echo "  [1] Infrastructure / Configuration (Ansible on Linux, Docker compose, local shell checks)"
  echo "  [2] Frontend / Web Application (HTML, React, Playwright E2E browser tests)"
  echo "  [3] Backend / API Microservices (Go modules, AMQP routing, REST API schemas)"
  echo "  [4] Hybrid / Full Stack"
  printf "Selection [default: 3]: "
  read -r VALIDATION_PROFILE
  VALIDATION_PROFILE="${VALIDATION_PROFILE:-3}"
  case "$VALIDATION_PROFILE" in
    1) VALIDATION_PROFILE="infra" ;;
    2) VALIDATION_PROFILE="frontend" ;;
    3) VALIDATION_PROFILE="backend" ;;
    4) VALIDATION_PROFILE="hybrid" ;;
    *) VALIDATION_PROFILE="backend" ;;
  esac
  log "Validation profile set to: $VALIDATION_PROFILE"
  echo ""

  echo "── MCP Configuration Credentials ──"
  echo "Sensitive credentials will be written locally to gitignored config files"
  echo "and NOT committed to public version control."
  echo ""
  
  printf "Enter Atlassian Cloud ID (leave blank to configure later): "
  read -r ATLASSIAN_CLOUD_ID
  
  if [ -n "$ATLASSIAN_CLOUD_ID" ]; then
    printf "Enter Atlassian Site URL [default: https://your-site.atlassian.net]: "
    read -r ATLASSIAN_SITE_URL
    ATLASSIAN_SITE_URL="${ATLASSIAN_SITE_URL:-https://your-site.atlassian.net}"

    printf "Enter Atlassian Project/Space Keys [default: PROJ]: "
    read -r ATLASSIAN_KEYS
    ATLASSIAN_KEYS="${ATLASSIAN_KEYS:-PROJ}"
  fi

  printf "Enter HashiCorp Vault Address [default: http://127.0.0.1:8200]: "
  read -r VAULT_ADDR
  VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
  
  printf "Enter HashiCorp Vault Token (leave blank to configure later): "
  read -r -s VAULT_TOKEN
  echo "" # print newline after hidden token input

  printf "Enter Live System path (if any, e.g. /opt/live-system) [default: none]: "
  read -r LIVE_SYSTEM_PATH
  LIVE_SYSTEM_PATH="${LIVE_SYSTEM_PATH:-}"
}

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

# ── Interactive prompts ────────────────────────────────────────────────────

# Ask a question with a default. Returns the answer (or default if empty).
prompt() {
  local question="$1"
  local default="$2"
  if [ -n "$default" ]; then
    read -r -p "$question [$default] " answer
  else
    read -r -p "$question " answer
  fi
  printf '%s' "${answer:-$default}"
}

# Yes/no prompt. Returns "y" or "n".
prompt_yn() {
  local question="$1"
  local default="${2:-n}"
  read -r -p "$question [y/N] " answer
  answer="${answer:-$default}"
  case "$answer" in
    [Yy]*) printf 'y' ;;
    *) printf 'n' ;;
  esac
}

# Prompt user to pick from a list. Returns the selected index (0-based) or empty.
prompt_choice() {
  local question="$1"
  shift
  printf '%s\n' "$question"
  local i=0
  for opt in "$@"; do
    printf '  %d) %s\n' "$((i+1))" "$opt"
    i=$((i + 1))
  done
  read -r -p "Choice [1-$i]: " choice
  if [ -z "$choice" ] || [ "$choice" -lt 1 ] || [ "$choice" -gt "$i" ] 2>/dev/null; then
    printf ''
  else
    printf '%s' "$((choice - 1))"
  fi
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

  # 3. Agent files for each chosen runtime
  for runtime in $RUNTIMES; do
    mkdir -p "$repo/.$runtime/agents"
    local copied=0
    # P6.2: source layout is agents/<role>/AGENT.md (dir-style). Fall back to
    # flat agents/<role>.md for any agent that wasn't split. Destination is
    # always flat — Claude Code recognises only .claude/agents/<role>.md files.
    for agent in "${MANDATORY_AGENTS[@]}"; do
      local agent_name="${agent%.md}"
      local src_dir="$AGENTS_DIR/$agent_name/AGENT.md"
      local src_flat="$AGENTS_DIR/$agent"
      local src_file=""
      if [ -f "$src_dir" ]; then
        src_file="$src_dir"
      elif [ -f "$src_flat" ]; then
        src_file="$src_flat"
      fi

      if [ -n "$src_file" ]; then
        local dst_file="$repo/.$runtime/agents/$agent"
        if [ -f "$dst_file" ]; then
          if cmp -s "$src_file" "$dst_file"; then
            # Identical contents, skip quietly
            copied=$((copied + 1))
            continue
          fi
          
          # Check if osEngineer additions/rules are already present to prevent infinite duplication
          if grep -q "## osEngineer" "$dst_file" 2>/dev/null; then
            log "  · osEngineer additions already present in $agent (skipped)"
            copied=$((copied + 1))
            continue
          fi

          # Contents differ! Check if interactive
          if [ -t 0 ] && [ -z "${CI:-}" ] && [ "${OSE_NONINTERACTIVE:-}" != "1" ]; then
            echo ""
            log "Agent file .$runtime/agents/$agent already exists and has custom changes."
            echo "What would you like to do?"
            echo "  [o] Overwrite with the standard osEngineer version"
            echo "  [a] Append osEngineer instructions to the end of the existing file"
            echo "  [k] Keep/skip the existing file and make no changes"
            read -r -p "Choice [o/a/K]: " choice
            choice="${choice:-k}"
            case "$choice" in
              [Oo]*)
                cp "$src_file" "$dst_file"
                log "  · Overwrote $agent"
                ;;
              [Aa]*)
                printf "\n\n## osEngineer Additions\n\n" >> "$dst_file"
                cat "$src_file" >> "$dst_file"
                log "  · Appended osEngineer instructions to $agent"
                ;;
              *)
                log "  · Preserved custom $agent (skipped)"
                ;;
            esac
          else
            # Non-interactive mode: act as an addition (append) by default
            printf "\n\n## osEngineer Additions\n\n" >> "$dst_file"
            cat "$src_file" >> "$dst_file"
            log "  + Appended osEngineer instructions to existing $agent (non-interactive)"
          fi
        else
          # New file
          cp "$src_file" "$dst_file"
        fi
        copied=$((copied + 1))
      fi
    done
    log "  + $copied agent files → .$runtime/agents/"
  done

  # 4. Settings — merge (never overwrite)
  install_assistant_settings "$repo"

  # Write secrets.env if any credentials provided
  if [ -n "$ATLASSIAN_CLOUD_ID" ] || [ -n "$VAULT_TOKEN" ]; then
    local env_file="$repo/.osengineer/secrets.env"
    cat > "$env_file" <<EOF
# osEngineer local environment secrets — gitignored
export ATLASSIAN_CLOUD_ID="$ATLASSIAN_CLOUD_ID"
export VAULT_ADDR="$VAULT_ADDR"
export VAULT_TOKEN="$VAULT_TOKEN"
EOF
    chmod 600 "$env_file"
    log "  + .osengineer/secrets.env created (restricted read permissions)"
  fi

  # Gitignore .osengineer/ secrets
  local gitignore="$repo/.gitignore"
  if [ -f "$gitignore" ]; then
    if ! grep -q '\.osengineer/secrets\.env' "$gitignore"; then
      echo "" >> "$gitignore"
      echo "# osEngineer sensitive local secrets" >> "$gitignore"
      echo ".osengineer/secrets.env" >> "$gitignore"
      log "  + added .osengineer/secrets.env to .gitignore"
    fi
  fi

  # 5. git safe.directory (idempotent)
  git config --global --add safe.directory "$repo" 2>/dev/null || true

  # Configure local git non-interactive safeguards
  if [ -d "$repo/.git" ]; then
    (
      cd "$repo"
      git config --local core.editor true 2>/dev/null || true
      git config --local core.askpass true 2>/dev/null || true
      git config --local core.terminalPrompt false 2>/dev/null || true
    )
    log "  + configured non-interactive local git core controls"
  fi

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

Key operational facts:
- **Conventional Commits** are enforced by the \`commit-msg\` git hook.
- **TDD** is enforced for production code: red → green → refactor, atomic commits.
- **Destructive bash** is blocked without an active 4-part plan.
- **Override any rule** with \`OSE_BYPASS=1\` — every bypass logged.

## Baseline & Extended Agent Rules

### Baseline Rules
1. **Think Before Coding**: State assumptions explicitly. If an instruction is ambiguous, name what is confusing and ask instead of guessing.
2. **Simplicity First**: Write the minimum code that solves the problem. No speculative abstractions or flexibility that wasn't explicitly requested.
3. **Surgical Changes**: Touch only what the task requires. Do not "improve" adjacent code, reformat, or refactor things that aren't broken.
4. **Goal-Driven Execution**: Turn vague instructions into verifiable targets. Create tests first to reproduce the issue, then loop until it passes.

### Extended Agent Rules
5. **Set Hard Token Budgets**: Stop runaway iterations by placing strict context limits.
6. **Expose Conflicts**: Don't blindly average contradictory patterns in the codebase.
7. **Read Before Writing**: Scan existing code before making edits to prevent duplication.
8. **Test Real Logic**: Ensure tests validate actual logic rather than just running to pass.
9. **Use Checkpoints**: Utilize checkpoints for long-running, multi-step tasks.
10. **Fail Explicitly**: Avoid silent failures that just appear successful.

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

Key operational facts:
- **Conventional Commits** are enforced by the \`commit-msg\` git hook.
- **TDD** is enforced for production code: red → green → refactor, atomic commits.
- **Destructive bash** is blocked without an active 4-part plan.
- **Override any rule** with \`OSE_BYPASS=1\` — every bypass logged.

## Baseline & Extended Agent Rules

### Baseline Rules
1. **Think Before Coding**: State assumptions explicitly. If an instruction is ambiguous, name what is confusing and ask instead of guessing.
2. **Simplicity First**: Write the minimum code that solves the problem. No speculative abstractions or flexibility that wasn't explicitly requested.
3. **Surgical Changes**: Touch only what the task requires. Do not "improve" adjacent code, reformat, or refactor things that aren't broken.
4. **Goal-Driven Execution**: Turn vague instructions into verifiable targets. Create tests first to reproduce the issue, then loop until it passes.

### Extended Agent Rules
5. **Set Hard Token Budgets**: Stop runaway iterations by placing strict context limits.
6. **Expose Conflicts**: Don't blindly average contradictory patterns in the codebase.
7. **Read Before Writing**: Scan existing code before making edits to prevent duplication.
8. **Test Real Logic**: Ensure tests validate actual logic rather than just running to pass.
9. **Use Checkpoints**: Utilize checkpoints for long-running, multi-step tasks.
10. **Fail Explicitly**: Avoid silent failures that just appear successful.
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
# osEngineer hook dispatcher — runs pre-existing hook then osEngineer-*.
"$dst.pre-osengineer" "\$@" || exit \$?
# --- osEngineer hook follows ---
EOF
    # Strip shebang from osEngineer source to avoid duplicate interpreter lines
    tail -n +2 "$src" >> "$dst"
  else
    cp "$src" "$dst"
  fi
  chmod +x "$dst"
}

install_assistant_settings() {
  local repo="$1"

  for runtime in $RUNTIMES; do
    local cfg="$repo/.$runtime/settings.json"
    mkdir -p "$(dirname "$cfg")"

    # Inline Node script merges osEngineer hook entries without overwriting user config.
    OSE_HOOKS_DIR="$HOOKS_DIR" \
    OSE_VERSION="$VERSION" \
    OSE_SETTINGS_PATH="$cfg" \
    OSE_RUNTIME="$runtime" \
    OSE_REPO_PATH="$repo" \
    OSE_ATLASSIAN_CLOUD_ID="$ATLASSIAN_CLOUD_ID" \
    OSE_ATLASSIAN_SITE_URL="$ATLASSIAN_SITE_URL" \
    OSE_ATLASSIAN_KEYS="$ATLASSIAN_KEYS" \
    OSE_VAULT_ADDR="$VAULT_ADDR" \
    OSE_VAULT_TOKEN="$VAULT_TOKEN" \
    node <<'NODE'
const fs = require('fs');
const path = require('path');

const hooksDir = process.env.OSE_HOOKS_DIR;
const settingsPath = process.env.OSE_SETTINGS_PATH;
const version = process.env.OSE_VERSION;
const runtime = process.env.OSE_RUNTIME;
const repo = process.env.OSE_REPO_PATH;

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
  catch (e) { console.error(`osEngineer: ${runtime} settings.json malformed, leaving as-is`); process.exit(0); }
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

// ── MCP Auto-Wiring ──
const defaultMcpServers = {
  "context7": {
    "command": "npx",
    "args": ["-y", "@upstash/context7-mcp@latest"]
  },
  "playwright": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-playwright"]
  }
};

const openSpacePath = path.resolve(repo, '../OpenSpace');
if (fs.existsSync(openSpacePath)) {
  defaultMcpServers["openspace"] = {
    "command": "python",
    "args": ["-m", "openspace.mcp_server"],
    "env": {
      "PYTHONPATH": openSpacePath
    }
  };
}

if (process.env.OSE_ATLASSIAN_CLOUD_ID) {
  const siteUrl = process.env.OSE_ATLASSIAN_SITE_URL || "https://your-site.atlassian.net";
  const keys = process.env.OSE_ATLASSIAN_KEYS || "PROJ";
  defaultMcpServers["atlassian"] = {
    "command": "npx",
    "args": ["-y", "@atlassian/mcp-server-atlassian"],
    "env": {
      "ATLASSIAN_CLOUD_ID": process.env.OSE_ATLASSIAN_CLOUD_ID,
      "ATLASSIAN_SITE_URL": siteUrl,
      "ATLASSIAN_PROJECT_KEYS": keys,
      "ATLASSIAN_SPACE_KEYS": keys
    }
  };
}

if (process.env.OSE_VAULT_ADDR && process.env.OSE_VAULT_TOKEN) {
  defaultMcpServers["hashicorp-vault"] = {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-vault"],
    "env": {
      "VAULT_ADDR": process.env.OSE_VAULT_ADDR,
      "VAULT_TOKEN": process.env.OSE_VAULT_TOKEN
    }
  };
}

existing.mcpServers = existing.mcpServers || {};
for (const [serverName, config] of Object.entries(defaultMcpServers)) {
  if (!existing.mcpServers[serverName]) {
    existing.mcpServers[serverName] = config;
  }
}

fs.writeFileSync(settingsPath, JSON.stringify(existing, null, 2) + '\n');
console.log(`  + .${runtime}/settings.json merged`);
NODE
  done
}

# ── Repo classification helpers ────────────────────────────────────────────

detect_dominant_lang() {
  local repo="$1"
  local counts=""
  counts=$(find "$repo" -type f -not -path '*/node_modules/*' -not -path '*/vendor/*' -not -path '*/.git/*' \
    | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -5 2>/dev/null || true)
  case "$counts" in
    *go*)     printf 'go' ;;
    *py*)     printf 'python' ;;
    *rs*)     printf 'rust' ;;
    *ts*)     printf 'typescript' ;;
    *js*)     printf 'javascript' ;;
    *java*)   printf 'java' ;;
    *cpp*|*cc*|*hpp*) printf 'cpp' ;;
    *c|*h)    printf 'c' ;;
    *)        printf 'mixed' ;;
  esac
}

classify_repo() {
  local repo="$1"
  local loc
  loc=$(find "$repo" -type f \( -name "*.go" -o -name "*.py" -o -name "*.ts" -o -name "*.js" -o -name "*.rs" -o -name "*.java" -o -name "*.cpp" -o -name "*.c" \) -not -path "*/node_modules/*" -not -path "*/.git/*" -not -path "*/vendor/*" 2>/dev/null | wc -l)
  if [ "$loc" -lt 20 ]; then printf 'small'
  elif [ "$loc" -lt 100 ]; then printf 'medium'
  else printf 'large'
  fi
}

# ── Workbench mode ─────────────────────────────────────────────────────────

init_workbench() {
  local root="${1:-$(dirname "$SCRIPT_DIR")}"
  [ -d "$root" ] || fail "workbench root $root does not exist"

  log "workbench root: $root"
  mkdir -p "$root/.osengineer/handoffs"
  touch "$root/.osengineer/handoffs/.gitkeep"

  # Check and clone OpenSpace if missing
  if [ ! -d "$root/OpenSpace" ]; then
    log "OpenSpace repo not found in workbench — cloning it from https://github.com/andreas2301/OpenSpace.git..."
    git clone https://github.com/andreas2301/OpenSpace.git "$root/OpenSpace" || warn "Failed to clone OpenSpace repo automatically. You will need to clone it manually."
  fi

  # ── 1. Project name ───────────────────────────────────────────────────────
  local project_name
  project_name="$(prompt "Project name" "$(basename "$root")")"
  log "project: $project_name"

  # ── 2. Discover repos ─────────────────────────────────────────────────────
  local discovered=()
  for candidate in "$root"/*; do
    [ -d "$candidate/.git" ] || continue
    discovered+=("$candidate")
  done

  printf 'Discovered %d repo(s):\n' "${#discovered[@]}"
  for d in "${discovered[@]}"; do
    printf '  · %s\n' "$(basename "$d")"
  done

  local use_all
  use_all="$(prompt_yn "Use all discovered repos?")"
  local repos=()
  if [ "$use_all" = "y" ]; then
    repos=("${discovered[@]}")
  else
    for d in "${discovered[@]}"; do
      local name
      name="$(basename "$d")"
      local inc
      inc="$(prompt_yn "Include $name?" "y")"
      [ "$inc" = "y" ] && repos+=("$d")
    done
  fi

  # Allow adding extra paths
  while true; do
    local extra
    extra="$(prompt "Additional repo path (or empty to finish)")"
    [ -z "$extra" ] && break
    extra="$(cd "$root" && realpath -m "$extra" 2>/dev/null || echo "$extra")"
    if [ -d "$extra/.git" ]; then
      repos+=("$extra")
      log "  + added $(basename "$extra")"
    else
      warn "$extra is not a git repo — skipping"
    fi
  done

  # ── 3. META repo ──────────────────────────────────────────────────────────
  local meta_candidates=()
  for candidate in "$root"/*; do
    [ -d "$candidate/.git" ] || continue
    local readme="$candidate/README.md"
    if [ -f "$readme" ] && grep -qiE 'source of truth|architecture|adr' "$readme" 2>/dev/null; then
      meta_candidates+=("$candidate")
    elif [ -d "$candidate/docs/adr" ] || [ -d "$candidate/documentation/adr" ]; then
      meta_candidates+=("$candidate")
    fi
  done

  local meta_repo=""
  local meta_choice
  printf 'META repo candidates (%d found):\n' "${#meta_candidates[@]}"
  local idx=1
  for c in "${meta_candidates[@]}"; do
    printf '  %d) %s\n' "$idx" "$(basename "$c")"
    idx=$((idx + 1))
  done
  printf '  %d) None — create a META repo skeleton\n' "$idx"
  idx=$((idx + 1))
  printf '  %d) None — skip META for now\n' "$idx"

  read -r -p "Select META repo option [1-$idx]: " meta_choice
  if [ -n "$meta_choice" ] && [ "$meta_choice" -ge 1 ] 2>/dev/null && [ "$meta_choice" -le "${#meta_candidates[@]}" ] 2>/dev/null; then
    meta_repo="${meta_candidates[$((meta_choice - 1))]}"
    log "META repo selected: $(basename "$meta_repo")"
  elif [ -n "$meta_choice" ] && [ "$meta_choice" -eq "$((idx - 1))" ] 2>/dev/null; then
    # Create META skeleton
    local meta_path="$root/meta"
    mkdir -p "$meta_path/docs/adr" "$meta_path/docs/teams"
    cat > "$meta_path/README.md" <<'META_README'
# META — Codified Source of Truth

This repo holds architecture decisions, team contracts, and cross-repo specifications.

## Structure

- `docs/adr/` — Architecture Decision Records
- `docs/teams/` — Team archetypes and conventions
- `docs/plans/` — Cross-repo phase plans
META_README
    cat > "$meta_path/docs/adr/ADR-001-project-charter.md" <<'META_ADR'
# ADR-001: Project Charter

## Status

Proposed

## Context

What is this project? Why does it exist? What are the constraints?

## Decision

(Write the initial architectural principles here.)

## Consequences

(What follows from this decision?)
META_ADR
    git -C "$meta_path" init >/dev/null 2>&1 || true
    meta_repo="$meta_path"
    log "META repo created: $meta_path"
  fi

  # ADR catalog discovery from META repo
  if [ -n "$meta_repo" ]; then
    node "$SCRIPT_DIR/bin/osengineer" discover-adrs "$meta_repo" \
      --out "$root/.osengineer/adr-catalog.yml" >/dev/null 2>&1 || true
    if [ -f "$root/.osengineer/adr-catalog.yml" ]; then
      local adr_count
      adr_count=$(awk '/^  - id:/ {n++} END {print n+0}' "$root/.osengineer/adr-catalog.yml" 2>/dev/null || echo 0)
      log "+ .osengineer/adr-catalog.yml ($adr_count ADRs from META)"
    fi
  fi

  # ── 4. Graphify ───────────────────────────────────────────────────────────
  local graphify_installed=false
  local graphify_path=""
  if command -v graphify >/dev/null 2>&1; then
    graphify_installed=true
    graphify_path="$(command -v graphify)"
    log "graphify detected: $graphify_path"
  else
    local clone_gf
    clone_gf="$(prompt_yn "graphify not found on PATH. Clone from GitHub?")"
    if [ "$clone_gf" = "y" ]; then
      local gf_dest
      gf_dest="$(prompt "Clone destination" "$HOME/.local/share/graphify")"
      mkdir -p "$(dirname "$gf_dest")"
      if [ ! -d "$gf_dest/.git" ]; then
        git clone https://github.com/safishamsi/graphify.git "$gf_dest" >/dev/null 2>&1 || warn "graphify clone failed; install manually later"
      fi
      if [ -d "$gf_dest/.git" ]; then
        graphify_installed=true
        graphify_path="$gf_dest"
        log "graphify cloned to $gf_dest"
        printf '\n>> Add to your PATH: export PATH="%s:$PATH"\n' "$gf_dest"
      fi
    fi
  fi

  # ── 5. Knowledge sources ──────────────────────────────────────────────────
  local has_confluence=false has_notion=false has_jira=false has_miro=false
  local has_figma=false has_linear=false has_slack=false
  printf '\n## Knowledge Sources ##\n'
  printf 'Which external platforms does this project use for docs, design, or tracking?\n'
  [ "$(prompt_yn "Confluence / Wiki?")" = "y" ] && has_confluence=true
  [ "$(prompt_yn "Notion?")" = "y" ] && has_notion=true
  [ "$(prompt_yn "Jira / Linear / Asana?")" = "y" ] && has_jira=true
  [ "$(prompt_yn "Miro / FigJam?")" = "y" ] && has_miro=true
  [ "$(prompt_yn "Figma?")" = "y" ] && has_figma=true
  [ "$(prompt_yn "Slack / Discord?")" = "y" ] && has_slack=true

  local confluence_url="" notion_url="" jira_url="" miro_url="" figma_url=""
  [ "$has_confluence" = true ] && confluence_url="$(prompt "Confluence base URL" "")"
  [ "$has_notion" = true ] && notion_url="$(prompt "Notion workspace URL" "")"
  [ "$has_jira" = true ] && jira_url="$(prompt "Jira/Linear project URL" "")"
  [ "$has_miro" = true ] && miro_url="$(prompt "Miro team URL" "")"
  [ "$has_figma" = true ] && figma_url="$(prompt "Figma file URL" "")"

  # ── 6. Project Overview ───────────────────────────────────────────────────
  local overview_file="$root/PROJECT_OVERVIEW.md"
  local overview_content=""

  # Try to synthesize from the first repo's README
  if [ ${#repos[@]} -gt 0 ]; then
    local first_readme="${repos[0]}/README.md"
    if [ -f "$first_readme" ]; then
      local readme_head
      readme_head="$(head -30 "$first_readme" 2>/dev/null || true)"
      if [ -n "$readme_head" ]; then
        overview_content="## Sourced from $(basename "${repos[0]}")/README.md

$readme_head
"
      fi
    fi
  fi

  printf '\n## Project Overview ##\n'
  printf 'osEngineer will create PROJECT_OVERVIEW.md for agents to read.\n'
  local user_overview
  user_overview="$(prompt "Describe this project in 1-2 sentences (or leave empty to use README)")"
  if [ -n "$user_overview" ]; then
    overview_content="$user_overview

$overview_content"
  fi

  cat > "$overview_file" <<OVERVIEW
# $project_name — Project Overview

**Generated by osEngineer init.** Agents read this file before starting work.

## What is this project?

$overview_content

## Tech Stack

| Repo | Language | Purpose |
|------|----------|---------|
OVERVIEW

  for r in "${repos[@]}"; do
    local rname rlang rpurpose
    rname="$(basename "$r")"
    rlang="$(detect_dominant_lang "$r")"
    rpurpose="$(head -3 "$r/README.md" 2>/dev/null | sed 's/^#* *//' || echo "—")"
    printf '| %s | %s | %s |\n' "$rname" "$rlang" "$rpurpose" >> "$overview_file"
  done

  cat >> "$overview_file" <<OVERVIEW

## Knowledge Sources

| Platform | URL | Use for |
|----------|-----|---------|
OVERVIEW

  if [ "$has_confluence" = true ]; then
    printf '| Confluence | %s | Architecture docs, runbooks, onboarding |\n' "$confluence_url" >> "$overview_file"
  fi
  if [ "$has_notion" = true ]; then
    printf '| Notion | %s | Product specs, meeting notes, roadmap |\n' "$notion_url" >> "$overview_file"
  fi
  if [ "$has_jira" = true ]; then
    printf '| Jira/Linear | %s | Tickets, incident history, sprint planning |\n' "$jira_url" >> "$overview_file"
  fi
  if [ "$has_miro" = true ]; then
    printf '| Miro | %s | Architecture diagrams, data flows |\n' "$miro_url" >> "$overview_file"
  fi
  if [ "$has_figma" = true ]; then
    printf '| Figma | %s | UI designs, component library |\n' "$figma_url" >> "$overview_file"
  fi
  if [ "$has_slack" = true ]; then
    printf '| Slack/Discord | — | Ad-hoc decisions, incident channels |\n' >> "$overview_file"
  fi
  if [ "$has_confluence" = false ] && [ "$has_notion" = false ] && [ "$has_jira" = false ] && [ "$has_miro" = false ] && [ "$has_figma" = false ] && [ "$has_slack" = false ]; then
    printf '| (none configured) | — | Add sources in `.osengineer/workbench-config.yml` |\n' >> "$overview_file"
  fi

  cat >> "$overview_file" <<'OVERVIEW'

## Agent Mandate

**Every agent MUST read this file before starting work on this project.**

- If the answer lives in an external knowledge source (Confluence, Notion, etc.), query that source before grepping raw code.
- If a diagram exists in Miro/Figma, reference it when explaining architecture.
- If a ticket exists in Jira/Linear, cite it in commit messages and phase plans.

## How to Update

1. Edit this file directly for high-level changes.
2. Re-run `osengineer init` to regenerate the repo table.
3. Update `.osengineer/workbench-config.yml` to add new knowledge sources.
OVERVIEW

  log "+ PROJECT_OVERVIEW.md"

  # ── 7. Write workbench-config.yml ─────────────────────────────────────────
  local config_file="$root/.osengineer/workbench-config.yml"
  cat > "$config_file" <<YAML
# osEngineer workbench configuration — generated by install.sh
schema_version: 1
project_name: "$project_name"
live_system_path: "$LIVE_SYSTEM_PATH"
validation_profile: "$VALIDATION_PROFILE"
droid_whispering:
  orchestrator_model: "$ORCHESTRATOR_MODEL"
  worker_model: "$WORKER_MODEL"
  validator_model: "$VALIDATOR_MODEL"
YAML

  if [ ${#repos[@]} -gt 0 ]; then
    printf '\ndiscovered_repos:\n' >> "$config_file"
    for r in "${repos[@]}"; do
      local rname rlang rclass rbranch
      rname="$(basename "$r")"
      rbranch="$(cd "$r" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"
      rlang="$(detect_dominant_lang "$r")"
      rclass="$(classify_repo "$r")"
      printf '  - path: "./%s"\n' "$rname" >> "$config_file"
      printf '    name: "%s"\n' "$rname" >> "$config_file"
      printf '    language: "%s"\n' "$rlang" >> "$config_file"
      printf '    classification: "%s"\n' "$rclass" >> "$config_file"
      printf '    default_branch: "%s"\n' "$rbranch" >> "$config_file"
    done
  fi

  if [ -n "$meta_repo" ]; then
    printf '\nmeta_repo:\n' >> "$config_file"
    printf '  path: "./%s"\n' "$(basename "$meta_repo")" >> "$config_file"
    printf '  name: "%s"\n' "$(basename "$meta_repo")" >> "$config_file"
    printf '  auto_detected: %s\n' "true" >> "$config_file"
  fi

  if [ "$graphify_installed" = true ]; then
    printf '\ngraphify:\n' >> "$config_file"
    printf '  installed: true\n' >> "$config_file"
    printf '  path: "%s"\n' "$graphify_path" >> "$config_file"
    printf '  output_dir: "graphify-out"\n' >> "$config_file"
  fi

  # Knowledge sources block
  printf '\nknowledge_sources:\n' >> "$config_file"
  [ "$has_confluence" = true ] && printf '  confluence: { url: "%s" }\n' "$confluence_url" >> "$config_file"
  [ "$has_notion" = true ] && printf '  notion: { url: "%s" }\n' "$notion_url" >> "$config_file"
  [ "$has_jira" = true ] && printf '  jira: { url: "%s" }\n' "$jira_url" >> "$config_file"
  [ "$has_miro" = true ] && printf '  miro: { url: "%s" }\n' "$miro_url" >> "$config_file"
  [ "$has_figma" = true ] && printf '  figma: { url: "%s" }\n' "$figma_url" >> "$config_file"
  [ "$has_slack" = true ] && printf '  slack: { url: "" }\n' >> "$config_file"

  log "+ .osengineer/workbench-config.yml"

  # ── 8. Workbench-level AGENTS.md ──────────────────────────────────────────
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
project_overview: ./PROJECT_OVERVIEW.md
---

# Workbench — $project_name

osEngineer-initialised workbench. See \`.osengineer/\` for cross-repo state and
\`./<repo>/AGENTS.md\` for each repo's team manifest.

## Project Overview

**All agents MUST read \`PROJECT_OVERVIEW.md\` before starting work.**
It contains the project description, tech stack, and knowledge source registry.

## Cross-repo handoffs

Run from this directory:
- \`osengineer handoff open --from-repo <r> --to-repo <r> --slug <s>\` to open a cross-repo ticket.
- \`osengineer handoff list\` to see open / closed XR-* tickets.
- Verify-phase transitions in any sub-repo are blocked while open XR tickets reference it.

## META repo

The META (Codified Source of Truth) repo holds ADRs, plans, team archetypes,
Confluence sync artifacts, and the graphify-out knowledge graph that spans
the workbench. Run \`osengineer explain teams\` for the model overview.
YAML
    log "+ workbench AGENTS.md"
  fi

  # Resumable init: track per-repo status in init-progress.yml
  local progress_file="$root/.osengineer/init-progress.yml"
  if [ ! -f "$progress_file" ]; then
    cat > "$progress_file" <<YAML
# osEngineer workbench init progress. Each entry: <repo-name>: <pending|complete|failed>.
osengineer_version: $VERSION
started_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
repos:
YAML
  fi

  # Iterate repos
  local skipped=0
  local processed=0
  for repo in "${repos[@]}"; do
    [ -d "$repo/.git" ] || continue
    local repo_name
    repo_name=$(basename "$repo")
    if grep -q "^  $repo_name: complete" "$progress_file" 2>/dev/null; then
      log "  · $repo_name already complete; skipping (delete .osengineer/init-progress.yml to force)"
      skipped=$((skipped + 1))
      continue
    fi
    if init_repo "$repo"; then
      if grep -q "^  $repo_name:" "$progress_file" 2>/dev/null; then
        sed -i.bak "s|^  $repo_name:.*|  $repo_name: complete|" "$progress_file"
        rm -f "$progress_file.bak"
      else
        printf '  %s: complete\n' "$repo_name" >> "$progress_file"
      fi
      processed=$((processed + 1))
    else
      if grep -q "^  $repo_name:" "$progress_file" 2>/dev/null; then
        sed -i.bak "s|^  $repo_name:.*|  $repo_name: failed|" "$progress_file"
        rm -f "$progress_file.bak"
      else
        printf '  %s: failed\n' "$repo_name" >> "$progress_file"
      fi
    fi
  done

  log "workbench init complete: $processed processed, $skipped skipped (resumable via $progress_file)"
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

# Collect inputs once at start
collect_interactive_inputs

if [ $# -eq 0 ]; then
  cat <<USAGE
osEngineer installer — version $VERSION

Usage:
  $0 <repo-path>                Initialise a single repo
  $0 --workbench [<path>]       Initialise every .git repo under <path>
  $0 --all                      --workbench plus any extra repos specified interactively
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
