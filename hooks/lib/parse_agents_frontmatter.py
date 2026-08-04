#!/usr/bin/env python3
# parse_agents_frontmatter.py — extract and minimally validate AGENTS.md frontmatter.
# Usage: parse_agents_frontmatter.py <AGENTS.md>
# Exit codes:
#   0 — success, frontmatter JSON printed to stdout
#   2 — no YAML frontmatter
#   3 — missing required 'scope:' discriminator
#   1 — other error

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from osengineer_common import parse_frontmatter


def scalar(v):
    v = v.strip()
    if v == "":
        return ""
    if v == "true":
        return True
    if v == "false":
        return False
    if v in ("null", "~"):
        return None
    if re.match(r"^-?\d+$", v):
        return int(v)
    if re.match(r"^-?\d+\.\d+$", v):
        return float(v)
    if re.match(r"^\[.*\]$", v):
        inner = v[1:-1].strip()
        return [scalar(x) for x in inner.split(",")] if inner else []
    return v.strip("\"'")


def deep_parse(fm_lines):
    root = {}
    stack = [{"indent": -1, "node": root}]
    i = 0
    while i < len(fm_lines):
        line = fm_lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        indent = len(line) - len(line.lstrip())
        while len(stack) > 1 and indent <= stack[-1]["indent"]:
            stack.pop()
        parent = stack[-1]["node"]
        body = line[indent:]
        if body.startswith("- "):
            if not isinstance(parent, list):
                i += 1
                continue
            item = body[2:]
            km = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", item)
            if km:
                obj = {}
                if km.group(2) != "":
                    obj[km.group(1)] = scalar(km.group(2))
                parent.append(obj)
                stack.append({"indent": indent, "node": obj})
            else:
                parent.append(scalar(item))
            i += 1
            continue
        km = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", body)
        if not km:
            i += 1
            continue
        if km.group(2) == "":
            j = i + 1
            while j < len(fm_lines) and not fm_lines[j].strip():
                j += 1
            is_list = j < len(fm_lines) and re.match(r"^\s*-\s+", fm_lines[j][indent + 1:])
            child = [] if is_list else {}
            parent[km.group(1)] = child
            stack.append({"indent": indent, "node": child})
        else:
            parent[km.group(1)] = scalar(km.group(2))
        i += 1
    return root


def main():
    if len(sys.argv) < 2:
        print("Usage: parse_agents_frontmatter.py <AGENTS.md>", file=sys.stderr)
        sys.exit(1)
    src = Path(sys.argv[1]).read_text()
    m = re.match(r"^---\r?\n([\s\S]*?)\r?\n---", src)
    if not m:
        print("NO_FRONTMATTER", file=sys.stderr)
        sys.exit(2)
    lines = m.group(1).splitlines()
    root = deep_parse(lines)
    if not isinstance(root, dict) or "scope" not in root:
        print("MISSING_SCOPE", file=sys.stderr)
        sys.exit(3)
    print(json.dumps(root))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
