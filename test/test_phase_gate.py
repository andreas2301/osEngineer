"""Phase transitions are a human decision, not something the agent can take.

Before this, the agent could move itself out of the read-only planning phases
three ways, and the edit guard told it to use the first:

  * `osengineer state set phase execute` — cmd_state wrote any key/value with
    no transition check and no human in the loop.
  * a Write/Edit of .osengineer/state.yml — .osengineer/ stays editable in
    discuss/plan, so the phase file itself was editable.
  * a shell write (`sed -i`, a redirect, `python -c`) to the same file.

The contract now:

  * `osengineer approve <phase>` is the only way to change the phase. It checks
    the transition table and the phase's prerequisite artifact, records who and
    when in state.yml, and appends to .osengineer/approvals.jsonl. Headless runs
    refuse it outright. `state set phase` routes to the same check.
  * The guards refuse the agent every route to it, in every phase, and
    OSE_BYPASS does not lift that (the refusal is logged instead).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "osengineer"
HOOKS = ROOT / "hooks"
ADAPTER = HOOKS / "lib" / "codex_hook.py"


def make_repo(tmp, phase="discuss"):
    repo = Path(tmp)
    (repo / ".git").mkdir(parents=True, exist_ok=True)
    (repo / ".osengineer").mkdir(parents=True, exist_ok=True)
    (repo / ".osengineer" / "state.yml").write_text(
        f"phase: {phase}\ncurrent_team: null\nosengineer_version: 0.5.0\n"
    )
    return repo


def add_artifact(repo, name, phase_dir="phase-001-x"):
    d = repo / "planning" / "active" / phase_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text("# artifact\n")


def clean_env(**extra):
    env = dict(os.environ)
    for k in ("OSE_BYPASS", "OSE_HEADLESS"):
        env.pop(k, None)
    env.update(extra)
    return env


def cli(repo, *args, **env):
    return subprocess.run(
        [sys.executable, str(CLI), *args], cwd=str(repo),
        capture_output=True, text=True, timeout=60, env=clean_env(**env),
    )


def phase(repo):
    for line in (repo / ".osengineer" / "state.yml").read_text().splitlines():
        if line.startswith("phase:"):
            return line.split(":", 1)[1].strip()
    return None


def approvals(repo):
    p = repo / ".osengineer" / "approvals.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def run_hook(name, payload, repo, **env):
    return subprocess.run(
        [sys.executable, str(HOOKS / name)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=30, cwd=str(repo), env=clean_env(**env),
    )


def is_block(proc):
    try:
        obj = json.loads(proc.stdout.strip() or "null")
    except json.JSONDecodeError:
        return False
    if not isinstance(obj, dict):
        return False
    hso = obj.get("hookSpecificOutput") or {}
    return obj.get("decision") == "block" and hso.get("permissionDecision") == "deny"


def bash(repo, command, **env):
    return run_hook("osEngineer-pre-bash-guard.py", {
        "session_id": "pg", "cwd": str(repo), "tool_name": "Bash",
        "tool_input": {"command": command},
    }, repo, **env)


def edit(repo, path, tool="Write", **env):
    return run_hook("osEngineer-pre-edit-guard.py", {
        "session_id": "pg", "cwd": str(repo), "tool_name": tool,
        "tool_input": {"file_path": str(path)},
    }, repo, **env)


class TestApproveCommand(unittest.TestCase):
    def test_valid_transition_records_who_and_when(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "discuss")
            proc = cli(repo, "approve", "plan")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(phase(repo), "plan")
            raw = (repo / ".osengineer" / "state.yml").read_text()
            self.assertRegex(raw, r"(?m)^phase_approved_by: \S+")
            self.assertRegex(raw, r"(?m)^phase_approved_at: \d{4}-\d\d-\d\dT")
            log = approvals(repo)
            self.assertEqual(len(log), 1)
            self.assertEqual((log[0]["from"], log[0]["to"]), ("discuss", "plan"))
            self.assertTrue(log[0]["by"] and log[0]["ts"])

    def test_approvals_log_is_append_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "discuss")
            add_artifact(repo, "PHASE_PLAN.md")
            self.assertEqual(cli(repo, "approve", "plan").returncode, 0)
            self.assertEqual(cli(repo, "approve", "execute").returncode, 0)
            self.assertEqual([(e["from"], e["to"]) for e in approvals(repo)],
                             [("discuss", "plan"), ("plan", "execute")])

    def test_skipping_a_phase_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "discuss")
            add_artifact(repo, "PHASE_PLAN.md")
            proc = cli(repo, "approve", "execute")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("discuss", proc.stderr)
            self.assertEqual(phase(repo), "discuss")
            self.assertEqual(approvals(repo), [])

    def test_execute_requires_a_phase_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "plan")
            proc = cli(repo, "approve", "execute")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("PHASE_PLAN.md", proc.stderr)
            self.assertEqual(phase(repo), "plan")
            add_artifact(repo, "PHASE_PLAN.md")
            self.assertEqual(cli(repo, "approve", "execute").returncode, 0)
            self.assertEqual(phase(repo), "execute")

    def test_accepted_requires_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "verify")
            proc = cli(repo, "approve", "accepted")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("VERIFICATION.md", proc.stderr)
            add_artifact(repo, "VERIFICATION.md")
            self.assertEqual(cli(repo, "approve", "accepted").returncode, 0)

    def test_micro_phase_closes_on_its_micro_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "idle")
            self.assertEqual(cli(repo, "approve", "hotfix").returncode, 0)
            self.assertNotEqual(cli(repo, "approve", "accepted").returncode, 0)
            add_artifact(repo, "MICRO_PLAN.md")
            self.assertEqual(cli(repo, "approve", "accepted").returncode, 0)

    def test_blocked_is_reachable_from_execute(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "execute")
            self.assertEqual(cli(repo, "approve", "blocked").returncode, 0)
            self.assertEqual(cli(repo, "approve", "plan").returncode, 0)

    def test_unknown_phase_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "discuss")
            proc = cli(repo, "approve", "shipped")
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(phase(repo), "discuss")

    def test_headless_refuses_every_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "discuss")
            proc = cli(repo, "approve", "plan", OSE_HEADLESS="1")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("headless", proc.stderr.lower())
            self.assertEqual(phase(repo), "discuss")
            self.assertEqual(approvals(repo), [])


class TestStateSetRoutesThroughTheGate(unittest.TestCase):
    def test_state_set_phase_is_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "discuss")
            proc = cli(repo, "state", "set", "phase", "execute")
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(phase(repo), "discuss")
            self.assertEqual(cli(repo, "state", "set", "phase", "plan").returncode, 0)
            self.assertEqual(phase(repo), "plan")
            self.assertEqual(len(approvals(repo)), 1)

    def test_state_set_phase_refused_headless(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "discuss")
            proc = cli(repo, "state", "set", "phase", "plan", OSE_HEADLESS="1")
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(phase(repo), "discuss")

    def test_approval_record_fields_cannot_be_forged(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "discuss")
            proc = cli(repo, "state", "set", "phase_approved_by", "someone")
            self.assertNotEqual(proc.returncode, 0)
            self.assertNotIn("phase_approved_by", (repo / ".osengineer" / "state.yml").read_text())

    def test_non_phase_keys_still_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "discuss")
            proc = cli(repo, "state", "set", "current_team", "coding")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("current_team: coding", (repo / ".osengineer" / "state.yml").read_text())


class TestEditGuardProtectsStateFiles(unittest.TestCase):
    def test_state_yml_unwritable_in_every_phase(self):
        for ph in ("idle", "discuss", "plan", "execute", "verify", "micro"):
            with tempfile.TemporaryDirectory() as tmp:
                repo = make_repo(tmp, ph)
                for tool in ("Write", "Edit", "MultiEdit"):
                    proc = edit(repo, repo / ".osengineer" / "state.yml", tool)
                    self.assertTrue(is_block(proc), f"{tool} of state.yml allowed in {ph}")

    def test_relative_path_and_approvals_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "plan")
            self.assertTrue(is_block(edit(repo, ".osengineer/state.yml")))
            self.assertTrue(is_block(edit(repo, repo / ".osengineer" / "approvals.jsonl")))

    def test_bypass_does_not_lift_it_and_is_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "plan")
            proc = edit(repo, repo / ".osengineer" / "state.yml", OSE_BYPASS="1")
            self.assertTrue(is_block(proc), "OSE_BYPASS let the agent edit state.yml")
            log = (repo / ".osengineer" / "bypass-log.jsonl").read_text()
            self.assertIn("not honoured", log)

    def test_other_osengineer_files_stay_editable_in_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "plan")
            self.assertFalse(is_block(edit(repo, repo / ".osengineer" / "notes.md")))

    def test_planning_block_message_asks_the_human_to_approve(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "plan")
            proc = edit(repo, repo / "src" / "main.py")
            self.assertTrue(is_block(proc))
            reason = json.loads(proc.stdout)["reason"]
            self.assertNotIn("state set phase", reason)
            self.assertIn("osengineer approve execute", reason)
            self.assertIn("human", reason.lower())


AGENT_TRANSITIONS = [
    "osengineer approve execute",
    ".osengineer/bin/osengineer approve plan",
    "python3 bin/osengineer approve accepted",
    "cd sub && osengineer state set phase execute",
    "osengineer state set phase_approved_by me",
    "echo 'phase: execute' > .osengineer/state.yml",
    "printf 'phase: execute\\n' >> state.yml",
    "sed -i 's/plan/execute/' .osengineer/state.yml",
    "python3 -c \"open('.osengineer/state.yml','w').write('phase: execute')\"",
    "echo '{}' | tee -a .osengineer/approvals.jsonl",
    "cp /tmp/x .osengineer/state.yml",
    "git checkout -- .osengineer/state.yml",
    "python3 -c 'from osengineer_common import write_state_field'",
]

ALLOWED = [
    "osengineer state",
    "cat .osengineer/state.yml",
    "grep phase .osengineer/state.yml",
    "git add .osengineer/state.yml",
    "git diff .osengineer/approvals.jsonl",
    "osengineer state set current_team coding",
    "osengineer evolve accept EP-001 --pattern-slug x",
]


class TestBashGuardRefusesAgentTransitions(unittest.TestCase):
    def test_transition_routes_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "plan")
            for cmd in AGENT_TRANSITIONS:
                self.assertTrue(is_block(bash(repo, cmd)), f"agent could run: {cmd}")

    def test_reads_and_other_state_keys_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "plan")
            for cmd in ALLOWED:
                self.assertFalse(is_block(bash(repo, cmd)), f"false positive: {cmd}")

    def test_bypass_does_not_lift_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "plan")
            proc = bash(repo, "osengineer approve execute", OSE_BYPASS="1")
            self.assertTrue(is_block(proc), "OSE_BYPASS let the agent approve its own phase")
            log = (repo / ".osengineer" / "bypass-log.jsonl").read_text()
            self.assertIn("not honoured", log)

    def test_block_holds_in_every_phase(self):
        for ph in ("idle", "discuss", "execute", "verify", "accepted", "blocked"):
            with tempfile.TemporaryDirectory() as tmp:
                repo = make_repo(tmp, ph)
                self.assertTrue(is_block(bash(repo, "osengineer approve plan")), ph)


class TestCodexGetsTheSameRefusal(unittest.TestCase):
    def run_adapter(self, script, payload, repo):
        return subprocess.run(
            [sys.executable, str(ADAPTER), script], input=json.dumps(payload),
            capture_output=True, text=True, timeout=60, cwd=str(repo), env=clean_env(),
        )

    def test_exec_command_argv_approve_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "plan")
            proc = self.run_adapter("osEngineer-pre-bash-guard.py", {
                "cwd": str(repo), "hook_event_name": "PreToolUse", "tool_name": "exec_command",
                "tool_input": {"command": ["osengineer", "approve", "execute"]},
            }, repo)
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)

    def test_apply_patch_to_state_yml_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, "execute")
            patch = ("*** Begin Patch\n*** Update File: .osengineer/state.yml\n"
                     "@@\n-phase: execute\n+phase: accepted\n*** End Patch\n")
            proc = self.run_adapter("osEngineer-pre-edit-guard.py", {
                "cwd": str(repo), "hook_event_name": "PreToolUse", "tool_name": "apply_patch",
                "tool_input": {"command": patch},
            }, repo)
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
