#!/usr/bin/env python3
# phase_gate.py — the human phase gate (planning/PROTOCOL.md).
#
# `osengineer approve <phase>` is the only way to change the phase. It checks
# TRANSITIONS and the target's prerequisite artifact, records who and when in
# state.yml and appends to .osengineer/approvals.jsonl. The guards use
# agent_route() and PROTECTED_FILES to refuse the agent every route to it.

import getpass
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from osengineer_common import planning_dir, read_state_map, write_state_field

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

# Written only by approve(); `state set` refuses them.
RECORD_FIELDS = ("phase_approved_by", "phase_approved_at")
PROTECTED_FILES = ("state.yml", "approvals.jsonl")


def required_artifact(current, target):
    """Artifact that must exist under <planning>/active/*/ for the move."""
    if target == "execute":
        return "PHASE_PLAN.md"
    if current in ("micro", "hotfix") and target in ("accepted", "idle"):
        return "MICRO_PLAN.md"
    if target == "accepted":
        return "VERIFICATION.md"
    return None


def check(repo_root, current, target):
    """None if the human may approve current -> target, else the reason."""
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
    return None


def approver(repo_root):
    try:
        email = subprocess.run(["git", "config", "user.email"], cwd=str(repo_root),
                               capture_output=True, text=True).stdout.strip()
    except OSError:
        email = ""
    return email or getpass.getuser()


def approve(repo_root, target, reason=None):
    """Validate and apply one transition; returns the log entry. Raises
    ValueError with the refusal reason."""
    state = read_state_map(repo_root) or {}
    current = state.get("phase") or "idle"
    refusal = check(repo_root, current, target)
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
    log = Path(repo_root) / ".osengineer" / "approvals.jsonl"
    with log.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    write_state_field(repo_root, "phase", target)
    write_state_field(repo_root, "phase_approved_by", entry["by"])
    write_state_field(repo_root, "phase_approved_at", entry["ts"])
    return entry


# ── Agent routes (best effort; see planning/PROTOCOL.md "Phase gate") ───────

# osengineer in command position: segment start, a quote (bash -c "..."),
# or $( / backtick, then env assignments, wrappers or an interpreter.
_CLI_ROUTE = re.compile(
    r"(?:^|[;&|(`\n'\"]|\$\()\s*(?:\w+=\S*\s+)*"
    r"(?:(?:sudo|exec|env|command|nohup|time|eval)\s+)*(?:python\d*(?:\.\d+)?\s+)?"
    r"(?:\S*/)?osengineer\s+(?:approve|state\s+set\s+phase\w*)\b"
)
_MENTION = re.compile(r"(?:state\.yml|approvals\.jsonl)\b")
_REDIRECT = re.compile(r">\|?\s*['\"]?[^\s;|&'\"]*(?:state\.yml|approvals\.jsonl)")
_WRITER = re.compile(
    r"\b(?:tee|mv|cp|rm|ln|truncate|dd|install|rsync|chmod|python\d*(?:\.\d+)?|"
    r"node|ruby|perl|awk|gawk|php|sed\s+(?:[^|;&\n]*\s)?-[a-zA-Z]*i|"
    r"git\s+(?:\S+\s+)*(?:checkout|restore|apply|stash|reset))\b"
)


def agent_route(cmd):
    """Why a shell command is a self-transition route, or None."""
    if _CLI_ROUTE.search(cmd):
        return "runs osengineer approve / state set phase"
    if "write_state_field" in cmd:
        return "calls write_state_field"
    for part in re.split(r"\|\||&&|[;|\n]", cmd):
        if not _MENTION.search(part):
            continue
        if _REDIRECT.search(part) or _WRITER.search(part):
            return "writes .osengineer/state.yml or approvals.jsonl"
    if _REDIRECT.search(cmd):
        return "writes .osengineer/state.yml or approvals.jsonl"
    return None


REFUSAL = (
    "Phase changes are a human decision: only the human approves a phase, by "
    "running `osengineer approve <phase>` in their own terminal (or as a `!` "
    "command in Claude Code). Ask the human to approve; do not edit "
    ".osengineer/state.yml or .osengineer/approvals.jsonl. OSE_BYPASS does "
    "not lift this."
)
