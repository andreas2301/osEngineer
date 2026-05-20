#!/usr/bin/env bash
# uninstall.sh — Remove osEngineer wiring from target project(s).
#
# Usage:
#   ./uninstall.sh /path/to/project              # Remove from a project
#   ./uninstall.sh --workbench                   # Remove from workbench repos
#   ./uninstall.sh --global                      # Remove global git hooks
#   ./uninstall.sh --all                         # All of the above
#
# This script is idempotent and safe. It only removes symlinks and
# directories that osEngineer created. It will ASK before deleting
# planning directories that contain user data.

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

# ── Project uninstall ────────────────────────────────────────────
uninstall_from_project() {
  local project_root="$1"

  if [ ! -d "$project_root" ]; then
    echo "[uninstall] WARNING: $project_root does not exist"
    return 0
  fi

  echo "[uninstall] Removing osEngineer from $project_root"

  # 1. Remove symlinks from .git/hooks
  echo "[uninstall] Removing git hooks..."
  for repo in $(find "$project_root" -maxdepth 2 -type d -name ".git" | sed 's|/.git$||'); do
    local hooks_dir="$repo/.git/hooks"
    local repo_name
    repo_name=$(basename "$repo")

    if [ -L "$hooks_dir/post-commit-graphify" ]; then
      rm -f "$hooks_dir/post-commit-graphify"
      echo "[uninstall]   - post-commit-graphify → $repo_name"
    fi
    if [ -L "$hooks_dir/pre-commit-schema-lint" ]; then
      rm -f "$hooks_dir/pre-commit-schema-lint"
      echo "[uninstall]   - pre-commit-schema-lint → $repo_name"
    fi
  done

  # 2. Remove .claude/settings.json if it matches our template
  echo "[uninstall] Removing zeroclaw config..."
  for repo in $(find "$project_root" -maxdepth 2 -type d -name ".git" | sed 's|/.git$||'); do
    local settings="$repo/.claude/settings.json"
    local repo_name
    repo_name=$(basename "$repo")

    if [ -f "$settings" ] && grep -q "graphify-out/graph.json" "$settings" 2>/dev/null; then
      rm -f "$settings"
      echo "[uninstall]   - .claude/settings.json → $repo_name"
      # Remove empty .claude directory
      rmdir "$repo/.claude" 2>/dev/null || true
    fi
  done

  # 3. Ask before removing planning directories (may contain user data)
  if [ -d "$project_root/planning" ]; then
    local has_user_data=false
    if [ -n "$(find "$project_root/planning" -type f 2>/dev/null | head -1)" ]; then
      has_user_data=true
    fi

    if [ "$has_user_data" = true ]; then
      read -r -p "[uninstall] $project_root/planning/ contains files. Delete? [y/N] " response
      if [[ "$response" =~ ^[Yy]$ ]]; then
        rm -rf "$project_root/planning"
        echo "[uninstall]   - planning/ removed"
      else
        echo "[uninstall]   - planning/ kept (user declined)"
      fi
    else
      rm -rf "$project_root/planning"
      echo "[uninstall]   - planning/ removed (empty)"
    fi
  fi

  # 4. Remove safe.directory entries (best effort)
  echo "[uninstall] Removing git safe.directory entries..."
  for repo in $(find "$project_root" -maxdepth 2 -type d -name ".git" | sed 's|/.git$||'); do
    git config --global --unset safe.directory "$repo" 2>/dev/null || true
  done

  echo "[uninstall] Done for $project_root"
}

# ── Workbench uninstall ──────────────────────────────────────────
uninstall_from_workbench() {
  local workbench="/home/engineer/.zeroclaw/workspace/workbench"

  if [ ! -d "$workbench" ]; then
    echo "[uninstall] Workbench not found at $workbench"
    return 0
  fi

  echo "[uninstall] Removing from all workbench repos..."

  for repo in "$workbench"/*; do
    if [ -d "$repo/.git" ]; then
      local repo_name
      repo_name=$(basename "$repo")
      echo "[uninstall] --- $repo_name ---"

      # Remove hooks
      local hooks_dir="$repo/.git/hooks"
      rm -f "$hooks_dir/post-commit-graphify" 2>/dev/null || true
      rm -f "$hooks_dir/pre-commit-schema-lint" 2>/dev/null || true

      # Remove settings.json if ours
      local settings="$repo/.claude/settings.json"
      if [ -f "$settings" ] && grep -q "graphify-out/graph.json" "$settings" 2>/dev/null; then
        rm -f "$settings"
        rmdir "$repo/.claude" 2>/dev/null || true
      fi

      # Remove safe.directory
      git config --global --unset safe.directory "$repo" 2>/dev/null || true

      # Ask before removing planning
      if [ -d "$repo/planning" ]; then
        local has_files
        has_files=$(find "$repo/planning" -type f 2>/dev/null | head -1)
        if [ -n "$has_files" ]; then
          read -r -p "[uninstall] $repo_name/planning/ contains files. Delete? [y/N] " response
          if [[ "$response" =~ ^[Yy]$ ]]; then
            rm -rf "$repo/planning"
            echo "[uninstall]   - planning/ removed"
          else
            echo "[uninstall]   - planning/ kept"
          fi
        else
          rm -rf "$repo/planning"
        fi
      fi
    fi
  done

  echo "[uninstall] Workbench uninstall complete"
}

# ── Global hooks uninstall ───────────────────────────────────────
uninstall_global_hooks() {
  echo "[uninstall] Removing global git hooks..."

  local global_hooks_dir
  global_hooks_dir="$(git config --global core.hooksPath 2>/dev/null || echo "")"

  if [ -z "$global_hooks_dir" ]; then
    global_hooks_dir="$HOME/.git-hooks"
  fi

  if [ -d "$global_hooks_dir" ]; then
    rm -f "$global_hooks_dir/post-commit-graphify" 2>/dev/null || true
    rm -f "$global_hooks_dir/pre-commit-schema-lint" 2>/dev/null || true
    echo "[uninstall] Global hooks removed from $global_hooks_dir"
  fi

  # Optionally unset global hooks path if it points to our dir
  local current_path
  current_path="$(git config --global core.hooksPath 2>/dev/null || echo "")"
  if [ "$current_path" = "$global_hooks_dir" ]; then
    read -r -p "[uninstall] Unset global core.hooksPath? [y/N] " response
    if [[ "$response" =~ ^[Yy]$ ]]; then
      git config --global --unset core.hooksPath 2>/dev/null || true
      echo "[uninstall] core.hooksPath unset"
    fi
  fi
}

# ── Main dispatch ────────────────────────────────────────────────
case "$MODE" in
  project)
    uninstall_from_project "$TARGET_PROJECT"
    ;;
  workbench)
    uninstall_from_workbench
    ;;
  global)
    uninstall_global_hooks
    ;;
  all)
    uninstall_from_workbench
    uninstall_global_hooks
    if [ -d "/opt/sovereign-shield" ]; then
      uninstall_from_project "/opt/sovereign-shield"
    fi
    echo "[uninstall] All modes complete"
    ;;
  *)
    echo "Usage: $0 <project-root> | --workbench | --global | --all"
    exit 1
    ;;
esac

echo "[uninstall] osEngineer removal complete"
