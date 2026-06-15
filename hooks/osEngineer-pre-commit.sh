#!/usr/bin/env bash
# osEngineer-pre-commit.sh — git pre-commit hook.
# Validates JSON Schema files against meta-schema (JSON Schema 2020-12).
# Validates staged AGENTS.md frontmatter against specs/SCHEMAS/agents-md.schema.json.
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
  # Parse YAML frontmatter -> JSON via Node, then validate.
  # Missing scope: is a hard error; other failures are warnings (schema still maturing).
  FRONTMATTER_JSON=$(SCHEMA_FILE="$SCHEMA_FILE" node -e '
const fs=require("fs");
const src=fs.readFileSync(process.argv[1],"utf8");
const m=src.match(/^---\r?\n([\s\S]*?)\r?\n---/);
if (!m) { console.error("NO_FRONTMATTER"); process.exit(2); }
const lines=m[1].split(/\r?\n/);
const scalar=v=>{v=v.trim();if(v==="")return"";if(v==="true")return true;if(v==="false")return false;if(v==="null"||v==="~")return null;if(/^-?\d+$/.test(v))return parseInt(v,10);if(/^-?\d+\.\d+$/.test(v))return parseFloat(v);if(/^\[.*\]$/.test(v)){const i=v.slice(1,-1).trim();return i?i.split(",").map(s=>scalar(s.replace(/^["\x27]|["\x27]$/g,""))):[];}return v.replace(/^["\x27]|["\x27]$/g,"");};
const root={};
const stack=[{indent:-1,node:root}];
for(let i=0;i<lines.length;i++){
  const line=lines[i];
  if(!line.trim()||line.trim().startsWith("#"))continue;
  const indent=line.match(/^ */)[0].length;
  while(stack.length>1&&indent<=stack[stack.length-1].indent)stack.pop();
  const parent=stack[stack.length-1].node;
  const body=line.slice(indent);
  if(body.startsWith("- ")){
    if(!Array.isArray(parent))continue;
    const item=body.slice(2);
    const km=item.match(/^([A-Za-z_][\w-]*)\s*:\s*(.*)$/);
    if(km){const obj={};if(km[2]!=="")obj[km[1]]=scalar(km[2]);parent.push(obj);stack.push({indent,node:obj});}
    else parent.push(scalar(item));
    continue;
  }
  const km=body.match(/^([A-Za-z_][\w-]*)\s*:\s*(.*)$/);
  if(!km)continue;
  if(km[2]===""){
    let j=i+1;while(j<lines.length&&!lines[j].trim())j++;
    const isList=j<lines.length&&/^\s*-\s+/.test(lines[j].slice(indent+1));
    const child=isList?[]:{};
    parent[km[1]]=child;
    stack.push({indent,node:child});
  } else parent[km[1]]=scalar(km[2]);
}
if(!root||typeof root!=="object"||!("scope" in root)){console.error("MISSING_SCOPE");process.exit(3);}
process.stdout.write(JSON.stringify(root));
' "$file" 2>/dev/null)
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
    FRONTMATTER_JSON="$FRONTMATTER_JSON" node -e '
const o=JSON.parse(process.env.FRONTMATTER_JSON);const e=[];
if(!["workbench","repo","team"].includes(o.scope))e.push("scope must be workbench|repo|team");
if(o.schema_version!==undefined&&o.schema_version!==1)e.push("schema_version must be 1");
if(o.scope==="workbench"&&o.repos!==undefined&&!Array.isArray(o.repos))e.push("repos must be array");
if(o.scope==="repo"&&o.teams!==undefined&&!Array.isArray(o.teams))e.push("teams must be array");
if(o.scope==="team"&&o.team_id===undefined)e.push("team scope requires team_id");
for(const k of ["owns_paths","reads_paths","excludes","agents"])if(o[k]!==undefined&&!Array.isArray(o[k]))e.push(k+" must be array");
if(e.length){console.error(e.join("; "));process.exit(1);}' 2>&1 | while IFS= read -r line; do
        [ -n "$line" ] && echo "[osEngineer-pre-commit] WARNING: $file: $line (non-blocking)" >&2
      done
  fi
done

if [ $ERRORS -gt 0 ]; then
  echo "[osEngineer-pre-commit] $ERRORS validation error(s). Commit aborted. Bypass with OSE_BYPASS=1 if absolutely necessary."
  exit 1
fi

exit 0
