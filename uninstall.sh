#!/usr/bin/env bash
# uninstall.sh — Remove osEngineer wiring from target project(s).
#
# Usage:
#   ./uninstall.sh <repo-path>              # Remove from a single repo
#   ./uninstall.sh --workbench [<path>]     # Remove from every .git repo under <path>
#   ./uninstall.sh --global                 # Remove global git hooks
#   ./uninstall.sh --all                    # All of the above
#
# Idempotent and safe. Only removes files/directories that osEngineer created.
# Asks before deleting planning directories or user-modified files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(cat "$SCRIPT_DIR/VERSION" 2>/dev/null || echo "0.0.0-dev")"

log() { printf '[osEngineer-uninstall] %s\n' "$*"; }
warn() { printf '[osEngineer-uninstall] WARNING: %s\n' "$*" >&2; }

# ── Helpers ────────────────────────────────────────────────────────────────

is_osengineer_hook() {
  local f="$1"
  [ -f "$f" ] && head -3 "$f" 2>/dev/null | grep -q 'osEngineer'
}

# ── Per-repo uninstall ─────────────────────────────────────────────────────

uninstall_repo() {
  local repo="$1"
  local repo_name
  repo_name="$(basename "$repo")"

  [ -d "$repo/.git" ] || { warn "$repo is not a git repo — skipping"; return 0; }

  log "── removing from $repo_name ──"

  # 1. Git hooks
  local ghooks="$repo/.git/hooks"
  if [ -d "$ghooks" ]; then
    for hook in commit-msg pre-commit post-commit; do
      local dst="$ghooks/$hook"
      if [ -f "$dst" ] && is_osengineer_hook "$dst"; then
        if [ -f "$dst.pre-osengineer" ]; then
          mv "$dst.pre-osengineer" "$dst"
          log "  · restored original $hook hook"
        else
          rm -f "$dst"
          log "  · removed $hook hook"
        fi
      fi
    done
  fi

  # 2. .osengineer/ directory
  if [ -d "$repo/.osengineer" ]; then
    local has_user_data=false
    # Anything beyond the default seeded files counts as user data
    if [ -n "$(find "$repo/.osengineer" -type f 2>/dev/null \
      | grep -v '/handoffs/\.gitkeep$' \
      | grep -v '/bypass-log\.jsonl$' \
      | grep -v '/state\.yml$' \
      | grep -v '/evolution-counter\.yml$' \
      | grep -v '/teams/' \
      | grep -v '/init-progress\.yml$' \
      | grep -v '/adr-catalog\.yml$' \
      | grep -v '/evolution-proposals/' \
      | grep -v '/evolution-rejections\.jsonl$' \
      | head -1)" ]; then
      has_user_data=true
    fi
    if [ "$has_user_data" = true ]; then
      read -r -p "[osEngineer-uninstall] $repo_name/.osengineer/ contains user data. Delete? [y/N] " response
      if [[ "$response" =~ ^[Yy]$ ]]; then
        rm -rf "$repo/.osengineer"
        log "  · .osengineer/ removed"
      else
        log "  · .osengineer/ kept (user declined)"
      fi
    else
      rm -rf "$repo/.osengineer"
      log "  · .osengineer/ removed"
    fi
  fi

  # 3. Assistant runtime directories (.claude/, .kimi/, .codex/)
  for runtime in claude kimi codex; do
    local runtime_dir="$repo/.$runtime"
    if [ ! -d "$runtime_dir" ]; then
      continue
    fi

    # Remove osEngineer agent files. Source agents may be dir-style
    # (agents/<role>/AGENT.md) or flat (agents/<role>.md); install.sh copies
    # either to a flat .<runtime>/agents/<role>.md, so derive the destination
    # filenames from BOTH source layouts (the old flat-only glob missed the
    # dir-style agents entirely and left them behind).
    if [ -d "$runtime_dir/agents" ]; then
      local removed=0
      local src fname
      for src in "$SCRIPT_DIR"/agents/*/AGENT.md; do
        [ -f "$src" ] || continue
        fname="$(basename "$(dirname "$src")").md"
        if [ -f "$runtime_dir/agents/$fname" ]; then
          rm -f "$runtime_dir/agents/$fname"
          removed=$((removed + 1))
        fi
      done
      for src in "$SCRIPT_DIR"/agents/*.md; do
        [ -f "$src" ] || continue
        fname="$(basename "$src")"
        if [ -f "$runtime_dir/agents/$fname" ]; then
          rm -f "$runtime_dir/agents/$fname"
          removed=$((removed + 1))
        fi
      done
      if [ $removed -gt 0 ]; then
        log "  · $removed agent files removed from .$runtime/agents/"
      fi
      # Mirror of install.sh's copy_agent_references: remove only the per-role
      # subdirs we created under agents/references/, never the whole tree — a
      # repo may keep its own references/ content there.
      if [ -d "$runtime_dir/agents/references" ]; then
        local role
        for src in "$SCRIPT_DIR"/agents/*/references; do
          [ -d "$src" ] || continue
          role="$(basename "$(dirname "$src")")"
          rm -rf "${runtime_dir:?}/agents/references/${role:?}"
        done
        rmdir "$runtime_dir/agents/references" 2>/dev/null || true
      fi
      rmdir "$runtime_dir/agents" 2>/dev/null || true
    fi

    # Revert osEngineer merge in settings.json (Python)
    if [ -f "$runtime_dir/settings.json" ]; then
      local cfg="$runtime_dir/settings.json"
      python3 - "$cfg" <<'PY' 2>/dev/null && log "  · .$runtime/settings.json reverted"
import json, os, sys
path = sys.argv[1]
try:
    with open(path) as f:
        existing = json.load(f)
except Exception:
    raise SystemExit(0)

def is_ose_entry(entry):
    if not entry or not isinstance(entry.get("hooks"), list):
        return False
    return any(isinstance(h, dict) and isinstance(h.get("command"), str) and "osEngineer-" in h["command"] for h in entry["hooks"])

for event in list((existing.get("hooks") or {}).keys()):
    existing["hooks"][event] = [e for e in existing["hooks"][event] if not is_ose_entry(e)]
    if not existing["hooks"][event]:
        del existing["hooks"][event]
if not existing.get("hooks"):
    existing.pop("hooks", None)

status_line = existing.get("statusLine") or {}
if isinstance(status_line, dict) and isinstance(status_line.get("command"), str) and "osEngineer-statusline" in status_line["command"]:
    existing.pop("statusLine", None)

env = existing.get("env") or {}
for key in ("OSENGINEER_HOME", "OSENGINEER_VERSION"):
    env.pop(key, None)
if env:
    existing["env"] = env
else:
    existing.pop("env", None)

if not existing:
    os.unlink(path)
else:
    with open(path, "w") as f:
        json.dump(existing, f, indent=2)
        f.write("\n")
PY
      rmdir "$runtime_dir" 2>/dev/null || true
    fi
  done

  # 4. AGENTS.md — remove only if generated by osEngineer
  if [ -f "$repo/AGENTS.md" ] && grep -q 'osengineer_version:' "$repo/AGENTS.md" 2>/dev/null; then
    rm -f "$repo/AGENTS.md"
    log "  · AGENTS.md removed"
  fi

  # 5. CLAUDE.md — remove osEngineer section only
  if [ -f "$repo/CLAUDE.md" ] && grep -q '## osEngineer' "$repo/CLAUDE.md" 2>/dev/null; then
    local line_count
    line_count="$(wc -l < "$repo/CLAUDE.md" | tr -d ' ')"
    if [ "$line_count" -le 10 ]; then
      rm -f "$repo/CLAUDE.md"
      log "  · CLAUDE.md removed (only osEngineer content)"
    else
      python3 - "$repo/CLAUDE.md" <<'PY' 2>/dev/null && log "  · osEngineer section removed from CLAUDE.md"
import re, sys
path = sys.argv[1]
with open(path) as f:
    content = f.read()
lines = content.splitlines()
start = -1
end = len(lines)
for i, line in enumerate(lines):
    if re.match(r'^##\s+osEngineer\s*$', line):
        start = i
    elif start != -1 and re.match(r'^##\s+', line):
        end = i
        break
if start == -1:
    raise SystemExit(0)
out = "\n".join(lines[:start] + lines[end:])
out = re.sub(r'\n{3,}', '\n\n', out)
with open(path, "w") as f:
    f.write(out)
PY
    fi
  fi

  # 6. git safe.directory
  git config --global --unset safe.directory "$repo" 2>/dev/null || true
}

# ── Workbench uninstall ────────────────────────────────────────────────────

uninstall_workbench() {
  local root="${1:-$(dirname "$SCRIPT_DIR")}"
  [ -d "$root" ] || { warn "workbench root $root does not exist"; return 0; }

  log "workbench root: $root"

  for repo in "$root"/*; do
    [ -d "$repo/.git" ] || continue
    uninstall_repo "$repo"
  done

  # Workbench-level files
  if [ -f "$root/AGENTS.md" ] && grep -q 'scope: workbench' "$root/AGENTS.md" 2>/dev/null; then
    rm -f "$root/AGENTS.md"
    log "  · workbench AGENTS.md removed"
  fi

  if [ -d "$root/.osengineer" ]; then
    read -r -p "[osEngineer-uninstall] Remove workbench-level .osengineer/? [y/N] " response
    if [[ "$response" =~ ^[Yy]$ ]]; then
      rm -rf "$root/.osengineer"
      log "  · workbench .osengineer/ removed"
    fi
  fi
}

# ── Global hooks uninstall ─────────────────────────────────────────────────

uninstall_global_hooks() {
  log "removing global git hooks"
  local gdir
  gdir="$(git config --global core.hooksPath 2>/dev/null || echo "")"
  if [ -z "$gdir" ]; then
    gdir="$HOME/.git-hooks"
  fi
  if [ -d "$gdir" ]; then
    for hook in commit-msg pre-commit post-commit; do
      local dst="$gdir/$hook"
      if [ -f "$dst" ] && is_osengineer_hook "$dst"; then
        if [ -f "$dst.pre-osengineer" ]; then
          mv "$dst.pre-osengineer" "$dst"
          log "  · restored original global $hook hook"
        else
          rm -f "$dst"
          log "  · removed global $hook hook"
        fi
      fi
    done
  fi

  local current_path
  current_path="$(git config --global core.hooksPath 2>/dev/null || echo "")"
  if [ "$current_path" = "$gdir" ]; then
    read -r -p "[osEngineer-uninstall] Unset global core.hooksPath? [y/N] " response
    if [[ "$response" =~ ^[Yy]$ ]]; then
      git config --global --unset core.hooksPath 2>/dev/null || true
      log "  · core.hooksPath unset"
    fi
  fi
}

# ── Dispatch ───────────────────────────────────────────────────────────────

if [ $# -eq 0 ]; then
  cat <<USAGE
osEngineer uninstaller — version $VERSION

Usage:
  $0 <repo-path>                Remove from a single repo
  $0 --workbench [<path>]       Remove from every .git repo under <path>
  $0 --global                   Remove global git hooks
  $0 --all                      All of the above

USAGE
  exit 1
fi

case "$1" in
  --workbench)
    uninstall_workbench "${2:-}"
    ;;
  --global)
    uninstall_global_hooks
    ;;
  --all)
    uninstall_workbench
    uninstall_global_hooks
    ;;
  -h|--help)
    cat <<USAGE
osEngineer uninstaller — version $VERSION
Usage: $0 <repo-path> | --workbench [<path>] | --global | --all
USAGE
    ;;
  *)
    uninstall_repo "$1"
    ;;
esac

log "osEngineer uninstall complete (version $VERSION)"
