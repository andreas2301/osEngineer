#!/usr/bin/env python3
# osEngineer-statusline.py — Claude statusline hook.
# Shows: model · phase · team · budget% · open-handoffs · cwd-name · context-meter
#
# Also writes context metrics to /tmp/claude-ctx-{session_id}.json which the
# osEngineer-post-tool hook reads for warning injection.

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from osengineer_common import count_handoffs, find_osengineer_root, read_state_map


def format_state_segment(state, handoffs):
    parts = [f"phase:{state.get('phase') or 'idle'}"]
    if state.get("current_team"):
        parts.append(f"team:{state['current_team']}")
    if state.get("budget_used") is not None:
        parts.append(f"b:{state['budget_used']}%")
    if handoffs > 0:
        parts.append(f"HO:{handoffs}")
    return " · ".join(parts)


def build_context_meter(remaining, session):
    if remaining is None:
        return ""
    total_ctx = 1_000_000
    acw = int(os.environ.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW") or "0")
    buf = min(100, (acw / total_ctx) * 100) if acw > 0 else 16.5
    usable_rem = max(0, ((remaining - buf) / (100 - buf)) * 100)
    used = max(0, min(100, round(100 - usable_rem)))

    if session and not re.search(r"[/\\]|\.\.", session):
        try:
            bridge_path = Path(tempfile.gettempdir()) / f"claude-ctx-{session}.json"
            bridge_path.write_text(json.dumps({
                "session_id": session,
                "remaining_percentage": remaining,
                "used_pct": round(100 - remaining),
                "timestamp": int(__import__("time").time()),
            }))
        except Exception:
            pass

    filled = used // 10
    bar = "█" * filled + "░" * (10 - filled)
    if used < 50:
        color = "\x1b[32m"
    elif used < 65:
        color = "\x1b[33m"
    elif used < 80:
        color = "\x1b[38;5;208m"
    else:
        color = "\x1b[5;31m💀 "
    return f" {color}{bar} {used}%\x1b[0m"


def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return

    model = (data.get("model") or {}).get("display_name") or "Claude"
    workspace = data.get("workspace") or {}
    cwd = workspace.get("current_dir") or os.getcwd()
    session = data.get("session_id") or ""
    remaining = (data.get("context_window") or {}).get("remaining_percentage")

    model_seg = f"\x1b[2m{model}\x1b[0m"
    dir_seg = f"\x1b[2m{Path(cwd).name}\x1b[0m"
    ctx = build_context_meter(remaining, session)

    repo_root = find_osengineer_root(cwd)
    state_seg = ""
    if repo_root:
        state = read_state_map(repo_root)
        if state:
            handoffs = count_handoffs(repo_root)
            state_seg = f" │ \x1b[2m{format_state_segment(state, handoffs)}\x1b[0m"

    print(f"{model_seg}{state_seg} │ {dir_seg}{ctx}", end="")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
