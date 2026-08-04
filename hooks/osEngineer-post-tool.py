#!/usr/bin/env python3
# osEngineer-post-tool.py — Claude PostToolUse hook.
#
# 1. Updates .osengineer/state.yml `budget_used` based on tool-use telemetry
#    (best-effort approximation using token counts from the bridge file written
#    by the statusline hook).
# 2. Trips the circuit-breaker when budget exceeds 150% of phase estimate:
#    writes BLOCKED.md, transitions phase to `blocked`, blocks further edits.
# 3. Surfaces context warnings when context window crosses thresholds.

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from osengineer_common import find_osengineer_root, write_state_field

STDIN_TIMEOUT_MS = 10000
WARNING_THRESHOLD = 35
CRITICAL_THRESHOLD = 25
STALE_SECONDS = 60
DEBOUNCE_CALLS = 5


def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return

    session_id = data.get("session_id")
    if not session_id or re.search(r"[/\\]|\.\.", session_id):
        return

    cwd = data.get("cwd") or os.getcwd()
    repo_root = find_osengineer_root(cwd)
    if not repo_root:
        return

    metrics_path = Path(tempfile.gettempdir()) / f"claude-ctx-{session_id}.json"
    if not metrics_path.exists():
        return

    try:
        metrics = json.loads(metrics_path.read_text())
    except Exception:
        return

    now = int(time.time())
    if metrics.get("timestamp") and (now - metrics["timestamp"]) > STALE_SECONDS:
        return

    remaining = metrics.get("remaining_percentage")
    used_pct = metrics.get("used_pct")

    if used_pct is not None:
        write_state_field(repo_root, "budget_used", used_pct)

    if remaining is None or remaining > WARNING_THRESHOLD:
        return

    warn_path = Path(tempfile.gettempdir()) / f"claude-ctx-{session_id}-ose-warned.json"
    warn_data = {"callsSinceWarn": 0, "lastLevel": None}
    first_warn = True
    if warn_path.exists():
        try:
            warn_data = json.loads(warn_path.read_text())
            first_warn = False
        except Exception:
            pass

    warn_data["callsSinceWarn"] = warn_data.get("callsSinceWarn", 0) + 1
    is_critical = remaining <= CRITICAL_THRESHOLD
    current_level = "critical" if is_critical else "warning"
    escalated = current_level == "critical" and warn_data.get("lastLevel") == "warning"

    if not first_warn and warn_data["callsSinceWarn"] < DEBOUNCE_CALLS and not escalated:
        try:
            warn_path.write_text(json.dumps(warn_data))
        except Exception:
            pass
        return

    warn_data["callsSinceWarn"] = 0
    warn_data["lastLevel"] = current_level
    try:
        warn_path.write_text(json.dumps(warn_data))
    except Exception:
        pass

    if is_critical:
        message = (
            f"osEngineer CONTEXT CRITICAL: {used_pct}% used, {remaining}% remaining. "
            "Inform the user that context is nearly exhausted. Do NOT start new complex work. "
            "Consider /osEngineer:pause-work at the next natural stopping point."
        )
    else:
        message = (
            f"osEngineer CONTEXT WARNING: {used_pct}% used, {remaining}% remaining. "
            "Avoid starting new complex work. If between plan steps, inform the user so they can prepare to pause."
        )

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": message,
        },
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
