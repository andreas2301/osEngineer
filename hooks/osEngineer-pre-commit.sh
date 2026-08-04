#!/usr/bin/env bash
# osEngineer-pre-commit.sh — git pre-commit hook.
# Validates JSON Schema files against meta-schema (JSON Schema 2020-12).
# Validates staged AGENTS.md frontmatter against specs/SCHEMAS/agents-md.schema.json.
#
# Active only in osEngineer repos. Honours OSE_BYPASS=1.
# Requires: python3 (no Node).

set -uo pipefail

[ -f .osengineer/state.yml ] || exit 0

if [ "${OSE_BYPASS:-0}" = "1" ]; then
  printf '{"ts":"%s","hook":"pre-commit","reason":"OSE_BYPASS=1"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> .osengineer/bypass-log.jsonl 2>/dev/null
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[osEngineer-pre-commit] WARNING: python3 not found; skipping validation" >&2
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
    if ! python3 -c "import json, sys; json.load(open(sys.argv[1]))" "$file" 2>/dev/null; then
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

  FRONTMATTER_JSON=$(python3 "$OSENGINEER_HOME/hooks/lib/parse_agents_frontmatter.py" "$file" 2>/dev/null)
  RC=$?
  if [ $RC -eq 2 ]; then
    echo "[osEngineer-pre-commit] WARNING: $file has no YAML frontmatter (skipping validation)"
    continue
  fi
  if [ $RC -eq 3 ]; then
    echo "[osEngineer-pre-commit] ERROR: $file frontmatter missing required 'scope:' discriminator" >&2
    ERRORS=$((ERRORS + 1))
    continue
  fi
  if [ $RC -ne 0 ] || [ -z "$FRONTMATTER_JSON" ]; then
    echo "[osEngineer-pre-commit] WARNING: $file frontmatter could not be parsed (skipping)" >&2
    continue
  fi
  if command -v check-jsonschema >/dev/null 2>&1; then
    TMP_JSON=$(mktemp 2>/dev/null || echo "/tmp/agents-md-$$.json")
    printf '%s' "$FRONTMATTER_JSON" > "$TMP_JSON"
    check-jsonschema --schemafile "$SCHEMA_FILE" "$TMP_JSON" >/dev/null 2>&1 || \
      echo "[osEngineer-pre-commit] WARNING: $file frontmatter does not validate against agents-md.schema.json (non-blocking)" >&2
    rm -f "$TMP_JSON" 2>/dev/null
  else
    FRONTMATTER_JSON="$FRONTMATTER_JSON" python3 "$OSENGINEER_HOME/hooks/lib/validate_agents_frontmatter.py" 2>&1 | while IFS= read -r line; do
      [ -n "$line" ] && echo "[osEngineer-pre-commit] WARNING: $line (non-blocking)" >&2
    done
  fi
done

if [ $ERRORS -gt 0 ]; then
  echo "[osEngineer-pre-commit] $ERRORS validation error(s). Commit aborted. Bypass with OSE_BYPASS=1 if absolutely necessary."
  exit 1
fi

exit 0
