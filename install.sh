#!/usr/bin/env bash
# install.sh — Install osEngineer skill and wire into target project(s).
#
# Usage:
#   ./install.sh /path/to/project              # Install on a project
#   ./install.sh --workbench                   # Install on workbench repos
#   ./install.sh --global                      # Install global git hooks
#   ./install.sh --all                         # All of the above
#
# This script is idempotent. Re-running is safe.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_PROJECT=""
MODE=""

# Parse args
if [ $# -eq 0 ]; then
  echo "Usage: $0 <project-root> | --workbench | --global | --all"
  exit 1
fi

if [ "$1" = "--all" ]; then
  MODE="all"
elif [ "$1" = "--workbench" ]; then
  MODE="workbench"
elif [ "$1" = "--global" ]; then
  MODE="global"
else
  TARGET_PROJECT="$1"
  MODE="project"
fi

# Ensure gh is authenticated
if ! gh auth status &>/dev/null; then
  echo "[install] WARNING: gh CLI not authenticated. Git operations may fail."
  echo "[install] Run: gh auth login"
fi

# Ensure git is available
if ! command -v git &>/dev/null; then
  echo "[install] ERROR: git is required but not installed."
  exit 1
fi

# ── Project install ──────────────────────────────────────────────
install_on_project() {
  local project_root="$1"

  if [ ! -d "$project_root" ]; then
    echo "[install] ERROR: $project_root does not exist"
    return 1
  fi

  echo "[install] Installing osEngineer on $project_root"

  # 1. Discover repos and add safe.directory
  echo "[install] Configuring git safe.directory..."
  for repo in $(find "$project_root" -maxdepth 2 -type d -name ".git" | sed 's|/.git$||'); do
    local repo_name
    repo_name=$(basename "$repo")
    git config --global --add safe.directory "$repo" 2>/dev/null || true
    echo "[install]   + $repo_name"
  done

  # 2. Install hooks on repos that have .git/hooks
  echo "[install] Installing git hooks..."
  for repo in $(find "$project_root" -maxdepth 2 -type d -name ".git" | sed 's|/.git$||'); do
    local hooks_dir="$repo/.git/hooks"
    if [ -d "$hooks_dir" ]; then
      # Post-commit graphify hook
      if [ -f "$SCRIPT_DIR/hooks/post-commit-graphify.sh" ]; then
        ln -sf "$SCRIPT_DIR/hooks/post-commit-graphify.sh" "$hooks_dir/post-commit-graphify" 2>/dev/null || true
        echo "[install]   + graphify hook → $(basename "$repo")"
      fi
      # Pre-commit schema lint hook
      if [ -f "$SCRIPT_DIR/hooks/pre-commit-schema-lint.sh" ]; then
        ln -sf "$SCRIPT_DIR/hooks/pre-commit-schema-lint.sh" "$hooks_dir/pre-commit-schema-lint" 2>/dev/null || true
        echo "[install]   + schema lint hook → $(basename "$repo")"
      fi
    fi
  done

  # 3. Create planning directory structure if missing
  if [ ! -d "$project_root/planning" ]; then
    echo "[install] Creating planning directories..."
    mkdir -p "$project_root/planning/active"
    mkdir -p "$project_root/planning/completed"
    echo "[install]   + planning/active/"
    echo "[install]   + planning/completed/"
  fi

  # 4. Copy templates if missing
  if [ ! -f "$project_root/planning/TEMPLATES/PHASE_PLAN.md" ]; then
    echo "[install] Copying planning templates..."
    cp -r "$SCRIPT_DIR/planning/TEMPLATES" "$project_root/planning/" 2>/dev/null || true
    echo "[install]   + planning/TEMPLATES/"
  fi

  # 5. Wire the agent runtime repo config (.claude/settings.json)
  echo "[install] Wiring agent runtime config..."
  for repo in $(find "$project_root" -maxdepth 2 -type d -name ".git" | sed 's|/.git$||'); do
    local claude_dir="$repo/.claude"
    mkdir -p "$claude_dir"
    if [ ! -f "$claude_dir/settings.json" ]; then
      cat > "$claude_dir/settings.json" <<'JSON'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Glob|Grep",
        "hooks": [
          {
            "type": "command",
            "command": "[ -f graphify-out/graph.json ] && echo '{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"additionalContext\":\"graphify: Knowledge graph exists. Read graphify-out/GRAPH_REPORT.md for god nodes and community structure before searching raw files.\"}}' || true"
          }
        ]
      }
    ]
  }
}
JSON
      echo "[install]   + .claude/settings.json → $(basename "$repo")"
    fi
  done

  # 6. Check for graphify and suggest build
  if [ ! -d "$project_root/graphify-out" ]; then
    local first_repo
    first_repo=$(find "$project_root" -maxdepth 2 -type d -name ".git" | head -1 | sed 's|/.git$||')
    if [ -n "$first_repo" ]; then
      echo "[install] NOTE: No graphify-out/ found. Suggest running:"
      echo "  cd $first_repo && graphify build"
    fi
  fi

  echo "[install] Done for $project_root"
}

# ── Workbench install ────────────────────────────────────────────
install_on_workbench() {
  local workbench="<workbench-path>"

  if [ ! -d "$workbench" ]; then
    echo "[install] ERROR: Workbench not found at $workbench"
    return 1
  fi

  echo "[install] Installing on all workbench repos..."

  for repo in "$workbench"/*; do
    if [ -d "$repo/.git" ]; then
      local repo_name
      repo_name=$(basename "$repo")
      echo "[install] --- $repo_name ---"

      # Safe directory
      git config --global --add safe.directory "$repo" 2>/dev/null || true

      # Hooks
      local hooks_dir="$repo/.git/hooks"
      ln -sf "$SCRIPT_DIR/hooks/post-commit-graphify.sh" "$hooks_dir/post-commit-graphify" 2>/dev/null || true
      ln -sf "$SCRIPT_DIR/hooks/pre-commit-schema-lint.sh" "$hooks_dir/pre-commit-schema-lint" 2>/dev/null || true

      # Planning dirs
      mkdir -p "$repo/planning/active" "$repo/planning/completed" 2>/dev/null || true

      # agent runtime config wiring (.claude/settings.json)
      local claude_dir="$repo/.claude"
      mkdir -p "$claude_dir"
      if [ ! -f "$claude_dir/settings.json" ]; then
        cat > "$claude_dir/settings.json" <<'JSON'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Glob|Grep",
        "hooks": [
          {
            "type": "command",
            "command": "[ -f graphify-out/graph.json ] && echo '{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"additionalContext\":\"graphify: Knowledge graph exists. Read graphify-out/GRAPH_REPORT.md for god nodes and community structure before searching raw files.\"}}' || true"
          }
        ]
      }
    ]
  }
}
JSON
        echo "[install]   + .claude/settings.json → $repo_name"
      fi
    fi
  done

  echo "[install] Workbench install complete"
}

# ── Global git hooks ─────────────────────────────────────────────
install_global_hooks() {
  echo "[install] Installing global git hooks..."

  local global_hooks_dir
  global_hooks_dir="$(git config --global core.hooksPath 2>/dev/null || echo "")"

  if [ -z "$global_hooks_dir" ]; then
    global_hooks_dir="$HOME/.git-hooks"
    git config --global core.hooksPath "$global_hooks_dir"
    echo "[install] Set global hooks path: $global_hooks_dir"
  fi

  mkdir -p "$global_hooks_dir"

  ln -sf "$SCRIPT_DIR/hooks/post-commit-graphify.sh" "$global_hooks_dir/post-commit-graphify" 2>/dev/null || true
  ln -sf "$SCRIPT_DIR/hooks/pre-commit-schema-lint.sh" "$global_hooks_dir/pre-commit-schema-lint" 2>/dev/null || true

  echo "[install] Global hooks installed"
}

# ── Main dispatch ────────────────────────────────────────────────
case "$MODE" in
  project)
    install_on_project "$TARGET_PROJECT"
    ;;
  workbench)
    install_on_workbench
    ;;
  global)
    install_global_hooks
    ;;
  all)
    install_on_workbench
    install_global_hooks
    if [ -d "/opt/<project>" ]; then
      install_on_project "/opt/<project>"
    fi
    echo "[install] All modes complete"
    ;;
  *)
    echo "Usage: $0 <project-root> | --workbench | --global | --all"
    exit 1
    ;;
esac

echo "[install] osEngineer installation complete"
