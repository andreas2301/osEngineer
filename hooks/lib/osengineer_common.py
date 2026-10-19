#!/usr/bin/env python3
# osengineer_common.py — shared helpers for osEngineer Python hooks.

import fcntl
import json
import os
import re
import sys
import tempfile
from pathlib import Path

# The profile loader ships in repo_profile/ so the installed skill can reuse it.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from repo_profile import config as profile_config  # noqa: E402

STDIN_TIMEOUT_MS = 3000


def read_stdin():
    """Read all stdin with a soft timeout. In practice hooks are invoked by the
    assistant runtime which closes stdin promptly, so a blocking read is fine."""
    try:
        return sys.stdin.read()
    except Exception:
        return ""


def find_osengineer_root(cwd=None):
    current = Path(cwd or os.getcwd()).resolve()
    home = Path.home()
    while True:
        if (current / ".osengineer").is_dir():
            return current
        parent = current.parent
        if parent == current or current == home:
            break
        current = parent
    return None


# Volatile counters live in the gitignored runtime.yml, not the tracked
# state.yml, so hook writes on every tool call don't dirty the tree.
RUNTIME_FIELDS = {"budget_used", "context_used_pct"}


def _parse_yml_map(p, state):
    for line in p.read_text().splitlines():
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if not m:
            continue
        val = m.group(2).strip().strip("\"'")
        # YAML null spellings must not read as a truthy string (e.g. a team
        # literally named "null").
        state[m.group(1)] = None if val in ("", "null", "~", "Null", "NULL") else val


def read_state_map(repo_root):
    d = Path(repo_root) / ".osengineer"
    p = d / "state.yml"
    if not p.exists():
        return None
    state = {}
    _parse_yml_map(p, state)
    runtime = d / "runtime.yml"
    if runtime.exists():
        _parse_yml_map(runtime, state)
    return state


def read_workbench_field(cwd, key):
    current = Path(cwd).resolve()
    home = Path.home()
    while True:
        p = current / ".osengineer" / "workbench-config.yml"
        if p.exists():
            try:
                raw = p.read_text()
                m = re.search(rf"^{re.escape(key)}:\s*\"(.*?)\"", raw, re.MULTILINE)
                if not m:
                    m = re.search(rf"^{re.escape(key)}:\s*(.*)$", raw, re.MULTILINE)
                if m:
                    val = m.group(1).strip().strip("\"'")
                    if val not in ("none", ""):
                        return val
            except Exception:
                pass
        parent = current.parent
        if parent == current or current == home:
            break
        current = parent
    return None


def count_handoffs(repo_root):
    d = Path(repo_root) / ".osengineer" / "handoffs"
    if not d.is_dir():
        return 0
    return len([f for f in os.listdir(d) if f.endswith(".md") and f != ".gitkeep"])


def read_team_cache(repo_root, team_id):
    p = Path(repo_root) / ".osengineer" / "teams" / f"{team_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def glob_to_regex(g):
    r = re.sub(r"[.+^${}()|[\\]\\\\]", r"\\\\\g<0>", g)
    r = r.replace("**/", "___DOUBLESLASH___")
    r = r.replace("**", "___DOUBLE___")
    r = r.replace("*", "[^/]*")
    r = r.replace("?", "[^/]")
    r = r.replace("___DOUBLESLASH___", "(?:.*/)?")
    r = r.replace("___DOUBLE___", ".*")
    return re.compile("^" + r + "$")


def path_matches_any(file_path, globs):
    normalised = file_path.replace("\\", "/").lstrip("./")
    for g in globs or []:
        if glob_to_regex(g).match(normalised):
            return True
    return False


def _is_runtime_field(key):
    # budget_* are the circuit breaker's per-tool-call usage counters.
    return key in RUNTIME_FIELDS or key.startswith("budget_")


def update_state_fields(repo_root, fn):
    """Atomically apply fn(current state map) -> {key: value} under the state lock.

    Each key goes to runtime.yml (volatile counters) or state.yml, as with
    write_state_field. Holding one lock across read and write keeps counters
    exact when hooks for parallel tool calls race.
    """
    d = Path(repo_root) / ".osengineer"
    d.mkdir(parents=True, exist_ok=True)
    lock_path = d / ".state.lock"
    with open(lock_path, "a") as lock_f:
        fcntl.flock(lock_f, fcntl.LOCK_EX)
        try:
            current = read_state_map(repo_root) or {}
            updates = fn(current) or {}
            for name in ("runtime.yml", "state.yml"):
                part = {k: v for k, v in updates.items() if (name == "runtime.yml") == _is_runtime_field(k)}
                if part:
                    _rewrite_fields(d, d / name, part)
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
        return updates


def _rewrite_fields(d, state_path, updates):
    tmp_name = None
    try:
        raw = state_path.read_text() if state_path.exists() else ""
        lines = raw.splitlines()
        for key, value in updates.items():
            for i, line in enumerate(lines):
                if re.match(r"^" + re.escape(key) + r":", line):
                    lines[i] = f"{key}: {value}"
                    break
            else:
                lines.append(f"{key}: {value}")
        content = "\n".join(lines) + "\n"
        with tempfile.NamedTemporaryFile(
            mode="w", dir=str(d), prefix=".state.", delete=False
        ) as tmp_f:
            tmp_name = tmp_f.name
            tmp_f.write(content)
            tmp_f.flush()
            os.fsync(tmp_f.fileno())
        os.replace(tmp_name, state_path)
        tmp_name = None
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def write_state_field(repo_root, key, value):
    update_state_fields(repo_root, lambda _current: {key: value})


def emit_json(obj):
    print(json.dumps(obj))


def emit_block(event, reason):
    """Emit a block that is honoured by BOTH Claude Code and Kimi Code."""
    emit_json({
        "decision": "block",
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": event,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    })


def emit_context(event, text):
    """Emit advisory context visible on BOTH harnesses."""
    emit_json({
        "message": text,
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": text,
        },
    })


def read_payload():
    """Parse stdin as the hook's JSON object; anything else is malformed."""
    try:
        data = json.loads(sys.stdin.read())
    except ValueError as exc:
        raise ValueError("invalid hook input or data") from exc
    if not isinstance(data, dict):
        raise ValueError("invalid hook input or data")
    return data


# Events whose action a hook can still stop. PostToolUse (tool already ran),
# SessionStart and the statusline can only fail loudly.
BLOCKABLE_EVENTS = {"PreToolUse", "UserPromptSubmit"}


def fail_strict(hook, event, exc):
    """Strict failure contract: diagnose on stderr, block, exit 2.

    Exit 2 is Claude Code's block signal (stderr reaches the model); the
    dual-dialect stdout block covers Kimi Code. Never exit 0 or 1 here:
    both let the action proceed.
    """
    message = f"{hook}: {type(exc).__name__}: {exc}"
    print(message, file=sys.stderr)
    if event in BLOCKABLE_EVENTS:
        emit_block(event, f"osEngineer: hook failed, action blocked ({message})")
    sys.exit(2)


def bypass_log(repo_root, hook, reason):
    # An unaudited bypass must fail visibly rather than silently continue.
    p = Path(repo_root) / ".osengineer" / "bypass-log.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": datetime_utc_iso(), "hook": hook, "reason": reason}
    with p.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def load_profile(repo_root):
    """Effective .osengineer/profile.json; invalid profiles raise (hooks then block)."""
    return profile_config.load(repo_root)


def is_repo_profile(repo_root):
    if load_profile(repo_root)["profile"] == "repo":
        return True
    return read_workbench_field(repo_root, "validation_profile") == "repo"


def profile_setting(repo_root, key):
    """One top-level profile setting, defaults included."""
    return load_profile(repo_root)[key]


def planning_dir(repo_root):
    if is_repo_profile(repo_root):
        return Path(repo_root) / profile_setting(repo_root, "planDirectory")
    return Path(repo_root) / "planning"


def datetime_utc_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def extract_frontmatter(raw):
    if not raw.startswith("---"):
        return None
    lines = raw.splitlines()
    if lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i]
    return None


def parse_frontmatter(raw):
    fm_lines = extract_frontmatter(raw)
    if fm_lines is None:
        return None
    result = {}
    i = 0
    while i < len(fm_lines):
        line = fm_lines[i]
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key = m.group(1)
        value = m.group(2)
        if re.match(r"^[|>>][-+]?\s*$", value.strip()):
            buf = []
            i += 1
            while i < len(fm_lines):
                nxt = fm_lines[i]
                if re.match(r"^[A-Za-z_][\w-]*:", nxt):
                    break
                if nxt.strip() == "":
                    buf.append("")
                else:
                    buf.append(nxt.lstrip())
                i += 1
            result[key] = " ".join(buf)
            continue
        result[key] = value.strip().strip("\"'")
        i += 1
    return result
