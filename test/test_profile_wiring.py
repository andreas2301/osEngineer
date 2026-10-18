"""Hooks, runtime and installer read settings only through repo_profile.config."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from repo_profile import install as profile_install
from repo_runtime.runtime import ContractError, load_contract

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"


class HookWiring(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".osengineer").mkdir()
        (self.root / ".osengineer/state.yml").write_text("phase: execute\n")
        self.session = "ose-test-" + uuid.uuid4().hex

    def tearDown(self):
        for path in Path(tempfile.gettempdir()).glob(f"claude-*{self.session}*"):
            path.unlink(missing_ok=True)
        self.tmp.cleanup()

    def profile(self, **settings):
        (self.root / ".osengineer/profile.json").write_text(json.dumps(settings))

    def metrics(self, remaining):
        (Path(tempfile.gettempdir()) / f"claude-ctx-{self.session}.json").write_text(json.dumps({
            "session_id": self.session, "remaining_percentage": remaining,
            "used_pct": 100 - remaining, "timestamp": int(time.time())}))

    def hook(self, name, payload):
        env = dict(os.environ)
        env.pop("OSE_BYPASS", None)
        env.pop("OSENGINEER_HOME", None)
        payload = {"cwd": str(self.root), "session_id": self.session, **payload}
        return subprocess.run([sys.executable, str(HOOKS / f"osEngineer-{name}.py")],
                              input=json.dumps(payload), text=True, capture_output=True, env=env)

    def registry(self, *rows):
        (self.root / ".osengineer/skill-registry.json").write_text(json.dumps({"skills": list(rows)}))

    def test_invalid_value_blocks_instead_of_falling_back(self):
        self.profile(profile="repo", planDirectory="/etc")
        result = self.hook("pre-edit-guard", {"tool_name": "Edit", "tool_input": {"file_path": "src/a.py"}})
        self.assertEqual(result.returncode, 2)
        self.assertIn("planDirectory", result.stderr)
        self.assertEqual(json.loads(result.stdout)["decision"], "block")

    def test_post_tool_warning_threshold_is_configurable(self):
        self.profile(context={"warnPct": 50, "criticalPct": 10})
        self.metrics(45)
        self.assertIn("WARNING", self.hook("post-tool", {}).stdout)
        self.metrics(5)
        self.assertIn("CRITICAL", self.hook("post-tool", {}).stdout)

    def test_repo_profile_prompt_uses_the_shared_warning_threshold(self):
        # Unified on post-tool's 35%: 38% remaining is no longer a warning.
        self.profile(profile="repo")
        self.metrics(38)
        self.assertNotIn("Context warning", self.hook("prompt-guard", {"prompt": "hello"}).stdout)
        self.metrics(30)
        self.assertIn("Context warning", self.hook("prompt-guard", {"prompt": "hello again"}).stdout)

    def test_generic_reinjection_threshold_is_configurable(self):
        self.metrics(38)
        self.assertIn("DEGRADATION", self.hook("prompt-guard", {"prompt": "hi"}).stdout)
        self.profile(context={"reinjectPct": 30})
        self.assertNotIn("DEGRADATION", self.hook("prompt-guard", {"prompt": "hi"}).stdout)

    def test_routing_rules_are_configurable(self):
        self.registry({"name": "judge", "canonical": ".agents/skills/judge"},
                      {"name": "dispatch", "canonical": ".claude/skills/dispatch",
                       "projections": {"codex": ".agents/skills/dispatch"}},
                      {"name": "deploy", "canonical": ".claude/skills/deploy"})
        self.profile(profile="repo", routing={"excludeNamePattern": "", "dispatchWords": ["ship"],
                                              "maxHints": 1, "projection": None})
        out = self.hook("prompt-guard", {"prompt": "ship it with judge"}).stdout
        self.assertIn("- judge: .agents/skills/judge", out)
        self.assertNotIn("dispatch", out)
        out = self.hook("prompt-guard", {"prompt": "ship the dispatch and deploy"}).stdout
        self.assertIn("- dispatch: .claude/skills/dispatch", out)
        self.assertNotIn("- deploy", out)
        # "workflow" is no longer a dispatch word once dispatchWords is set.
        self.assertNotIn("- dispatch", self.hook("prompt-guard", {"prompt": "run the workflow now"}).stdout)


class RuntimeAndInstallWiring(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / ".osengineer").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_runtime_rejects_an_invalid_profile(self):
        (self.repo / ".osengineer/profile.json").write_text('{"policy": "../POLICY.md"}')
        contract = Path(self.tmp.name) / "c.json"
        contract.write_text("{}")
        with self.assertRaises(ContractError) as caught:
            load_contract(contract, self.repo)
        self.assertIn("policy", str(caught.exception))

    def test_installer_defaults_come_from_the_loader(self):
        from repo_profile import config
        cfg = profile_install.profile_config()
        for key in ("policy", "planDirectory", "skillRegistry"):
            self.assertEqual(cfg[key], config.DEFAULTS[key])
        with self.assertRaises(config.ProfileError):
            profile_install.profile_config(plan_dir="/abs")

    def test_profile_version_is_the_release_version(self):
        (self.repo / "POLICY.md").write_text("policy\n")
        profile_install.install(self.repo)
        manifest = json.loads((self.repo / profile_install.MANIFEST_REL).read_text())
        self.assertEqual(manifest["profileVersion"], (ROOT / "VERSION").read_text().strip())


if __name__ == "__main__":
    unittest.main()
