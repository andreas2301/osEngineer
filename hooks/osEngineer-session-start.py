#!/usr/bin/env python3
# osEngineer-session-start.py — Claude SessionStart hook.
#
# Loads .osengineer/state.yml on session start and emits a banner showing
# phase / team / budget / open handoffs / auto-nudge (if 5+ phases since
# last evolution).

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from osengineer_common import count_handoffs, emit_context, find_osengineer_root, is_repo_profile, profile_setting, read_state_map, fail_strict, read_payload


def read_evolution_counter(repo_root):
    p = Path(repo_root) / ".osengineer" / "evolution-counter.yml"
    if not p.exists():
        return None
    try:
        m = re.search(r"^phases_since_last_evolution:\s*(\d+)", p.read_text(), re.MULTILINE)
        return int(m.group(1)) if m else None
    except Exception:
        return None


def main():
    data = read_payload()
    cwd = data.get("cwd") or os.getcwd()
    repo_root = find_osengineer_root(cwd)
    if not repo_root:
        return

    state = read_state_map(repo_root)
    if not state:
        return

    handoffs = count_handoffs(repo_root)
    counter = read_evolution_counter(repo_root)

    repo_profile = is_repo_profile(repo_root)
    lines = ["## Repo profile state" if repo_profile else "## osEngineer state"]
    lines.append(f"- phase: {state.get('phase') or 'idle'}")
    if state.get("current_team"):
        lines.append(f"- team: {state['current_team']}")
    if state.get("budget_used") is not None:
        lines.append(f"- budget used: {state['budget_used']}%")
    if state.get("context_used_pct") is not None:
        lines.append(f"- context window used: {state['context_used_pct']}% (not task spend)")
    if handoffs > 0:
        lines.append(f"- open handoffs: {handoffs}")
    if repo_profile:
        lines.append(f"- policy: {profile_setting(repo_root, 'policy')}; plan references: {profile_setting(repo_root, 'planDirectory')}/; "
                     f"skill registry: {profile_setting(repo_root, 'skillRegistry')}")
    if not repo_profile and counter is not None and counter >= 5:
        lines.append(f"- ⚙ {counter} phases since last /osEngineer:evolve — consider running it to surface improvement proposals.")
    if state.get("phase") == "blocked":
        lines.append("- ⚠ phase is BLOCKED. See .osengineer/BLOCKED.md for resume instructions.")

    emit_context("SessionStart", "\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Strict: a malformed payload or any hook fault blocks (exit 2).
        fail_strict(Path(__file__).name, 'SessionStart', exc)
