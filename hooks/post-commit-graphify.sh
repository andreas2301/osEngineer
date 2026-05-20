#!/usr/bin/env bash
# post-commit-graphify.sh — Auto-rebuild graphify on commit.
# Install: ln -s $(pwd)/hooks/post-commit-graphify.sh .git/hooks/post-commit
#
# Skip filter: exits early if all changed files are inside graphify-out/.
# This prevents infinite auto-commit loops.

set -euo pipefail

GRAPHIFY_OUT="graphify-out/"

# Check if all changed files are inside graphify-out/
all_in_graphify=true
for file in $(git diff --name-only HEAD~1 HEAD); do
  if [[ ! "$file" =~ ^$GRAPHIFY_OUT ]]; then
    all_in_graphify=false
    break
  fi
done

if [ "$all_in_graphify" = true ]; then
  echo "[post-commit-graphify] Skipping — all changes inside $GRAPHIFY_OUT"
  exit 0
fi

# Run AST-only rebuild (deterministic, no LLM)
if command -v graphify &> /dev/null; then
  echo "[post-commit-graphify] Running AST rebuild..."
  graphify build --ast-only || true
else
  echo "[post-commit-graphify] graphify not installed — skipping"
fi
