#!/usr/bin/env python3
# phase_gate.py — the human phase gate (planning/PROTOCOL.md).
#
# `osengineer approve <phase>` is the only way to change the phase. It checks
# TRANSITIONS and the target's prerequisite artifact, records who and when in
# state.yml and appends to .osengineer/approvals.jsonl. The guards use
# agent_route() and PROTECTED_FILES to refuse the agent every route to it.
# runtime.yml is protected too: it holds the circuit breaker's budget_*
# counters, which hooks write in code; an agent rewrite would reset its budget.
# So are the breaker's limit and off switch (CONFIG_FILES), and approve() records
# the budget it approves, so that raising one takes a human. The gate into
# execute is also where a producer's HANDOFF.json is read (family_handoff).

import getpass
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from osengineer_common import is_repo_profile, planning_dir, read_state_map, write_state_field
from repo_profile import family_handoff, phase_plan

# current phase -> phases a human may approve next. Discuss -> Plan -> Execute
# -> Verify -> Accepted is the main line; Blocked is reachable from every
# working phase and recovers to Discuss or Plan; micro/hotfix is the
# Micro-Phase, which upgrades to Plan when it outgrows its scope.
TRANSITIONS = {
    "idle": {"discuss", "micro", "hotfix"},
    "discuss": {"plan", "micro", "hotfix", "blocked"},
    "plan": {"execute", "discuss", "micro", "hotfix", "blocked"},
    "execute": {"verify", "blocked"},
    "verify": {"accepted", "execute", "blocked"},
    "accepted": {"idle", "discuss", "micro", "hotfix"},
    "blocked": {"discuss", "plan"},
    "suspended": {"discuss", "plan"},
    "micro": {"accepted", "idle", "plan", "blocked"},
    "hotfix": {"accepted", "idle", "plan", "blocked"},
}
PHASES = set(TRANSITIONS)
# Phases that spend budget. discuss/plan author the plan; blocked has stopped.
SPENDING_PHASES = ("execute", "micro", "hotfix")

# Written only by approve(); `state set` refuses them.
RECORD_FIELDS = ("phase_approved_by", "phase_approved_at", "phase_approved_budget")
# budget.tripPct and the profile switch that turns the meter off. Common file
# names, so the shell guard counts them only under .osengineer/.
CONFIG_FILES = ("profile.json", "workbench-config.yml")
PROTECTED_FILES = ("state.yml", "approvals.jsonl", "runtime.yml") + CONFIG_FILES
# The breaker's notice to the human; held only while the phase is blocked.
BLOCKED_FILE = "BLOCKED.md"


def required_artifact(current, target):
    """Artifact that must exist under <planning>/active/*/ for the move."""
    if target == "execute":
        return "PHASE_PLAN.md"
    if current in ("micro", "hotfix") and target in ("accepted", "idle"):
        return "MICRO_PLAN.md"
    if target == "accepted":
        return "VERIFICATION.md"
    return None


def active_handoff(repo_root):
    """The family-handoff record of the one active plan, or None. Raises HandoffError."""
    plans = sorted((planning_dir(repo_root) / "active").glob(f"*/{phase_plan.PLAN_NAME}"))
    return family_handoff.read(plans[0]) if len(plans) == 1 else None


def check(repo_root, current, target, reason=None):
    """None if the human may approve current -> target, else the reason. A plan
    that differs from the one handed off needs the human's own reason."""
    if target not in PHASES:
        return f"unknown phase {target!r}; phases: {', '.join(sorted(PHASES))}"
    if current not in TRANSITIONS:
        return (f"current phase {current!r} is not in the transition table; "
                "fix .osengineer/state.yml by hand")
    if target not in TRANSITIONS[current]:
        allowed = ", ".join(sorted(TRANSITIONS[current]))
        return f"{current} -> {target} is not an allowed transition (from {current}: {allowed})"
    artifact = required_artifact(current, target)
    if artifact:
        active = planning_dir(repo_root) / "active"
        if not list(active.glob(f"*/{artifact}")):
            rel = active.relative_to(repo_root).as_posix()
            return f"{current} -> {target} requires {rel}/<phase>/{artifact}"
    if target == "execute":
        try:
            handoff = active_handoff(repo_root)
        except family_handoff.HandoffError as exc:
            return str(exc)
        if handoff and handoff["plan_changed"] and not reason:
            return (f"the active plan is not the one handed off as {handoff['trace_id']}: "
                    'review the change, then approve with --reason "<text>"')
    return None


def approver(repo_root):
    try:
        email = subprocess.run(["git", "config", "user.email"], cwd=str(repo_root),
                               capture_output=True, text=True).stdout.strip()
    except OSError:
        email = ""
    return email or getpass.getuser()


def log_transition(repo_root, entry):
    """Append one phase change to .osengineer/approvals.jsonl, the single log
    of every transition (human approvals and the circuit breaker's trip)."""
    log = Path(repo_root) / ".osengineer" / "approvals.jsonl"
    with log.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def approved_budget(repo_root, target):
    """What this approval commits the phase to, or None without a valid plan.
    osengineer_budget.held_budget holds the phase to it."""
    if target not in SPENDING_PHASES or is_repo_profile(repo_root):
        return None
    try:
        found = phase_plan.load_active(planning_dir(repo_root))
    except phase_plan.PlanError:
        return None     # the gate checks presence; the guards refuse the plan in execute
    if found is None:
        return None
    path, plan = found
    return {"plan": path.relative_to(repo_root).as_posix(), "phase_id": plan["phase_id"],
            "estimate": phase_plan.estimate(plan)}


def approve(repo_root, target, reason=None):
    """Validate and apply one transition; returns the log entry. Raises
    ValueError with the refusal reason."""
    state = read_state_map(repo_root) or {}
    current = state.get("phase") or "idle"
    refusal = check(repo_root, current, target, reason)
    if refusal:
        raise ValueError(refusal)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "from": current,
        "to": target,
        "by": approver(repo_root),
    }
    if reason:
        entry["reason"] = reason
    budget = approved_budget(repo_root, target)
    if budget:
        entry["budget"] = budget
    handoff = active_handoff(repo_root) if target == "execute" else None
    if handoff:
        entry["handoff"] = handoff
    log_transition(repo_root, entry)
    write_state_field(repo_root, "phase", target)
    write_state_field(repo_root, "phase_approved_by", entry["by"])
    write_state_field(repo_root, "phase_approved_at", entry["ts"])
    if target in SPENDING_PHASES:
        write_state_field(repo_root, "phase_approved_budget", json.dumps(budget))
    return entry


# ── Agent routes (best effort; see planning/PROTOCOL.md "Phase gate") ───────

# osengineer in command position: segment start, a quote (bash -c "..."),
# or $( / backtick, then env assignments, wrappers or an interpreter.
_CLI_ROUTE = re.compile(
    r"(?:^|[;&|(`\n'\"]|\$\()\s*(?:\w+=\S*\s+)*"
    r"(?:(?:sudo|exec|env|command|nohup|time|eval)\s+)*(?:python\d*(?:\.\d+)?\s+)?"
    r"(?:\S*/)?osengineer\s+(?:approve|state\s+set\s+(?:phase|budget_|context_used_pct)\w*"
    r"|profile\s+(?:(?:un)?install|detect\b[^;|&\n]*--write))\b"
)
# The same writes from Python.
_STATE_CODE = re.compile(
    r"\b(?:write_state_field|update_state_fields|_rewrite_fields)\b"
    r"|-m\s+repo_profile\b[^;|&\n]*(?:\b(?:un)?install\b|--write\b)"
)
# The guards stand down in a repo without .osengineer/, a rewound state.yml forgets
# an approval, and a missing runtime.yml (gitignored, so git stash -a takes it)
# reads as no usage at all.
_STATE_WIPE = re.compile(
    r"\b(?:mv|rm|rsync|git\s+(?:\S+\s+)*(?:checkout|restore))\b"
    r"[^;|&\n]*\s['\"]?(?:\S*/)?\.osengineer/?['\"]?(?=$|[\s;|&])"
    r"|\bgit\s+(?:\S+\s+)*stash\b[^;|&\n]*\s(?:-a|--all)\b"
)


def _names(blocked):
    names = [re.escape(n) for n in PROTECTED_FILES if n not in CONFIG_FILES]
    names += [r"\.osengineer/" + re.escape(n) for n in CONFIG_FILES]
    if blocked:
        names.append(re.escape(BLOCKED_FILE))
    return "(?:" + "|".join(names) + ")"


def _mention(blocked):
    return re.compile(_names(blocked) + r"\b")


def _redirect(blocked):
    return re.compile(r">\|?\s*['\"]?[^\s;|&'\"]*" + _names(blocked))


_WRITER = re.compile(
    r"\b(?:tee|mv|cp|rm|ln|truncate|dd|install|rsync|chmod|python\d*(?:\.\d+)?|"
    r"node|ruby|perl|awk|gawk|php|sed\s+(?:[^|;&\n]*\s)?-[a-zA-Z]*i|"
    r"git\s+(?:\S+\s+)*(?:checkout|restore|apply|stash|reset))\b"
)


def agent_route(cmd, blocked=False):
    """Why a shell command is a self-transition route, or None. With blocked,
    writes to BLOCKED.md count as one too."""
    mention, redirect = _mention(blocked), _redirect(blocked)
    if _CLI_ROUTE.search(cmd):
        return "runs osengineer approve, or state set / profile on what the hooks own"
    if _STATE_CODE.search(cmd):
        return "calls osEngineer's state writers"
    if _STATE_WIPE.search(cmd):
        return "removes .osengineer state"
    for part in re.split(r"\|\||&&|[;|\n]", cmd):
        if not mention.search(part):
            continue
        if redirect.search(part) or _WRITER.search(part):
            return WRITE_ROUTE
    if redirect.search(cmd):
        return WRITE_ROUTE
    return None


WRITE_ROUTE = ("writes a hook-owned .osengineer file (state.yml, approvals.jsonl, runtime.yml, "
               "profile.json, workbench-config.yml or BLOCKED.md)")

REFUSAL = (
    "Phase changes are a human decision: only the human approves a phase, by "
    "running `osengineer approve <phase>` in their own terminal (or as a `!` "
    "command in Claude Code). Ask the human to approve; do not edit "
    ".osengineer/state.yml, approvals.jsonl, runtime.yml (budget counters), "
    "profile.json or workbench-config.yml (budget limits), and leave "
    ".osengineer/BLOCKED.md for the human while the phase is blocked. "
    "OSE_BYPASS does not lift this."
)
