#!/usr/bin/env python3
# osEngineer-read-guard.py — Claude PreToolUse hook on Write/Edit.
#
# Advisory: when an edit is attempted on an existing file inside an osEngineer
# repo, remind the agent to Read first.
#
# Claude Code itself enforces read-before-edit natively, so this hook detects
# the Claude Code session and silently exits in that environment.

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from osengineer_common import find_osengineer_root


def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return

    tool = (data.get("tool_name") or "").lower()
    is_edit_tool = any(t in tool for t in ("write", "edit", "replace"))
    if not is_edit_tool:
        return

    is_claude_code = (
        bool(isinstance(data.get("session_id"), str) and data.get("session_id"))
        or bool(os.environ.get("CLAUDE_CODE_ENTRYPOINT"))
        or bool(os.environ.get("CLAUDE_CODE_SSE_PORT"))
        or bool(os.environ.get("CLAUDE_SESSION_ID"))
        or bool(os.environ.get("CLAUDECODE"))
    )
    if is_claude_code:
        return

    file_path = (
        data.get("tool_input", {}).get("file_path")
        or data.get("tool_input", {}).get("path")
        or data.get("tool_input", {}).get("TargetFile")
        or data.get("tool_input", {}).get("AbsolutePath")
        or ""
    )
    if not file_path:
        return

    if not Path(file_path).exists():
        return

    repo_root = find_osengineer_root(data.get("cwd") or os.getcwd())
    if not repo_root:
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                f"READ-BEFORE-EDIT REMINDER: {Path(file_path).name} exists on disk. "
                "If you have not Read it in this session, do so first — the runtime "
                "will otherwise reject the edit."
            ),
        },
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
