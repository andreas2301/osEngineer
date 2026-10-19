#!/usr/bin/env python3
# osengineer_budget.py — the budget circuit breaker (trust/circuit-breakers.md).
#
# Shared by the post-tool hook (one tool call at a time) and `osengineer run`
# (wall time of a headless run). Usage is kept per phase_id in the gitignored
# .osengineer/runtime.yml as budget_* fields and compared with the active
# PHASE_PLAN.md task budgets summed (repo_profile/phase_plan.py).

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from osengineer_common import (
    is_repo_profile,
    load_profile,
    planning_dir,
    read_state_map,
    update_state_fields,
)
from repo_profile import phase_plan

# Phases that spend budget. discuss/plan author the plan; blocked has stopped.
SPENDING_PHASES = ("execute", "micro", "hotfix")
BLOCKED_REL = ".osengineer/BLOCKED.md"


def active_budget(repo_root):
    """(plan_path, plan, estimate) while a generic-profile phase spends budget, else None.

    An invalid or ambiguous active plan raises PlanError (callers fail closed).
    """
    if is_repo_profile(repo_root):
        return None
    state = read_state_map(repo_root) or {}
    if state.get("phase") not in SPENDING_PHASES:
        return None
    found = phase_plan.load_active(planning_dir(repo_root))
    if found is None:
        return None
    path, plan = found
    return path, plan, phase_plan.estimate(plan)


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def ratio_pct(tool_calls, wall_seconds, estimate):
    """Percent used: the larger of the tool-call and wall-time ratios."""
    calls = tool_calls / estimate["tool_calls"]
    wall = wall_seconds / (estimate["wall_minutes"] * 60)
    return int(max(calls, wall) * 100 + 1e-9)


def transcript_tokens(path, offset, last_id):
    """New (tokens, offset, last_id) from a Claude Code transcript JSONL, or None.

    Sums input + cache creation + cache read + output tokens of assistant
    messages, counting each message id once. The format is not a documented
    contract and the file may lag the session, so tokens are recorded only.
    """
    try:
        p = Path(path)
        if not p.is_file():
            return None
        size = p.stat().st_size
        if offset > size:
            offset = 0
        with p.open("rb") as f:
            f.seek(offset)
            chunk = f.read()
    except (OSError, TypeError, ValueError):
        return None
    end = chunk.rfind(b"\n") + 1  # only complete lines; a partial one is read next time
    tokens = 0
    for raw in chunk[:end].splitlines():
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        msg = row.get("message") if isinstance(row, dict) and row.get("type") == "assistant" else None
        usage = msg.get("usage") if isinstance(msg, dict) else None
        if not isinstance(usage, dict) or msg.get("id") == last_id:
            continue
        last_id = msg.get("id")
        for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"):
            if type(usage.get(key)) is int:
                tokens += usage[key]
    return tokens, offset + end, last_id


def account(repo_root, plan, estimate, *, tool_call=False, wall_seconds=0.0,
            now=None, transcript_path=None):
    """Add one tool call and/or wall seconds to the phase usage; return the usage."""
    idle = load_profile(repo_root)["budget"]["idleSeconds"]
    now = time.time() if now is None else now

    def bump(cur):
        if cur.get("budget_phase") != plan["phase_id"]:
            # A new phase starts from zero; the transcript read position carries
            # over so an earlier phase's tokens are not counted again.
            keep = ("budget_transcript", "budget_transcript_offset", "budget_last_message")
            cur = {"budget_warned": "0", **{k: cur[k] for k in keep if k in cur}}
        calls = int(_num(cur.get("budget_tool_calls")))
        wall = _num(cur.get("budget_wall_seconds")) + wall_seconds
        updates = {"budget_phase": plan["phase_id"]}
        if tool_call:
            calls += 1
            last = cur.get("budget_last_ts")
            if last is not None and 0 <= now - _num(last) <= idle:
                wall += now - _num(last)
            updates["budget_last_ts"] = f"{now:.3f}"
        tokens = cur.get("budget_tokens")
        if transcript_path:
            same = cur.get("budget_transcript") == transcript_path
            got = transcript_tokens(transcript_path,
                                    int(_num(cur.get("budget_transcript_offset"))) if same else 0,
                                    cur.get("budget_last_message") if same else None)
            if got is not None:
                tokens = int(_num(tokens)) + got[0]
                updates.update(budget_transcript=transcript_path, budget_transcript_offset=got[1],
                               budget_last_message=got[2] or "null", budget_tokens=tokens)
        updates.update(budget_tool_calls=calls, budget_wall_seconds=f"{wall:.1f}",
                       budget_ratio_pct=ratio_pct(calls, wall, estimate),
                       budget_warned=cur.get("budget_warned") or "0")
        if tokens is not None:
            updates["budget_tokens"] = tokens
        return updates

    return update_state_fields(repo_root, bump)


def evidence(usage, estimate):
    calls, wall = int(usage["budget_tool_calls"]), float(usage["budget_wall_seconds"])
    lines = [
        f"- tool calls: {calls} / {estimate['tool_calls']} ({int(calls * 100 / estimate['tool_calls'])}%)",
        f"- wall time: {wall / 60:.1f} / {estimate['wall_minutes']} min "
        f"({int(wall * 100 / (estimate['wall_minutes'] * 60))}%)",
    ]
    if usage.get("budget_tokens") is not None:
        est = estimate["tokens"]
        lines.append(f"- tokens: {usage['budget_tokens']}"
                     + (f" / {est} (recorded only, not enforced)" if est else " (no estimate; recorded only)"))
    return lines


def check(repo_root, plan_path, plan, estimate, usage, source):
    """Apply the warn/trip thresholds to fresh usage; return a message or None.

    Tripping is the one automatic transition into `blocked`: it writes
    .osengineer/BLOCKED.md and sets phase=blocked (blocked_from keeps the phase
    to resume). Leaving `blocked` is a human decision.
    """
    cfg = load_profile(repo_root)["budget"]
    pct = int(usage["budget_ratio_pct"])
    if pct >= cfg["tripPct"]:
        state = read_state_map(repo_root) or {}
        if state.get("phase") == "blocked":
            return None
        rel = Path(plan_path).relative_to(repo_root).as_posix()
        body = "\n".join([
            "# BLOCKED — budget circuit breaker tripped",
            "",
            f"- phase: {plan['phase_id']} ({rel})",
            f"- tripped: {datetime.now(timezone.utc).isoformat()} by {source}",
            f"- threshold: {pct}% used >= budget.tripPct {cfg['tripPct']}%",
            f"- phase before block: {state.get('phase')}",
            *evidence(usage, estimate),
            "",
            "Edits and Bash are refused while phase is blocked. A human decides:",
            "",
            "- continue with more budget: raise the task budgets in the PHASE_PLAN.md, then approve;",
            "- split the task into a new phase, or abandon it.",
            "",
            "Leaving `blocked` needs a human: `osengineer approve` where it exists, otherwise",
            f"`osengineer state set phase {state.get('phase')}` run by the human outside the agent session.",
            "If usage is still at or above budget.tripPct the breaker trips again on the next tool call.",
            "",
        ])
        (Path(repo_root) / BLOCKED_REL).write_text(body)
        update_state_fields(repo_root, lambda _cur: {"phase": "blocked", "blocked_from": state.get("phase")})
        return (f"osEngineer CIRCUIT BREAKER TRIPPED: {plan['phase_id']} used {pct}% of its budget "
                f"(trip at {cfg['tripPct']}%). Phase is now blocked; STOP. Edits and Bash are refused until a "
                f"human approves. Evidence: {BLOCKED_REL}.")
    if pct >= cfg["warnPct"] and usage.get("budget_warned") != "1":
        update_state_fields(repo_root, lambda _cur: {"budget_warned": "1"})
        return (f"osEngineer BUDGET WARNING: {plan['phase_id']} used {pct}% of its budget "
                f"({'; '.join(l[2:] for l in evidence(usage, estimate))}). "
                f"The circuit breaker trips at {cfg['tripPct']}%; finish or checkpoint the current task.")
    return None
