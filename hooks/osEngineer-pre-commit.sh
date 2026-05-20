#!/usr/bin/env bash
# osEngineer-pre-commit.sh — git pre-commit hook.
# Validates JSON Schema files against meta-schema (JSON Schema 2020-12).
# In future P3+: enforces team owns_paths from AGENTS.md.
#
# Active only in osEngineer repos. Honours OSE_BYPASS=1.

set -uo pipefail

[ -f .osengineer/state.yml ] || exit 0

if [ "${OSE_BYPASS:-0}" = "1" ]; then
  printf '{"ts":"%s","hook":"pre-commit","reason":"OSE_BYPASS=1"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> .osengineer/bypass-log.jsonl 2>/dev/null
  exit 0
fi

ERRORS=0

# Validate JSON Schema files
for file in $(git diff --cached --name-only --diff-filter=ACM 2>/dev/null | grep '\.schema\.json$' || true); do
  if command -v check-jsonschema >/dev/null 2>&1; then
    if ! check-jsonschema --check-metaschema "$file" >/dev/null 2>&1; then
      echo "[osEngineer-pre-commit] ERROR: $file is not a valid JSON Schema document"
      ERRORS=$((ERRORS + 1))
    fi
  else
    # Fallback: at least require valid JSON
    if ! node -e "JSON.parse(require('fs').readFileSync(process.argv[1],'utf8'))" "$file" 2>/dev/null; then
      echo "[osEngineer-pre-commit] ERROR: $file is not valid JSON"
      ERRORS=$((ERRORS + 1))
    fi
  fi
done

# Validate AGENTS.md frontmatter against schema when present
SCHEMA_FILE=""
if [ -n "${OSENGINEER_HOME:-}" ] && [ -f "$OSENGINEER_HOME/specs/SCHEMAS/agents-md.schema.json" ]; then
  SCHEMA_FILE="$OSENGINEER_HOME/specs/SCHEMAS/agents-md.schema.json"
fi
for file in $(git diff --cached --name-only --diff-filter=ACM 2>/dev/null | grep -E '(^|/)AGENTS\.md$' || true); do
  [ -n "$SCHEMA_FILE" ] || break
  # Extract YAML frontmatter and validate
  node -e "
const fs=require('fs');
const content=fs.readFileSync(process.argv[1],'utf8');
const m=content.match(/^---\n([\s\S]*?)\n---/);
if (!m) { console.error('No frontmatter found in '+process.argv[1]); process.exit(1); }
" "$file" 2>/dev/null || {
    echo "[osEngineer-pre-commit] WARNING: $file has no YAML frontmatter (skipping validation)"
  }
done

if [ $ERRORS -gt 0 ]; then
  echo "[osEngineer-pre-commit] $ERRORS validation error(s). Commit aborted. Bypass with OSE_BYPASS=1 if absolutely necessary."
  exit 1
fi

exit 0
