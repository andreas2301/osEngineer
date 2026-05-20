#!/usr/bin/env bash
# pre-commit-schema-lint.sh — Validate contracts before commit.
# Install: ln -s $(pwd)/hooks/pre-commit-schema-lint.sh .git/hooks/pre-commit

set -euo pipefail

ERRORS=0

# Find JSON schema files changed in this commit
for file in $(git diff --cached --name-only --diff-filter=ACM | grep '\.json$' || true); do
  if [[ "$file" =~ schema ]] || [[ "$file" =~ contract ]]; then
    if command -v check-jsonschema &> /dev/null; then
      echo "[pre-commit-schema] Validating $file..."
      check-jsonschema --schemafile "$file" /dev/null 2>/dev/null || {
        echo "[pre-commit-schema] ERROR: $file is not valid JSON Schema"
        ERRORS=$((ERRORS + 1))
      }
    fi
  fi
done

if [ $ERRORS -gt 0 ]; then
  echo "[pre-commit-schema] $ERRORS schema validation error(s). Commit aborted."
  exit 1
fi
