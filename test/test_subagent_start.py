"""SubagentStart re-injects osEngineer rules and state into every subagent.

SessionStart context never reaches a subagent, so without this hook a
subagent works without the agent rules or the current phase/team. The hook
emits the same state banner the session-start hook computes, plus the rules
from their single source, templates/agent-rules.md.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"
HOOK = HOOKS / "osEngineer-subagent-start.py"
SESSION_HOOK = HOOKS / "osEngineer-session-start.py"
RULES = ROOT / "templates" / "agent-rules.md"
INSTALL = ROOT / "install.sh"
UNINSTALL = ROOT / "uninstall.sh"


def run(hook, payload):
    return subprocess.run([sys.executable, str(hook)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=30)


class SubagentStartHook(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="ose-sub-"))
        (self.repo / ".osengineer").mkdir()
        (self.repo / ".osengineer" / "state.yml").write_text(
            "phase: execute\ncurrent_team: coding\nbudget_used: 0\n")
        self.payload = {"session_id": "s", "cwd": str(self.repo),
                        "hook_event_name": "SubagentStart",
                        "agent_id": "agent-1", "agent_type": "Explore"}

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def context(self, hook, payload):
        proc = run(hook, payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)["hookSpecificOutput"]

    def test_injects_state_and_rules_as_subagent_context(self):
        hso = self.context(HOOK, self.payload)
        self.assertEqual(hso["hookEventName"], "SubagentStart")
        ctx = hso["additionalContext"]
        self.assertIn("- phase: execute", ctx)
        self.assertIn("- team: coding", ctx)
        self.assertIn(RULES.read_text().strip(), ctx)

    def test_reuses_the_session_start_banner(self):
        banner = self.context(SESSION_HOOK, dict(self.payload, hook_event_name="SessionStart"))
        ctx = self.context(HOOK, self.payload)["additionalContext"]
        self.assertTrue(ctx.startswith(banner["additionalContext"]), ctx)

    def test_silent_outside_an_osengineer_repo(self):
        outside = Path(tempfile.mkdtemp(prefix="ose-none-"))
        try:
            proc = run(HOOK, dict(self.payload, cwd=str(outside)))
        finally:
            shutil.rmtree(outside, ignore_errors=True)
        self.assertEqual((proc.returncode, proc.stdout), (0, ""), proc.stderr)

    def test_malformed_payload_fails_loudly(self):
        proc = subprocess.run([sys.executable, str(HOOK)], input="{",
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("invalid hook input", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


class SubagentStartWiring(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ose-subwire-"))
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.repo = self.tmp / "repo"
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sh(self, script):
        env = dict(os.environ, OSE_NONINTERACTIVE="1", HOME=str(self.home), RUNTIMES="claude")
        env.pop("CI", None)
        proc = subprocess.run(["bash", str(script), str(self.repo)], capture_output=True,
                              text=True, timeout=300, env=env, stdin=subprocess.DEVNULL)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def subagent_commands(self):
        cfg = self.repo / ".claude" / "settings.json"
        if not cfg.exists():
            return []
        groups = json.loads(cfg.read_text()).get("hooks", {}).get("SubagentStart", [])
        return [h["command"] for g in groups for h in g["hooks"]]

    def test_claude_wiring_is_idempotent_and_uninstalled(self):
        self.sh(INSTALL)
        self.sh(INSTALL)
        cmds = self.subagent_commands()
        self.assertEqual(len(cmds), 1, cmds)
        self.assertIn("osEngineer-subagent-start.py", cmds[0])
        self.sh(UNINSTALL)
        self.assertEqual(self.subagent_commands(), [])


if __name__ == "__main__":
    unittest.main()
