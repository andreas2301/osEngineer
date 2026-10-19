#!/usr/bin/env python3
# osEngineer-subagent-start.py — Claude Code / Codex SubagentStart hook.
#
# SessionStart context never reaches a subagent, so every subagent would
# otherwise run without the agent rules or the current phase/team. This
# re-injects the session-start state banner plus the agent rules
# (templates/agent-rules.md) as the subagent's additionalContext. The repo
# profile brings its own policy, so it gets the banner only.

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from osengineer_common import agent_rules, emit_context, find_osengineer_root, is_repo_profile, state_banner, fail_strict, read_payload


def main():
    data = read_payload()
    cwd = data.get("cwd") or os.getcwd()
    repo_root = find_osengineer_root(cwd)
    if not repo_root:
        return
    parts = [state_banner(repo_root)]
    if not is_repo_profile(repo_root):
        parts.append(agent_rules())
    context = "\n\n".join(p for p in parts if p)
    if context:
        emit_context("SubagentStart", context)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Strict: SubagentStart cannot block; fail loudly with exit 2 + stderr.
        fail_strict(Path(__file__).name, 'SubagentStart', exc)
