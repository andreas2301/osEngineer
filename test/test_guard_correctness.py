"""Guards must fire where they claim to, on the verbs that actually exist.

Three defects, each of which makes an advertised rule unenforceable:

  1. pre-bash-guard tests `Path(cwd)/.osengineer/state.yml` and returns early
     if absent, THEN resolves the real root with find_osengineer_root(cwd) seven
     lines later. Any session whose cwd is a subdirectory silently loses the
     destructive-command denylist. This matters far more once Kimi wiring is
     machine-global, because then hooks fire from every directory on the box.

  2. prompt-guard gates `/osEngineer:execute` — a verb that has never shipped.
     The real execute verbs are fix, feature and hotfix, and all three are
     ungated, directly contradicting commands/osEngineer-fix.md:38-46 which
     tells the user the hook will block them.

  3. Command frontmatter is internally inconsistent: osEngineer-fix.md declares
     `phase_allowed: [execute]` while its own prose preconditions require phase
     in `idle | plan` and say the command refuses when phase is already execute.
     No command anywhere declares `phase_after: execute`, so `execute` is a
     phase nothing produces — making every command that requires it unreachable.
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"
COMMANDS = ROOT / "commands"

INITIAL_PHASE = "idle"


def make_repo(tmp, phase="idle"):
    repo = Path(tmp)
    (repo / ".osengineer").mkdir(parents=True, exist_ok=True)
    (repo / ".osengineer" / "state.yml").write_text(
        f"phase: {phase}\ncurrent_team: null\nbudget_used: 0\n"
    )
    return repo


def run_hook(name, payload, cwd=None):
    return subprocess.run(
        [sys.executable, str(HOOKS / name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(cwd) if cwd else None,
    )


def emitted(proc):
    out = proc.stdout.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def is_block(obj):
    if not obj:
        return False
    hso = obj.get("hookSpecificOutput") or {}
    return obj.get("decision") == "block" or hso.get("permissionDecision") == "deny"


def parse_frontmatter(path):
    raw = path.read_text()
    if not raw.startswith("---"):
        return {}
    lines = raw.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}
    fm = {}
    for line in lines[1:end]:
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith("[") and val.endswith("]"):
            fm[key] = [v.strip() for v in val[1:-1].split(",") if v.strip()]
        else:
            fm[key] = val.strip("\"'")
    return fm


def all_commands():
    return {p: parse_frontmatter(p) for p in sorted(COMMANDS.glob("osEngineer-*.md"))}


class TestBashGuardWorksFromSubdirectory(unittest.TestCase):
    def test_denylist_fires_from_nested_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            nested = repo / "src" / "deep" / "nested"
            nested.mkdir(parents=True)
            proc = run_hook(
                "osEngineer-pre-bash-guard.py",
                {
                    "session_id": "sub-1",
                    "cwd": str(nested),
                    "tool_name": "Bash",
                    "tool_input": {"command": "chmod 777 /etc/passwd"},
                },
                cwd=nested,
            )
            self.assertNotIn("Traceback", proc.stderr)
            self.assertTrue(
                is_block(emitted(proc)),
                "destructive-bash guard did not block from a subdirectory of an "
                "osEngineer repo; it self-disables whenever cwd is not the repo "
                f"root. stdout={proc.stdout!r}",
            )

    def test_denylist_still_fires_at_repo_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            proc = run_hook(
                "osEngineer-pre-bash-guard.py",
                {
                    "session_id": "root-1",
                    "cwd": str(repo),
                    "tool_name": "Bash",
                    "tool_input": {"command": "chmod 777 /etc/passwd"},
                },
                cwd=repo,
            )
            self.assertTrue(is_block(emitted(proc)), "regression at repo root")

    def test_stays_silent_outside_any_osengineer_repo(self):
        """Global Kimi wiring means this hook runs everywhere. It must not
        block commands in directories that have nothing to do with osEngineer."""
        with tempfile.TemporaryDirectory() as tmp:
            plain = Path(tmp) / "unrelated"
            plain.mkdir()
            proc = run_hook(
                "osEngineer-pre-bash-guard.py",
                {
                    "session_id": "out-1",
                    "cwd": str(plain),
                    "tool_name": "Bash",
                    "tool_input": {"command": "chmod 777 /etc/passwd"},
                },
                cwd=plain,
            )
            self.assertFalse(
                is_block(emitted(proc)),
                "guard blocked outside any osEngineer repo — with machine-global "
                "Kimi wiring that would break unrelated work on the whole box",
            )


class TestPromptGuardGatesRealVerbs(unittest.TestCase):
    def test_no_reference_to_nonexistent_execute_verb(self):
        src = (HOOKS / "osEngineer-prompt-guard.py").read_text()
        shipped = {fm.get("name") for fm in all_commands().values() if fm.get("name")}
        self.assertNotIn(
            "osEngineer:execute", shipped, "test premise stale: :execute now ships"
        )
        hits = [
            f"{i}: {line.strip()}"
            for i, line in enumerate(src.splitlines(), 1)
            if "/osEngineer:execute" in line
        ]
        self.assertEqual(
            hits, [],
            "prompt-guard still gates /osEngineer:execute, a verb that has never "
            "shipped. The real execute verbs are fix, feature and hotfix.\n"
            + "\n".join(hits),
        )

    def test_fix_without_phase_plan_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, phase="plan")
            proc = run_hook(
                "osEngineer-prompt-guard.py",
                {"session_id": "pg-1", "cwd": str(repo),
                 "prompt": "/osEngineer:fix TICKET-1"},
                cwd=repo,
            )
            self.assertNotIn("Traceback", proc.stderr)
            self.assertTrue(
                is_block(emitted(proc)),
                "/osEngineer:fix ran with no PHASE_PLAN.md; osEngineer-fix.md:38-46 "
                f"promises the hook blocks this. stdout={proc.stdout!r}",
            )

    def test_feature_without_phase_plan_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, phase="plan")
            proc = run_hook(
                "osEngineer-prompt-guard.py",
                {"session_id": "pg-2", "cwd": str(repo),
                 "prompt": "/osEngineer:feature TICKET-2"},
                cwd=repo,
            )
            self.assertTrue(is_block(emitted(proc)), "/osEngineer:feature ungated")

    def test_fix_with_phase_plan_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, phase="plan")
            phase_dir = repo / "planning" / "active" / "phase-1"
            phase_dir.mkdir(parents=True)
            (phase_dir / "PHASE_PLAN.md").write_text("# Phase 1\n")
            proc = run_hook(
                "osEngineer-prompt-guard.py",
                {"session_id": "pg-3", "cwd": str(repo),
                 "prompt": "/osEngineer:fix TICKET-3"},
                cwd=repo,
            )
            self.assertFalse(
                is_block(emitted(proc)),
                "a valid PHASE_PLAN.md exists but /osEngineer:fix was still blocked",
            )

    def test_unrelated_prompt_is_not_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, phase="plan")
            proc = run_hook(
                "osEngineer-prompt-guard.py",
                {"session_id": "pg-4", "cwd": str(repo),
                 "prompt": "what does this repo do?"},
                cwd=repo,
            )
            self.assertFalse(is_block(emitted(proc)), "plain question was blocked")


class TestCommandFrontmatterIsCoherent(unittest.TestCase):
    def test_every_command_declares_name_and_phase_allowed(self):
        missing = [
            p.name for p, fm in all_commands().items()
            if not fm.get("name") or not fm.get("phase_allowed")
        ]
        self.assertEqual(missing, [], f"commands missing frontmatter: {missing}")

    def test_every_command_is_reachable(self):
        """Some command must be able to produce a phase each command allows.

        `execute` is currently declared by nothing as a phase_after, yet fix,
        feature, verify and both sandbox recipes all require it — so the whole
        execute family is unreachable through the documented command graph.
        """
        cmds = all_commands()
        producible = {INITIAL_PHASE}
        for fm in cmds.values():
            after = fm.get("phase_after")
            if after and after not in ("null", "none"):
                producible.add(after)
        unreachable = {
            p.name: fm["phase_allowed"]
            for p, fm in cmds.items()
            if fm.get("phase_allowed")
            and not (set(fm["phase_allowed"]) & producible)
        }
        self.assertEqual(
            unreachable, {},
            "these commands require a phase no command produces and no fresh "
            f"repo starts in ({sorted(producible)}): {unreachable}",
        )

    def test_frontmatter_matches_documented_preconditions(self):
        """fix.md prose says idle|plan; its frontmatter says execute."""
        fix = COMMANDS / "osEngineer-fix.md"
        fm = parse_frontmatter(fix)
        body = fix.read_text()
        m = re.search(r"reports `phase` in `([^`]+)` state", body)
        self.assertIsNotNone(m, "fix.md no longer documents its phase precondition")
        documented = {p.strip() for p in m.group(1).split("|")}
        self.assertTrue(
            set(fm.get("phase_allowed", [])) & documented,
            f"osEngineer-fix.md frontmatter phase_allowed={fm.get('phase_allowed')} "
            f"shares nothing with its own documented precondition {sorted(documented)}",
        )

    def test_no_stale_js_hook_references(self):
        """The Node->Python migration left .js hook names in user-facing prose."""
        offenders = []
        for p in sorted(COMMANDS.glob("*.md")):
            for i, line in enumerate(p.read_text().splitlines(), 1):
                if re.search(r"osEngineer-[a-z-]+\.js", line):
                    offenders.append(f"{p.name}:{i}: {line.strip()}")
        self.assertEqual(offenders, [], "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
