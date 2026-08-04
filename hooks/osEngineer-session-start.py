#!/usr/bin/env python3
# osEngineer-session-start.py — Claude SessionStart hook.
#
# Loads .osengineer/state.yml on session start and emits a banner showing
# phase / team / budget / open handoffs / auto-nudge (if 5+ phases since
# last evolution).

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from osengineer_common import count_handoffs, find_osengineer_root, read_state_map


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
    cwd = os.getcwd()
    repo_root = find_osengineer_root(cwd)
    if not repo_root:
        return

    state = read_state_map(repo_root)
    if not state:
        return

    handoffs = count_handoffs(repo_root)
    counter = read_evolution_counter(repo_root)

    lines = ["## osEngineer state"]
    lines.append(f"- phase: {state.get('phase') or 'idle'}")
    if state.get("current_team"):
        lines.append(f"- team: {state['current_team']}")
    if state.get("budget_used") is not None:
        lines.append(f"- budget used: {state['budget_used']}%")
    if handoffs > 0:
        lines.append(f"- open handoffs: {handoffs}")
    if counter is not None and counter >= 5:
        lines.append(f"- ⚙ {counter} phases since last /osEngineer:evolve — consider running it to surface improvement proposals.")
    if state.get("phase") == "blocked":
        lines.append("- ⚠ phase is BLOCKED. See .osengineer/BLOCKED.md for resume instructions.")

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines),
        },
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
