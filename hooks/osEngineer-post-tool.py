#!/usr/bin/env python3
# osEngineer-post-tool.py — Claude PostToolUse hook.
#
# 1. Budget circuit breaker (trust/circuit-breakers.md, hooks/lib/osengineer_budget.py).
#    While the phase is execute/micro/hotfix and one valid active PHASE_PLAN.md
#    exists, every tool call adds 1 to budget_tool_calls and the gap since the
#    previous call (up to budget.idleSeconds) to budget_wall_seconds in the
#    gitignored .osengineer/runtime.yml; tokens are added from the Claude Code
#    transcript when readable (recorded, not enforced). At budget.warnPct (100)
#    of the summed task budgets it warns once; at budget.tripPct (150) it writes
#    .osengineer/BLOCKED.md and sets phase=blocked, after which the pre-edit and
#    pre-bash guards refuse edits and Bash. An invalid plan fails closed (exit 2).
# 2. Context telemetry, which describes window occupancy, not task spend:
#    records `context_used_pct` (runtime.yml) from the statusline bridge file
#    and surfaces context warning/critical transitions.
#
# Wired for Claude Code only: Kimi and Codex get no PostToolUse hook, so their
# interactive sessions are not metered (headless `osengineer run` meters wall
# time for every harness).

import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from osengineer_common import emit_context, find_osengineer_root, is_repo_profile, load_profile, planning_dir, write_state_field, fail_strict, read_payload
import osengineer_budget

STDIN_TIMEOUT_MS = 10000


def main():
    data = read_payload()

    cwd = data.get("cwd") or os.getcwd()
    repo_root = find_osengineer_root(cwd)
    if not repo_root:
        return

    messages = [budget_message(data, repo_root), context_message(data, repo_root)]
    messages = [m for m in messages if m]
    if messages:
        emit_context("PostToolUse", "\n\n".join(messages))


def budget_message(data, repo_root):
    active = osengineer_budget.active_budget(repo_root)
    if active is None:
        return None
    plan_path, plan, estimate = active
    transcript = data.get("transcript_path")
    usage = osengineer_budget.account(
        repo_root, plan, estimate, tool_call=True,
        transcript_path=transcript if isinstance(transcript, str) and transcript else None)
    return osengineer_budget.check(repo_root, plan_path, plan, estimate, usage, "post-tool hook")


def context_message(data, repo_root):
    session_id = data.get("session_id")
    if not isinstance(session_id, str) or not session_id or re.search(r"[/\\]|\.\.", session_id):
        return None

    metrics_path = Path(tempfile.gettempdir()) / f"claude-ctx-{session_id}.json"
    if not metrics_path.exists():
        return None
    # Thresholds are percent remaining, shared with prompt-guard (profile.json `context`).
    context = load_profile(repo_root)["context"]

    try:
        metrics = json.loads(metrics_path.read_text())
    except Exception as exc:
        raise ValueError("invalid context telemetry") from exc

    if metrics.get("session_id") not in (None, session_id):
        raise ValueError("context telemetry session mismatch")

    now = int(time.time())
    if metrics.get("timestamp") and (now - metrics["timestamp"]) > context["staleSeconds"]:
        return None

    remaining = metrics.get("remaining_percentage")
    used_pct = metrics.get("used_pct")

    if used_pct is not None:
        # Both profiles: volatile, gitignored runtime.yml. Never the repo
        # profile's <planDirectory>/osengineer/, the runtime's evidence namespace.
        write_state_field(repo_root, "context_used_pct", used_pct)

    warn_path = Path(tempfile.gettempdir()) / f"claude-ctx-{session_id}-ose-warned.json"
    if remaining is None:
        return None
    if remaining > context["warnPct"]:
        warn_path.unlink(missing_ok=True)
        return None

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
    is_critical = remaining <= context["criticalPct"]
    current_level = "critical" if is_critical else "warning"
    escalated = current_level == "critical" and warn_data.get("lastLevel") == "warning"

    if not first_warn and not escalated:
        try:
            warn_path.write_text(json.dumps(warn_data))
        except Exception as exc:
            raise RuntimeError("cannot load or persist warning state") from exc
        return None

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

    return message


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Strict: a malformed payload or any hook fault blocks (exit 2).
        fail_strict(Path(__file__).name, 'PostToolUse', exc)
