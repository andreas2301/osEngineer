#!/usr/bin/env bash
# osEngineer-post-commit.sh — git post-commit hook.
# 1. Auto-rebuild graphify (AST-only) when HEAD advances on default branch.
# 2. Increment .osengineer/evolution-counter.yml phases_since_last_evolution.
#
# Skips if changed files are all under graphify-out/ (loop prevention).
# Skips if not on default branch (no thrash on feature branches).
# Skips if graphify binary not on PATH.
# Always exits 0 — must never block commit completion.
#
# Origin: combines logic from get-shit-done/hooks/gsd-graphify-update.sh
# + osEngineer/hooks/post-commit-graphify.sh, simplified per ADR-001.

set -uo pipefail

# Active only in osEngineer repos
[ -f .osengineer/state.yml ] || exit 0

# Bypass escape hatch
if [ "${OSE_BYPASS:-0}" = "1" ]; then
  printf '{"ts":"%s","hook":"post-commit","reason":"OSE_BYPASS=1"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> .osengineer/bypass-log.jsonl 2>/dev/null
  exit 0
fi

# Skip in CI
[ -z "${CI:-}" ] || exit 0

# Inside a git repo?
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

# Determine default branch
DEFAULT_BRANCH=""
for cand in main master trunk; do
  if git rev-parse --verify "$cand" >/dev/null 2>&1; then
    DEFAULT_BRANCH="$cand"
    break
  fi
done
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

# 1. Graphify rebuild — only on default branch, only when not all-graphify-out changes
if [ -n "$DEFAULT_BRANCH" ] && [ "$CURRENT_BRANCH" = "$DEFAULT_BRANCH" ]; then
  ALL_IN_GRAPHIFY=true
  for file in $(git diff --name-only HEAD~1 HEAD 2>/dev/null); do
    if [[ ! "$file" =~ ^graphify-out/ ]]; then
      ALL_IN_GRAPHIFY=false
      break
    fi
  done
  if [ "$ALL_IN_GRAPHIFY" = false ] && command -v graphify >/dev/null 2>&1; then
    graphify update . --ast-only >/dev/null 2>&1 || true
  fi
fi

# 2. Increment evolution counter
COUNTER_FILE=".osengineer/evolution-counter.yml"
if [ -f "$COUNTER_FILE" ]; then
  node -e "
const fs=require('fs');
const path='$COUNTER_FILE';
try {
  const content = fs.readFileSync(path, 'utf8');
  const lines = content.split('\n');
  let changed = false;
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^(phases_since_last_evolution:\s*)(\d+)/);
    if (m) {
      lines[i] = m[1] + (parseInt(m[2], 10) + 1);
      changed = true;
      break;
    }
  }
  if (changed) fs.writeFileSync(path, lines.join('\n'));
} catch {}
" 2>/dev/null || true
fi

exit 0
