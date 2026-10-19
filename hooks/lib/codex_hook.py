#!/usr/bin/env python3
"""Run an osEngineer guard for Codex CLI and translate its verdict.

Usage (wired by install.sh into <repo>/.codex/hooks.json):
    python3 hooks/lib/codex_hook.py osEngineer-<guard>.py

The guards speak the Claude Code / Kimi dialect. Codex differs in ways that
would make them fail open (learn.chatgpt.com/docs/hooks):

  * Edits arrive as tool_name "apply_patch", the patch in tool_input.command,
    with no file_path. Each file the patch touches is checked as one Edit.
  * Shell tools may be reported as exec_command etc., and the command as argv.
    They are normalised to Bash with a string command.
  * Codex marks a hook run failed on unsupported output fields and lets the
    action continue, so a block is exit 2 with the reason on stderr, and
    context is re-emitted as hookSpecificOutput.additionalContext only.

A guard's own non-zero exit is relayed unchanged.
"""
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
SCRIPT_RE = re.compile(r"^osEngineer-[A-Za-z0-9-]+\.py$")
SHELL_TOOLS = {"bash", "shell", "local_shell", "exec_command", "unified_exec", "container.exec"}
PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+?)\s*$", re.MULTILINE)


def run_guard(script, payload):
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / script)],
        input=json.dumps(payload), capture_output=True, text=True,
    )


def patch_payloads(payload):
    """One Claude-shaped Edit payload per file an apply_patch touches."""
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    cwd = Path(payload.get("cwd") or ".")
    paths = PATCH_FILE_RE.findall(command) if isinstance(command, str) else []
    if not paths:
        return [dict(payload, tool_name="Edit", tool_input={})]
    out = []
    for p in paths:
        target = Path(p)
        if not target.is_absolute():
            target = cwd / target
        out.append(dict(payload, tool_name="Edit", tool_input={"file_path": str(target)}))
    return out


def normalise(payload):
    tool = payload.get("tool_name")
    if not isinstance(tool, str):
        return [payload]
    if tool == "apply_patch":
        return patch_payloads(payload)
    if tool.lower() in SHELL_TOOLS:
        tool_input = dict(payload.get("tool_input") or {})
        if isinstance(tool_input.get("command"), list):
            tool_input["command"] = shlex.join(str(a) for a in tool_input["command"])
        return [dict(payload, tool_name="Bash", tool_input=tool_input)]
    return [payload]


def verdict(stdout):
    """(block_reason, context) from a guard's JSON output."""
    try:
        out = json.loads(stdout)
    except ValueError:
        return None, stdout.strip() or None  # plain text is context
    if not isinstance(out, dict):
        return None, None
    hso = out.get("hookSpecificOutput") if isinstance(out.get("hookSpecificOutput"), dict) else {}
    if out.get("decision") == "block" or hso.get("permissionDecision") == "deny":
        return hso.get("permissionDecisionReason") or out.get("reason") or "osEngineer: blocked", None
    return None, hso.get("additionalContext") or out.get("message")


def main():
    if len(sys.argv) != 2 or not SCRIPT_RE.match(sys.argv[1]) or not (HOOKS_DIR / sys.argv[1]).is_file():
        print(f"codex_hook: expected one osEngineer-*.py guard in {HOOKS_DIR}, got {sys.argv[1:]}", file=sys.stderr)
        return 1
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        # Let the guard apply its own bad-input contract.
        proc = subprocess.run([sys.executable, str(HOOKS_DIR / sys.argv[1])],
                              input=raw, capture_output=True, text=True)
        sys.stderr.write(proc.stderr)
        return proc.returncode

    event = payload.get("hook_event_name") or "PreToolUse"
    contexts = []
    for item in normalise(payload):
        proc = run_guard(sys.argv[1], item)
        sys.stderr.write(proc.stderr)
        if proc.returncode != 0:
            return proc.returncode
        reason, context = verdict(proc.stdout)
        if reason:
            print(reason, file=sys.stderr)
            return 2
        if context:
            contexts.append(context)
    if contexts:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": "\n\n".join(contexts),
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
