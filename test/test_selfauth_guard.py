"""An agent must not be able to lift its own denylist.

Observed live on 2026-09-14, Kimi Code 0.36.1 against the real guards: the
destructive-bash guard correctly blocked `chmod 777` twice, and the agent then
wrote `.osengineer/current-plan.md` with the four required headings — the
unblock documented at trust/denylist.md:117 — and re-ran the command, which
succeeded. File mode went 644 -> 777.

    "the repo's osEngineer denylist blocked the bare command twice ... It only
     went through after I wrote the 4-part plan file the hook requires at
     .osengineer/current-plan.md"

So the human-in-the-loop gate was a file the constrained agent could create.
Interactively that is arguably visible to the human in the session. Headlessly
it is no gate at all: any autonomous run can lift any denylist entry by writing
four markdown headings.

Two defences, both required:

  1. Self-authorisation is blocked everywhere — the edit guard refuses writes to
     .osengineer/current-plan.md, so only a human can author it.
  2. Headless runs treat the denylist as absolute — OSE_HEADLESS=1 makes the
     plan-file unblock inert regardless of who wrote the file.

One thing that already held and must keep holding: the agent tried to pass
OSE_BYPASS=1 as part of the shell command and it had no effect, because the
hook reads its own process env rather than parsing the command string.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"

FOUR_PART_PLAN = """# Touch
.osengineer/

# Change
anything

# Impact
none

# Rollback
git checkout .
"""


def make_repo(tmp, plan=False):
    repo = Path(tmp)
    (repo / ".osengineer").mkdir(parents=True, exist_ok=True)
    (repo / ".osengineer" / "state.yml").write_text(
        "phase: execute\ncurrent_team: null\nbudget_used: 0\n"
    )
    if plan:
        (repo / ".osengineer" / "current-plan.md").write_text(FOUR_PART_PLAN)
    return repo


def run_hook(name, payload, cwd=None, env=None):
    e = dict(os.environ)
    e.pop("OSE_BYPASS", None)
    e.pop("OSE_HEADLESS", None)
    if env:
        e.update(env)
    return subprocess.run(
        [sys.executable, str(HOOKS / name)],
        input=json.dumps(payload), capture_output=True, text=True,
        timeout=30, cwd=str(cwd) if cwd else None, env=e,
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


class TestAgentCannotWriteItsOwnPlanFile(unittest.TestCase):
    def test_write_to_current_plan_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            proc = run_hook(
                "osEngineer-pre-edit-guard.py",
                {"session_id": "sa-1", "cwd": str(repo), "tool_name": "Write",
                 "tool_input": {"file_path": str(repo / ".osengineer" / "current-plan.md")}},
                cwd=repo,
            )
            self.assertNotIn("Traceback", proc.stderr)
            self.assertTrue(
                is_block(emitted(proc)),
                "the agent can author .osengineer/current-plan.md, which is the "
                "documented unblock for every denylist pattern — that makes the "
                f"HITL gate self-serviceable. stdout={proc.stdout!r}",
            )

    def test_edit_to_current_plan_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, plan=True)
            proc = run_hook(
                "osEngineer-pre-edit-guard.py",
                {"session_id": "sa-2", "cwd": str(repo), "tool_name": "Edit",
                 "tool_input": {"file_path": str(repo / ".osengineer" / "current-plan.md")}},
                cwd=repo,
            )
            self.assertTrue(is_block(emitted(proc)), "Edit to the plan file was allowed")

    def test_relative_path_is_also_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            proc = run_hook(
                "osEngineer-pre-edit-guard.py",
                {"session_id": "sa-3", "cwd": str(repo), "tool_name": "Write",
                 "tool_input": {"file_path": ".osengineer/current-plan.md"}},
                cwd=repo,
            )
            self.assertTrue(
                is_block(emitted(proc)),
                "relative path slipped past the self-authorisation check",
            )

    def test_other_osengineer_files_still_writable(self):
        """The phase gate deliberately allows .osengineer/ edits; only the
        plan file is special."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            proc = run_hook(
                "osEngineer-pre-edit-guard.py",
                {"session_id": "sa-4", "cwd": str(repo), "tool_name": "Write",
                 "tool_input": {"file_path": str(repo / ".osengineer" / "notes.md")}},
                cwd=repo,
            )
            self.assertFalse(
                is_block(emitted(proc)),
                "blocked an unrelated .osengineer/ file; only current-plan.md "
                "should be protected",
            )


class TestHeadlessDenylistIsAbsolute(unittest.TestCase):
    def test_plan_file_does_not_unblock_when_headless(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, plan=True)
            proc = run_hook(
                "osEngineer-pre-bash-guard.py",
                {"session_id": "hl-1", "cwd": str(repo), "tool_name": "Bash",
                 "tool_input": {"command": "chmod 777 /etc/passwd"}},
                cwd=repo, env={"OSE_HEADLESS": "1"},
            )
            self.assertNotIn("Traceback", proc.stderr)
            self.assertTrue(
                is_block(emitted(proc)),
                "a 4-part plan lifted the denylist during a headless run; with "
                "no human in the session the plan file proves nothing",
            )

    def test_plan_file_still_unblocks_interactively(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, plan=True)
            proc = run_hook(
                "osEngineer-pre-bash-guard.py",
                {"session_id": "hl-2", "cwd": str(repo), "tool_name": "Bash",
                 "tool_input": {"command": "chmod 777 /etc/passwd"}},
                cwd=repo,
            )
            self.assertFalse(
                is_block(emitted(proc)),
                "interactive behaviour regressed: a valid 4-part plan should "
                "still unblock when a human is in the session",
            )

    def test_bypass_env_is_ignored_when_headless(self):
        """OSE_BYPASS is the human's escape hatch, not the runner's."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            proc = run_hook(
                "osEngineer-pre-bash-guard.py",
                {"session_id": "hl-3", "cwd": str(repo), "tool_name": "Bash",
                 "tool_input": {"command": "chmod 777 /etc/passwd"}},
                cwd=repo, env={"OSE_HEADLESS": "1", "OSE_BYPASS": "1"},
            )
            self.assertTrue(
                is_block(emitted(proc)),
                "OSE_BYPASS=1 lifted the denylist in a headless run",
            )


class TestBypassIsNotReadableFromTheCommandString(unittest.TestCase):
    def test_inline_env_assignment_does_not_bypass(self):
        """Held during the live test; lock it in so it cannot regress."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            proc = run_hook(
                "osEngineer-pre-bash-guard.py",
                {"session_id": "by-1", "cwd": str(repo), "tool_name": "Bash",
                 "tool_input": {"command": "OSE_BYPASS=1 chmod 777 /etc/passwd"}},
                cwd=repo,
            )
            self.assertTrue(
                is_block(emitted(proc)),
                "an OSE_BYPASS=1 prefix inside the command string disabled the "
                "guard; bypass must come from the hook's own process env",
            )


class TestDenylistContractIsDocumented(unittest.TestCase):
    def test_denylist_documents_the_headless_rule(self):
        body = (ROOT / "trust" / "denylist.md").read_text()
        self.assertIn(
            "OSE_HEADLESS", body,
            "trust/denylist.md still documents the 4-part plan as an "
            "unconditional unblock; it must record that headless runs ignore it",
        )


if __name__ == "__main__":
    unittest.main()
