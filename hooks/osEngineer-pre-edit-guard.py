#!/usr/bin/env python3
# osEngineer-pre-edit-guard.py — Claude PreToolUse hook on Write/Edit.
#
# Blocks edits during `discuss`/`plan` phases (planning is read-only by design).
# Blocks edits to the configured live system at all times.
# Blocks edits to paths outside the current team's owns_paths when in `execute`
# phase with a `current_team` set.
#
# Reads:
#   .osengineer/state.yml          — phase + current_team
#   .osengineer/teams/<id>.json    — current team's owns_paths globs
#
# Honours OSE_BYPASS=1.

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from osengineer_common import (
    emit_json,
    find_osengineer_root,
    path_matches_any,
    read_state_map,
    read_team_cache,
    read_workbench_field,
)


def main():
    if os.environ.get("OSE_BYPASS") == "1":
        return

    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return

    tool = (data.get("tool_name") or "").lower()
    is_edit_tool = any(t in tool for t in ("write", "edit", "replace"))
    if not is_edit_tool:
        return

    cwd = data.get("cwd") or os.getcwd()
    file_path = (
        data.get("tool_input", {}).get("file_path")
        or data.get("tool_input", {}).get("path")
        or data.get("tool_input", {}).get("TargetFile")
        or data.get("tool_input", {}).get("AbsolutePath")
        or ""
    )

    live_system = read_workbench_field(cwd, "live_system_path")
    if live_system and live_system not in ("none", ""):
        if live_system in file_path or file_path.startswith(live_system):
            emit_json({
                "decision": "block",
                "reason": f"osEngineer: edits to {live_system} are forbidden — that path is the live system. Edit in workbench and deploy via normal project workflow. Bypass with OSE_BYPASS=1 if absolutely necessary.",
            })
            return

    repo_root = find_osengineer_root(cwd)
    if not repo_root:
        return

    state = read_state_map(repo_root)
    if not state:
        return

    profile = read_workbench_field(cwd, "validation_profile") or "hybrid"
    try:
        rel = str(Path(file_path).resolve().relative_to(repo_root))
    except Exception:
        rel = file_path
    rel = rel.replace("\\", "/")

    if profile == "infra" and not re.match(r"^(planning|\.osengineer|ansible|docker|scripts)[/\\]", rel) and (rel.endswith(".yml") or rel.endswith(".yaml") or rel.endswith(".json")):
        if state.get("phase") in ("discuss", "plan"):
            emit_json({
                "decision": "block",
                "reason": f"osEngineer: [Infra Profile] Editing configuration file {rel} is forbidden during {state['phase']} phase to prevent configuration drift. Focus on playbooks/scripts in planning directories first.",
            })
            return

    if profile == "frontend" and ("assets/" in rel or rel.endswith((".png", ".jpg", ".svg"))):
        if state.get("phase") == "execute" and not state.get("current_team"):
            emit_json({
                "decision": "block",
                "reason": f"osEngineer: [Frontend Profile] Editing visual asset {rel} requires an active team context (e.g., UI/UX designer) to ensure design system consistency. Set current team first.",
            })
            return

    if state.get("phase") in ("discuss", "plan"):
        if not re.match(r"^(planning|\.osengineer)[/\\]", rel):
            emit_json({
                "decision": "block",
                "reason": f"osEngineer: cannot edit {Path(file_path).name} during {state['phase']} phase — only planning/ and .osengineer/ artifacts are editable. Transition to execute phase first (`osengineer state set phase execute`).",
            })
            return

    if state.get("phase") in ("execute", "micro", "hotfix") and state.get("current_team"):
        team = read_team_cache(repo_root, state["current_team"])
        owns = team and team.get("owns_paths")
        if owns:
            is_state_artifact = re.match(r"^(planning|\.osengineer)[/\\]", rel)
            if not is_state_artifact and not path_matches_any(rel, owns):
                emit_json({
                    "decision": "block",
                    "reason": f'osEngineer: {rel} is outside team "{state["current_team"]}"\'s owns_paths. Either (a) open a handoff to the right team — `osengineer handoff open --from {state["current_team"]} --to <team> --slug <s>` — or (b) bypass with OSE_BYPASS=1 if absolutely necessary.',
                })
                return


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
