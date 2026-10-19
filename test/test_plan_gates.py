"""PHASE_PLAN.md is validated where it is consumed, and fails closed there:
headless `osengineer run`, plan-gated slash commands (prompt-guard), and
edits during execute (pre-edit-guard)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_headless_run import HeadlessBase, make_repo, run_cli

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"
INVALID = '---\n{"phase_id": "phase-001-test", "goal": "Missing the task budgets.", ' \
          '"tasks": [{"id": "T1", "description": "d", "acceptance": "a"}]}\n---\n'


def commit_all(repo):
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "plan"], cwd=repo, check=True)


class HeadlessRunValidatesThePlan(HeadlessBase):
    def test_invalid_plan_refuses_before_spawning(self):
        repo = make_repo(self.tmp)
        (repo / "planning/active/phase-1/PHASE_PLAN.md").write_text(INVALID)
        commit_all(repo)
        proc = run_cli(repo, ["run", "fix", "T"], self.env())
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("tasks[0].budget is required", proc.stderr)
        self.assertFalse(self.record.exists(), "harness spawned with an invalid plan")

    def test_blocked_phase_refuses_before_spawning(self):
        repo = make_repo(self.tmp, phase="blocked")
        proc = run_cli(repo, ["run", "fix", "T"], self.env())
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("blocked", proc.stderr)
        self.assertFalse(self.record.exists(), "harness spawned while blocked")


class HooksValidateThePlan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / ".osengineer").mkdir()
        self.plan_dir = self.repo / "planning/active/phase-1"
        self.plan_dir.mkdir(parents=True)
        (self.plan_dir / "PHASE_PLAN.md").write_text(INVALID)

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, name, payload, phase):
        (self.repo / ".osengineer/state.yml").write_text(f"phase: {phase}\ncurrent_team: null\n")
        env = dict(os.environ)
        env.pop("OSE_BYPASS", None)
        return subprocess.run([sys.executable, str(HOOKS / name)], text=True, capture_output=True, env=env,
                              input=json.dumps({"session_id": "gate", "cwd": str(self.repo), **payload}))

    def test_plan_gated_command_blocks_on_an_invalid_plan(self):
        proc = self.hook("osEngineer-prompt-guard.py", {"prompt": "/osEngineer:fix T-1"}, "plan")
        out = json.loads(proc.stdout)
        self.assertEqual(out["decision"], "block")
        self.assertIn("tasks[0].budget", out["reason"])

    def test_execute_edits_block_on_an_invalid_plan(self):
        edit = {"tool_name": "Edit", "tool_input": {"file_path": str(self.repo / "src/a.py")}}
        proc = self.hook("osEngineer-pre-edit-guard.py", edit, "execute")
        out = json.loads(proc.stdout)
        self.assertEqual(out["decision"], "block")
        self.assertIn("tasks[0].budget", out["reason"])
        # Fixing the plan itself stays possible.
        plan_edit = {"tool_name": "Edit", "tool_input": {"file_path": str(self.plan_dir / "PHASE_PLAN.md")}}
        self.assertEqual(self.hook("osEngineer-pre-edit-guard.py", plan_edit, "execute").stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
