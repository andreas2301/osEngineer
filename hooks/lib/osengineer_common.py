#!/usr/bin/env python3
# osengineer_common.py — shared helpers for osEngineer Python hooks.

import fcntl
import json
import os
import re
import sys
import tempfile
from pathlib import Path

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
    for _ in range(8):
        if (current / ".osengineer").is_dir():
            return current
        parent = current.parent
        if parent == current or current == home:
            break
        current = parent
    return None


def read_state_map(repo_root):
    p = Path(repo_root) / ".osengineer" / "state.yml"
    if not p.exists():
        return None
    state = {}
    for line in p.read_text().splitlines():
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if not m:
            continue
        val = m.group(2).strip().strip("\"'")
        state[m.group(1)] = val or None
    return state


def read_workbench_field(cwd, key):
    current = Path(cwd).resolve()
    home = Path.home()
    for _ in range(8):
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


def write_state_field(repo_root, key, value):
    d = Path(repo_root) / ".osengineer"
    d.mkdir(parents=True, exist_ok=True)
    state_path = d / "state.yml"
    lock_path = d / ".state.lock"
    tmp_name = None
    with open(lock_path, "a") as lock_f:
        fcntl.flock(lock_f, fcntl.LOCK_EX)
        try:
            raw = state_path.read_text() if state_path.exists() else ""
            lines = raw.splitlines()
            found = False
            for i, line in enumerate(lines):
                if re.match(r"^" + re.escape(key) + r":", line):
                    lines[i] = f"{key}: {value}"
                    found = True
                    break
            if not found:
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
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            if tmp_name is not None:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass


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


def bypass_log(repo_root, hook, reason):
    try:
        p = Path(repo_root) / ".osengineer" / "bypass-log.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        entry = json.dumps({
            "ts": datetime_utc_iso(),
            "hook": hook,
            "reason": reason,
        })
        with open(p, "a") as f:
            f.write(entry + "\n")
    except Exception:
        pass


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
