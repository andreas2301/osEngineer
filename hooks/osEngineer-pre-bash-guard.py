#!/usr/bin/env python3
# osEngineer-pre-bash-guard.py — Claude PreToolUse hook on Bash.
#
# Blocks destructive bash commands without an active 4-part plan
# (.osengineer/current-plan.md). The 4-part plan must contain Touch/Change/
# Impact/Rollback sections.
#
# Patterns are loaded at runtime from trust/denylist.md (the readable
# contract). If the file is missing or malformed, the hook falls back to a
# hardcoded baseline so enforcement is never silently disabled.
#
# Per-team overrides can `disabled`, `downgraded_to_warning`, or `added` patterns.
# Honours OSE_BYPASS=1 (logged to .osengineer/bypass-log.jsonl).

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from osengineer_common import (
    bypass_log,
    find_osengineer_root,
    read_state_map,
)

STDIN_TIMEOUT_MS = 3000

FALLBACK_PATTERNS = [
    {"name": "rm -rf",           "regex": r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)"},
    {"name": "git push --force", "regex": r"\bgit\s+(?:\S+\s+)*push\s+(?:[^|;&]*\s)?(?:--force\b|-f\b)"},
    {"name": "git reset --hard", "regex": r"\bgit\s+(?:\S+\s+)*reset\s+--hard"},
    {"name": "docker rm",        "regex": r"\bdocker\s+(rm|volume\s+rm|system\s+prune)"},
    {"name": "kubectl delete",   "regex": r"\bkubectl\s+(?:\S+\s+)*delete\b"},
]


def find_denylist_file():
    home = os.environ.get("OSENGINEER_HOME")
    if home:
        p = Path(home) / "trust" / "denylist.md"
        if p.exists():
            return p
    sibling = Path(__file__).resolve().parent.parent / "trust" / "denylist.md"
    if sibling.exists():
        return sibling
    return None


def load_patterns():
    f = find_denylist_file()
    if not f:
        return FALLBACK_PATTERNS
    try:
        content = f.read_text()
    except Exception:
        return FALLBACK_PATTERNS
    m = re.search(r"```json\s*\n([\s\S]*?)\n```", content)
    if not m:
        return FALLBACK_PATTERNS
    try:
        parsed = json.loads(m.group(1))
    except Exception:
        return FALLBACK_PATTERNS
    if not isinstance(parsed, list):
        return FALLBACK_PATTERNS
    compiled = []
    for entry in parsed:
        if not entry or not isinstance(entry.get("name"), str) or not isinstance(entry.get("regex"), str):
            continue
        try:
            compiled.append({
                "name": entry["name"],
                "regex": re.compile(entry["regex"]),
                "category": entry.get("category", "uncategorised"),
            })
        except Exception:
            continue
    return compiled if compiled else FALLBACK_PATTERNS


def has_four_part_plan(repo_root):
    plan_path = Path(repo_root) / ".osengineer" / "current-plan.md"
    if not plan_path.exists():
        return False
    try:
        content = plan_path.read_text()
        required = ["touch", "change", "impact", "rollback"]
        return all(re.search(r"^#+\s*" + section + r"\b", content, re.IGNORECASE | re.MULTILINE) for section in required)
    except Exception:
        return False


def log_override(repo_root, entry):
    try:
        p = Path(repo_root) / ".osengineer" / "override-log.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": utc_now(), "hook": "pre-bash-guard"}
        record.update(entry)
        with open(p, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def utc_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def load_override_file(repo_root, file_path, source):
    p = Path(file_path)
    if not p.exists():
        return None
    try:
        raw = p.read_text()
    except Exception as e:
        log_override(repo_root, {"event": "override_parse_failure", "source": source, "file": str(file_path), "error": "read_error"})
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        log_override(repo_root, {"event": "override_parse_failure", "source": source, "file": str(file_path), "error": "json_parse_error"})
        return None
    if not parsed or not isinstance(parsed, dict):
        log_override(repo_root, {"event": "override_parse_failure", "source": source, "file": str(file_path), "error": "not_an_object"})
        return None
    out = {"disabled": [], "downgraded_to_warning": [], "added": []}
    if isinstance(parsed.get("disabled"), list):
        out["disabled"] = [s for s in parsed["disabled"] if isinstance(s, str)]
    if isinstance(parsed.get("downgraded_to_warning"), list):
        out["downgraded_to_warning"] = [s for s in parsed["downgraded_to_warning"] if isinstance(s, str)]
    if isinstance(parsed.get("added"), list):
        for entry in parsed["added"]:
            if not entry or not isinstance(entry.get("name"), str) or not isinstance(entry.get("regex"), str):
                continue
            try:
                out["added"].append({
                    "name": entry["name"],
                    "regex": re.compile(entry["regex"]),
                    "category": entry.get("category", "team-override"),
                })
            except Exception:
                log_override(repo_root, {"event": "override_parse_failure", "source": source, "file": str(file_path), "error": "invalid_regex", "name": entry.get("name")})
    return out


def build_effective_denylist(globals_, repo_ov, team_ov):
    downgraded = set()
    disabled = set()
    added = []
    if repo_ov:
        disabled.update(repo_ov.get("disabled", []))
        downgraded.update(repo_ov.get("downgraded_to_warning", []))
        for a in repo_ov.get("added", []):
            added.append({**a, "_source": "repo"})
    if team_ov:
        disabled.update(team_ov.get("disabled", []))
        downgraded.update(team_ov.get("downgraded_to_warning", []))
        for a in team_ov.get("added", []):
            added.append({**a, "_source": "team"})
    added = [a for a in added if a["name"] not in disabled]
    effective_globals = [p for p in globals_ if p["name"] not in disabled]
    return {
        "patterns": effective_globals + added,
        "downgraded": downgraded,
        "disabled": disabled,
        "added_names": {a["name"] for a in added},
    }


def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return

    if data.get("tool_name") != "Bash":
        return

    cwd = data.get("cwd") or os.getcwd()
    if not (Path(cwd) / ".osengineer" / "state.yml").exists():
        return

    cmd = data.get("tool_input", {}).get("command") or ""
    if not cmd:
        return

    repo_root = find_osengineer_root(cwd) or Path(cwd)

    if os.environ.get("OSE_BYPASS") == "1":
        bypass_log(repo_root, "pre-bash-guard", "OSE_BYPASS=1")
        return

    globals_ = load_patterns()
    repo_ov_path = Path(repo_root) / ".osengineer" / "denylist-overrides.json"
    repo_ov = load_override_file(repo_root, repo_ov_path, "repo")

    state = read_state_map(repo_root)
    current_team = state.get("current_team") if state else None
    team_ov = None
    if current_team:
        team_ov_path = Path(repo_root) / ".osengineer" / "teams" / current_team / "denylist-overrides.json"
        team_ov = load_override_file(repo_root, team_ov_path, "team:" + current_team)

    effective = build_effective_denylist(globals_, repo_ov, team_ov)

    if effective["disabled"]:
        for name in effective["disabled"]:
            global_pat = next((p for p in globals_ if p["name"] == name), None)
            if global_pat and re.search(global_pat["regex"], cmd):
                log_override(repo_root, {"event": "disabled_applied", "pattern": name, "team": current_team, "cmd": cmd[:200]})

    matched = None
    for p in effective["patterns"]:
        if re.search(p["regex"], cmd):
            matched = p
            break

    if not matched:
        return

    if matched["name"] in effective["added_names"]:
        log_override(repo_root, {"event": "added_pattern_matched", "pattern": matched["name"], "team": current_team, "cmd": cmd[:200]})

    if has_four_part_plan(repo_root):
        return

    if matched["name"] in effective["downgraded"]:
        log_override(repo_root, {"event": "downgraded_to_warning", "pattern": matched["name"], "team": current_team, "cmd": cmd[:200]})
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": (
                    f'osEngineer warning: command matches denylist pattern "{matched["name"]}"'
                    + (f' (category: {matched.get("category")})' if matched.get("category") else "")
                    + ". This pattern is downgraded-to-warning by a per-team override; the command will run but the match was logged to override-log.jsonl."
                ),
            },
        }))
        return

    print(json.dumps({
        "decision": "block",
        "reason": (
            f'osEngineer: command matches denylist pattern "{matched["name"]}"'
            + (f' (category: {matched.get("category")})' if matched.get("category") else "")
            + " and no 4-part plan is active.\n"
            + "Either:\n"
            + "  (a) write .osengineer/current-plan.md with sections Touch / Change / Impact / Rollback, or\n"
            + "  (b) set OSE_BYPASS=1 if absolutely necessary (logged to bypass-log.jsonl).\n"
            + "See trust/denylist.md for the full pattern contract and rationale."
        ),
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
