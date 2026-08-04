#!/usr/bin/env python3
# validate_agents_frontmatter.py — minimal schema validation for AGENTS.md frontmatter.
# Usage: validate_agents_frontmatter.py
# Reads frontmatter JSON from FRONTMATTER_JSON env var; prints warnings to stderr.

import json
import os
import sys


def main():
    try:
        o = json.loads(os.environ.get("FRONTMATTER_JSON", "{}"))
    except Exception as e:
        sys.stderr.write(f"invalid JSON: {e}")
        sys.exit(1)

    e = []
    if not isinstance(o, dict) or o.get("scope") not in ("workbench", "repo", "team"):
        e.append("scope must be workbench|repo|team")
    if o.get("schema_version") is not None and o.get("schema_version") != 1:
        e.append("schema_version must be 1")
    if o.get("scope") == "workbench" and o.get("repos") is not None and not isinstance(o["repos"], list):
        e.append("repos must be array")
    if o.get("scope") == "repo" and o.get("teams") is not None and not isinstance(o["teams"], list):
        e.append("teams must be array")
    if o.get("scope") == "team" and o.get("team_id") is None:
        e.append("team scope requires team_id")
    for k in ("owns_paths", "reads_paths", "excludes", "agents"):
        if o.get(k) is not None and not isinstance(o[k], list):
            e.append(k + " must be array")
    if e:
        sys.stderr.write("; ".join(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
