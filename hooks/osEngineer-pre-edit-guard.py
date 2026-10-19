#!/usr/bin/env python3
# osEngineer-pre-edit-guard.py — Claude PreToolUse hook on Write/Edit.
#
# Blocks edits during `discuss`/`plan` phases (planning is read-only by design).
# Blocks edits to the configured live system at all times.
# Blocks the agent authoring .osengineer/current-plan.md (self-authorisation guard).
# Blocks non-plan edits in `execute` while the active PHASE_PLAN.md is invalid.
# Blocks edits to .osengineer/state.yml and approvals.jsonl in every phase —
# only `osengineer approve`, run by a human, changes the phase.
# Blocks edits to paths outside the current team's owns_paths when in `execute`
# phase with a `current_team` set.
#
# Reads:
#   .osengineer/state.yml          — phase + current_team
#   .osengineer/teams/<id>.json    — current team's owns_paths globs
#
# Honours OSE_BYPASS=1, except for the state files (refused and logged).

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from osengineer_common import (
    fail_strict,
    read_payload,
    emit_block,
    bypass_log,
    is_repo_profile,
    planning_dir,
    find_osengineer_root,
    path_matches_any,
    read_state_map,
    read_team_cache,
    read_workbench_field,
)
from repo_profile import phase_plan
import phase_gate


def main():
    data = read_payload()

    tool = (data.get("tool_name") or "").lower()
    is_edit_tool = any(t in tool for t in ("write", "edit", "replace"))
    if not is_edit_tool:
        return

    cwd = data.get("cwd") or os.getcwd()
    repo_root = find_osengineer_root(cwd)
    file_path = (
        data.get("tool_input", {}).get("file_path")
        or data.get("tool_input", {}).get("path")
        or data.get("tool_input", {}).get("TargetFile")
        or data.get("tool_input", {}).get("AbsolutePath")
        or ""
    )

    if repo_root:
        target = Path(file_path)
        if not target.is_absolute():
            target = Path(cwd) / target
        protected = {(Path(repo_root) / ".osengineer" / f).resolve() for f in phase_gate.PROTECTED_FILES}
        if target.resolve() in protected:
            if os.environ.get("OSE_BYPASS") == "1":
                bypass_log(repo_root, "pre-edit-guard", "OSE_BYPASS=1 not honoured for phase approval")
            emit_block("PreToolUse", f"osEngineer: refusing to edit .osengineer/{target.name}. " + phase_gate.REFUSAL)
            return

    if repo_root and os.environ.get("OSE_BYPASS") == "1":
        bypass_log(repo_root, "pre-edit-guard", "OSE_BYPASS=1")
        return

    if repo_root:
        # The 4-part plan is the human authorisation for denylisted commands;
        # the constrained agent must never be able to author it.
        target = Path(file_path)
        if not target.is_absolute():
            target = Path(repo_root) / target
        if target.resolve() == (Path(repo_root) / ".osengineer" / "current-plan.md").resolve():
            emit_block(
                "PreToolUse",
                "osEngineer: refusing to write .osengineer/current-plan.md — the 4-part plan is the human authorisation for denylisted commands, so the agent may not author it. Ask a human to create it, or set OSE_BYPASS=1 in the hook environment.",
            )
            return

    live_system = read_workbench_field(cwd, "live_system_path")
    if live_system and live_system not in ("none", ""):
        if live_system in file_path or file_path.startswith(live_system):
            emit_block(
                "PreToolUse",
                f"osEngineer: edits to {live_system} are forbidden — that path is the live system. Edit in workbench and deploy via normal project workflow. Bypass with OSE_BYPASS=1 if absolutely necessary.",
            )
            return

    if not repo_root:
        return

    state = read_state_map(repo_root)
    if not state:
        return

    profile = read_workbench_field(cwd, "validation_profile") or "hybrid"
    planning_name = planning_dir(repo_root).relative_to(repo_root).as_posix()
    artifact_pattern = r"^(" + re.escape(planning_name) + r"|\.osengineer)[/\\]"
    if state.get("phase") in ("blocked", "suspended"):
        emit_block("PreToolUse", f"osEngineer: edits denied while phase is {state['phase']}. Resume explicitly first.")
        return

    try:
        target = Path(file_path)
        if not target.is_absolute():
            target = Path(cwd) / target
        rel = str(target.resolve().relative_to(repo_root))
    except Exception:
        rel = file_path
    rel = rel.replace("\\", "/")

    if profile == "infra" and not re.match(r"^(planning|\.osengineer|ansible|docker|scripts)[/\\]", rel) and (rel.endswith(".yml") or rel.endswith(".yaml") or rel.endswith(".json")):
        if state.get("phase") in ("discuss", "plan"):
            emit_block(
                "PreToolUse",
                f"osEngineer: [Infra Profile] Editing configuration file {rel} is forbidden during {state['phase']} phase to prevent configuration drift. Focus on playbooks/scripts in planning directories first.",
            )
            return

    if profile == "frontend" and ("assets/" in rel or rel.endswith((".png", ".jpg", ".svg"))):
        if state.get("phase") == "execute" and not state.get("current_team"):
            emit_block(
                "PreToolUse",
                f"osEngineer: [Frontend Profile] Editing visual asset {rel} requires an active team context (e.g., UI/UX designer) to ensure design system consistency. Set current team first.",
            )
            return

    if state.get("phase") in ("discuss", "plan"):
        if not re.match(artifact_pattern, rel):
            emit_block(
                "PreToolUse",
                f"osEngineer: cannot edit {Path(file_path).name} during {state['phase']} phase — only {planning_name}/ and .osengineer/ artifacts are editable. Ask the human to approve the move to execute (they run `osengineer approve execute`; you cannot).",
            )
            return

    # Execution runs against the plan it was approved with: an active
    # PHASE_PLAN.md must validate (its task budgets feed the circuit breaker).
    # The plan itself and .osengineer/ stay editable so it can be fixed.
    if state.get("phase") == "execute" and not re.match(artifact_pattern, rel):
        try:
            phase_plan.load_active(planning_dir(repo_root))
        except phase_plan.PlanError as exc:
            emit_block("PreToolUse", f"osEngineer: edits denied in execute — invalid PHASE_PLAN.md: {exc}")
            return

    # Repo profile scope is owned by the repository policy/dispatch contract.
    # The legacy team cache must not become a second scope authority.
    if not is_repo_profile(repo_root) and state.get("phase") in ("execute", "micro", "hotfix") and state.get("current_team"):
        team = read_team_cache(repo_root, state["current_team"])
        owns = team.get("owns_paths") if isinstance(team, dict) else None
        if not isinstance(owns, list) or not owns or not all(isinstance(pattern, str) and pattern for pattern in owns):
            emit_block("PreToolUse", f"osEngineer: team configuration fault for {state['current_team']}: valid nonempty owns_paths are required.")
            return
        if owns:
            is_state_artifact = re.match(artifact_pattern, rel)
            if not is_state_artifact and not path_matches_any(rel, owns):
                emit_block(
                    "PreToolUse",
                    f'osEngineer: {rel} is outside team "{state["current_team"]}"\'s owns_paths. Either (a) open a handoff to the right team — `osengineer handoff open --from {state["current_team"]} --to <team> --slug <s>` — or (b) bypass with OSE_BYPASS=1 if absolutely necessary.',
                )
                return


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Strict: a malformed payload or any hook fault blocks (exit 2).
        fail_strict(Path(__file__).name, 'PreToolUse', exc)
