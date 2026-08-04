#!/usr/bin/env python3
# osEngineer-prompt-guard.py — Claude UserPromptSubmit hook.
#
# On every prompt: read .osengineer/state.yml from cwd and inject a one-paragraph
# status block (phase, current team, budget used%, open handoff count) into the
# agent context as `additionalContext`.
#
# Also blocks certain prompts when state is incompatible:
#   - `/osEngineer:execute` when no PHASE_PLAN.md exists for the active phase
#   - any prompt when state.phase === 'blocked' (advisory, not block)
#
# Honours OSE_BYPASS=1. Always exits 0 on parse failure.

import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from osengineer_common import (
    bypass_log,
    count_handoffs,
    find_osengineer_root,
    parse_frontmatter,
    read_state_map,
)

STDIN_TIMEOUT_MS = 3000
ROUTING_STOPWORDS = {
    "the", "a", "an", "is", "are", "in", "on", "of", "for", "to", "with",
    "when", "this", "that", "and", "or",
}


def tokenize(text):
    if not text:
        return []
    return [
        t for t in re.split(r"[\s\.,;:!?\(\)\[\]\{\}'\"`<>/\\\-_=+*&^%$#@~|]+", text.lower())
        if t and t not in ROUTING_STOPWORDS
    ]


def sentence_until_terminator(text):
    if not text:
        return ""
    i = 0
    while i < len(text):
        if text[i] == ".":
            j = i + 1
            if j >= len(text):
                return text[:i + 1].strip()
            while j < len(text) and text[j].isspace():
                j += 1
            if j >= len(text):
                return text[:i + 1].strip()
            if text[j].isupper():
                return text[:i + 1].strip()
        if text[i] == ";":
            return text[:i].strip() + "."
        i += 1
    return text.strip()


def extract_use_signal(description):
    if not description:
        return ""
    m = re.search(r"Use when\s+(.+)$", description, re.IGNORECASE)
    if not m:
        return ""
    return sentence_until_terminator(m.group(1))


def extract_dont_use_signal(description):
    if not description:
        return ""
    m = re.search(r"Don'?t use(?:\s+when)?\s+(.+)$", description, re.IGNORECASE) or \
        re.search(r"Do not use(?:\s+when)?\s+(.+)$", description, re.IGNORECASE)
    if not m:
        return ""
    return sentence_until_terminator(m.group(1))


def first_sentence(description):
    return sentence_until_terminator(description)


def load_skill_entries(ose_home):
    entries = []
    agents_dir = Path(ose_home) / "agents"
    if agents_dir.is_dir():
        for dirname in sorted(os.listdir(agents_dir)):
            agent_path = agents_dir / dirname / "AGENT.md"
            if not agent_path.is_file():
                flat = agents_dir / f"{dirname}.md"
                if flat.is_file():
                    agent_path = flat
                else:
                    continue
            try:
                raw = agent_path.read_text()
                fm = parse_frontmatter(raw)
                if not fm or not fm.get("name") or not fm.get("description"):
                    continue
                entries.append({"name": fm["name"], "description": fm["description"], "type": "agent"})
            except Exception:
                continue
    cmd_dir = Path(ose_home) / "commands"
    if cmd_dir.is_dir():
        for fname in sorted(os.listdir(cmd_dir)):
            if not re.match(r"^osEngineer-.*\.md$", fname):
                continue
            try:
                raw = (cmd_dir / fname).read_text()
                fm = parse_frontmatter(raw)
                if not fm or not fm.get("name") or not fm.get("description"):
                    continue
                entries.append({"name": fm["name"], "description": fm["description"], "type": "command"})
            except Exception:
                continue
    return entries


def find_matching_skills(prompt, ose_home, max_matches=3):
    if not ose_home or not Path(ose_home).is_dir():
        return []
    prompt_tokens = tokenize(prompt)
    if not prompt_tokens:
        return []
    prompt_set = set(prompt_tokens)
    try:
        entries = load_skill_entries(ose_home)
    except Exception:
        return []
    scored = []
    for e in entries:
        use_signal = extract_use_signal(e["description"])
        signal_tokens = tokenize(use_signal)
        if not signal_tokens:
            continue
        signal_set = set(signal_tokens)
        overlap = len(prompt_set & signal_set)
        denom = max(len(prompt_tokens), len(signal_tokens))
        score = overlap / denom if denom else 0
        name_lower = (e.get("name") or "").lower()
        for t in prompt_set:
            if len(t) >= 3 and t in name_lower:
                score += 0.1
                break
        dont_signal = extract_dont_use_signal(e["description"])
        if dont_signal:
            dont_tokens = set(tokenize(dont_signal))
            for t in prompt_set:
                if t in dont_tokens:
                    score -= 0.5
                    break
        if score > 0.15:
            scored.append({"name": e["name"], "description": e["description"], "score": score, "type": e["type"]})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:max_matches]


def format_routing_hints(matches):
    if not matches:
        return ""
    lines = ["osEngineer routing hints (high-confidence matches for this prompt):"]
    for m in matches:
        excerpt = first_sentence(m["description"])
        if len(excerpt) > 200:
            excerpt = excerpt[:197] + "..."
        lines.append(f'- {m["name"]} (score: {m["score"]:.2f}) — {excerpt}')
    return "\n".join(lines)


def build_context(state, open_handoffs):
    parts = [f"phase={state.get('phase') or 'idle'}"]
    if state.get("current_team"):
        parts.append(f"team={state['current_team']}")
    if state.get("budget_used") is not None:
        parts.append(f"budget={state['budget_used']}%")
    if open_handoffs > 0:
        parts.append(f"open_handoffs={open_handoffs}")
    return "osEngineer state: " + " · ".join(parts)


def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return

    cwd = data.get("cwd") or os.getcwd()
    repo_root = find_osengineer_root(cwd)
    if not repo_root:
        return

    if os.environ.get("OSE_BYPASS") == "1":
        bypass_log(repo_root, "prompt-guard", "OSE_BYPASS=1")
        return

    state = read_state_map(repo_root)
    if not state:
        return

    prompt = data.get("prompt") or ""
    open_handoffs = count_handoffs(repo_root)

    if re.search(r"/osEngineer:execute\b", prompt):
        active_dir = Path(repo_root) / "planning" / "active"
        has_plan = False
        if active_dir.is_dir():
            for d in active_dir.iterdir():
                if d.is_dir() and (d / "PHASE_PLAN.md").exists():
                    has_plan = True
                    break
        if not has_plan:
            print(json.dumps({
                "decision": "block",
                "reason": "osEngineer: cannot /osEngineer:execute — no PHASE_PLAN.md in any planning/active/ directory. Run /osEngineer:plan first.",
            }))
            return

    session_id = data.get("session_id") or "default"
    state_str = build_context(state, open_handoffs)
    additional_context = ""

    if session_id and not re.search(r"[/\\]|\.\.", session_id):
        remaining_percent = 100
        metrics_path = Path(tempfile.gettempdir()) / f"claude-ctx-{session_id}.json"
        if metrics_path.exists():
            try:
                metrics = json.loads(metrics_path.read_text())
                if metrics.get("remaining_percentage") is not None:
                    remaining_percent = metrics["remaining_percentage"]
            except Exception:
                pass

        bridge_path = Path(tempfile.gettempdir()) / f"claude-ose-prompt-{session_id}.json"
        session_data = {"lastStateString": "", "turnCounter": 0}
        if bridge_path.exists():
            try:
                session_data = json.loads(bridge_path.read_text())
            except Exception:
                pass

        if remaining_percent <= 40:
            active_dir = Path(repo_root) / "planning" / "active"
            plan_summary = "No active PHASE_PLAN.md found."
            if active_dir.is_dir():
                for phase_dir in active_dir.iterdir():
                    plan_path = phase_dir / "PHASE_PLAN.md"
                    if plan_path.exists():
                        try:
                            plan_lines = "\n".join(plan_path.read_text().splitlines()[:15])
                            plan_summary = f"Active Phase Plan ({phase_dir.name}):\n{plan_lines}"
                            break
                        except Exception:
                            pass
            additional_context = "\n".join([
                f"⚠️ osEngineer CONTEXT DEGRADATION WARNING: Claude context remaining: {remaining_percent}%.",
                "High-frequency turns have triggered auto-compaction. Core instructions and targets have been injected into active memory to prevent cognitive drift.",
                f"Current State: {state_str}",
                plan_summary,
                "CRITICAL WORKER CONSTRAINTS:",
                "1. Commit format: type(scope): subject (Conventional Commits).",
                "2. Enforce TDD: Write the failing test FIRST in a 'red' commit, then implementation in a 'green' commit.",
                "3. Non-interactive Git: All git commands must run with '--no-edit' or 'git -c core.editor=true' to bypass text editor prompts.",
                "4. Phase Gate: Editing outside 'planning/' or '.osengineer/' is strictly read-only during 'discuss' or 'plan' phases.",
                "5. Owns Paths: Edits to a path outside the active team's owns_paths list are blocked.",
                "6. Think Before Coding: State assumptions explicitly; ask if ambiguous.",
                "7. Simplicity First: Write minimum code; no speculative abstractions.",
                "8. Surgical Changes: Touch only what task requires.",
                "9. Goal-Driven Execution: Create tests first to reproduce issue, then loop until pass.",
                "10. Set Hard Token Budgets: Stop runaway iterations.",
                "11. Expose Conflicts: Don't average contradictory patterns.",
                "12. Read Before Writing: Scan existing code before making edits.",
                "13. Test Real Logic: Validate actual logic, not just running to pass.",
                "14. Use Checkpoints: For long-running, multi-step tasks.",
                "15. Fail Explicitly: Avoid silent failures; fail immediately and clearly.",
            ])
            session_data["turnCounter"] = 0
        elif session_data.get("lastStateString") == state_str and session_data.get("turnCounter", 0) < 5:
            session_data["turnCounter"] = session_data.get("turnCounter", 0) + 1
            additional_context = "osEngineer state: active (unchanged)"
        else:
            session_data["lastStateString"] = state_str
            session_data["turnCounter"] = 0
            additional_context = state_str
        try:
            bridge_path.write_text(json.dumps(session_data))
        except Exception:
            pass
    else:
        additional_context = state_str

    try:
        ose_home = os.environ.get("OSENGINEER_HOME")
        if ose_home and prompt:
            matches = find_matching_skills(prompt, ose_home)
            if matches:
                hint_block = format_routing_hints(matches)
                if hint_block:
                    additional_context = f"{additional_context}\n\n{hint_block}" if additional_context else hint_block
    except Exception:
        pass

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional_context,
        },
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
