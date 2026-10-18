#!/usr/bin/env python3
# osEngineer-post-tool.py — Claude PostToolUse hook.
#
# Context telemetry describes window occupancy, not task token spend.
# 1. Records `context_used_pct` (in the gitignored .osengineer/runtime.yml) from
#    the bridge file written by the statusline hook.
# 2. Surfaces context warning/critical transitions. It implements no budget
#    circuit-breaker.

import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from osengineer_common import emit_context, find_osengineer_root, is_repo_profile, planning_dir, write_state_field, fail_strict, read_payload

STDIN_TIMEOUT_MS = 10000
WARNING_THRESHOLD = 35
CRITICAL_THRESHOLD = 25
STALE_SECONDS = 60


def main():
    data = read_payload()

    session_id = data.get("session_id")
    if not isinstance(session_id, str) or not session_id or re.search(r"[/\\]|\.\.", session_id):
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
    except Exception as exc:
        raise ValueError("invalid context telemetry") from exc

    if metrics.get("session_id") not in (None, session_id):
        raise ValueError("context telemetry session mismatch")

    now = int(time.time())
    if metrics.get("timestamp") and (now - metrics["timestamp"]) > STALE_SECONDS:
        return

    remaining = metrics.get("remaining_percentage")
    used_pct = metrics.get("used_pct")

    if used_pct is not None:
        # Both profiles: volatile, gitignored runtime.yml. Never the repo
        # profile's <planDirectory>/osengineer/, the runtime's evidence namespace.
        write_state_field(repo_root, "context_used_pct", used_pct)

    warn_path = Path(tempfile.gettempdir()) / f"claude-ctx-{session_id}-ose-warned.json"
    if remaining is None:
        return
    if remaining > WARNING_THRESHOLD:
        warn_path.unlink(missing_ok=True)
        return

    warn_path = Path(tempfile.gettempdir()) / f"claude-ctx-{session_id}-ose-warned.json"
    warn_data = {"callsSinceWarn": 0, "lastLevel": None}
    first_warn = True
    if warn_path.exists():
        try:
            warn_data = json.loads(warn_path.read_text())
            first_warn = False
        except Exception as exc:
            raise RuntimeError("cannot load or persist warning state") from exc

    warn_data["callsSinceWarn"] = warn_data.get("callsSinceWarn", 0) + 1
    is_critical = remaining <= CRITICAL_THRESHOLD
    current_level = "critical" if is_critical else "warning"
    escalated = current_level == "critical" and warn_data.get("lastLevel") == "warning"

    if not first_warn and not escalated:
        try:
            warn_path.write_text(json.dumps(warn_data))
        except Exception as exc:
            raise RuntimeError("cannot load or persist warning state") from exc
        return

    warn_data["callsSinceWarn"] = 0
    warn_data["lastLevel"] = current_level
    try:
        warn_path.write_text(json.dumps(warn_data))
    except Exception as exc:
        raise RuntimeError("cannot load or persist warning state") from exc

    if is_repo_profile(repo_root):
        message = (f"Repo profile context {current_level}: {remaining}% remaining. "
                   f"Checkpoint the active task under {planning_dir(repo_root).name}/; load only the next required references.")
    elif is_critical:
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

    emit_context("PostToolUse", message)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Strict: a malformed payload or any hook fault blocks (exit 2).
        fail_strict(Path(__file__).name, 'PostToolUse', exc)
