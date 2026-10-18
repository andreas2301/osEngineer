"""Offline detectors report facts; profile.json maps them to named handlers."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from repo_profile import detect
from repo_profile.install import install, uninstall, PROFILE_REL

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "osengineer"


def no_tools(_name):
    return None


class Detectors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def touch(self, *names):
        for name in names:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n")

    def profile(self, value):
        self.touch(PROFILE_REL)
        (self.repo / PROFILE_REL).write_text(json.dumps(value))

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if k != "OSE_BYPASS"}
        return subprocess.run([sys.executable, str(CLI), "profile", *args, "--repo", str(self.repo)],
                              capture_output=True, text=True, env=env)

    def test_empty_repo_has_no_facts(self):
        self.assertEqual(detect.detect(self.repo, which=no_tools), [])

    def test_file_and_tool_facts(self):
        self.touch("POLICY.md", "EVAL_POLICY.json", ".osengineer/skill-registry.json",
                   ".github/workflows/ci.yml", "package.json", "pyproject.toml", "go.mod", "Cargo.toml")
        (self.repo / ".claude").mkdir()
        tools = {"gh", "op", "codex", "kimi"}
        facts = detect.detect(self.repo, which=lambda n: "/bin/" + n if n in tools else None)
        self.assertEqual(facts, sorted([
            "policy-file", "eval-policy", "skill-registry", "ci:github-actions",
            "package-manager:npm", "package-manager:pip", "package-manager:go", "package-manager:cargo",
            "harness:claude", "harness:codex", "harness:kimi", "cli:gh", "cli:op"]))

    def test_detectors_follow_configured_paths(self):
        self.profile({"policy": "AGENTS.md", "eval": {"policy": "evals/policy.json"}})
        self.touch("POLICY.md", "EVAL_POLICY.json")
        self.assertEqual(detect.detect(self.repo, which=no_tools), ["profile-json"])
        self.touch("AGENTS.md", "evals/policy.json")
        self.assertEqual(detect.detect(self.repo, which=no_tools), ["eval-policy", "policy-file", "profile-json"])

    def test_known_facts_are_proposed_and_unknown_facts_only_reported(self):
        self.touch("EVAL_POLICY.json", ".github/workflows/ci.yml")
        report = detect.report(self.repo, which=no_tools)
        rows = {r["fact"]: r for r in report["facts"]}
        self.assertEqual(rows["eval-policy"], {"fact": "eval-policy", "status": "unconfigured", "handler": "eval.gate"})
        self.assertEqual(rows["ci:github-actions"], {"fact": "ci:github-actions", "status": "unhandled", "handler": None})
        self.assertEqual(report["proposed"]["handlers"], {"eval-policy": {"handler": "eval.gate", "enabled": True}})
        self.assertEqual(report["unhandled"], ["ci:github-actions"])

    def test_configured_disabled_and_missing_entries(self):
        self.touch("EVAL_POLICY.json", "package.json")
        self.profile({"handlers": {"eval-policy": {"handler": "eval.gate", "enabled": True},
                                   "package-manager:npm": {"enabled": False},
                                   "cli:gh": {"handler": "integrations.github", "enabled": True}}})
        rows = {r["fact"]: r["status"] for r in detect.report(self.repo, which=no_tools)["facts"]}
        self.assertEqual(rows, {"eval-policy": "handled", "package-manager:npm": "acknowledged",
                                "profile-json": "unconfigured", "cli:gh": "not-detected"})

    def test_detect_cli_never_writes_without_flag(self):
        self.touch("EVAL_POLICY.json", ".github/workflows/ci.yml")
        result = self.cli("detect")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "detected")
        self.assertFalse((self.repo / PROFILE_REL).exists())
        result = self.cli("detect", "--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        written = json.loads((self.repo / PROFILE_REL).read_text())
        self.assertEqual(written["handlers"]["eval-policy"], {"handler": "eval.gate", "enabled": True})
        self.assertNotIn("ci:github-actions", written["handlers"])
        self.assertNotIn("profile", written)

    def test_doctor_flags_unhandled_and_unconfigured_facts(self):
        self.touch(".github/workflows/ci.yml")
        result = self.cli("doctor")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["unhandled"], ["ci:github-actions"])
        self.profile({"handlers": {"ci:github-actions": {"enabled": False}}})
        result = self.cli("doctor")
        self.assertEqual(result.returncode, 1, result.stdout)  # profile-json itself is unconfigured
        self.cli("detect", "--write")
        self.assertEqual(self.cli("doctor").returncode, 0)

    def test_invalid_profile_fails_closed(self):
        self.profile({"handlers": {"eval-policy": {"handler": "nope", "enabled": True}}})
        for verb in ("detect", "doctor"):
            result = self.cli(verb)
            self.assertEqual(result.returncode, 1)
            self.assertIn("handlers.eval-policy.handler", json.loads(result.stdout)["reason"])


class InstallerKeepsUserProfileKeys(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / "POLICY.md").write_text("policy\n")
        (self.repo / "EVAL_POLICY.json").write_text("{}\n")

    def tearDown(self):
        self.tmp.cleanup()

    def read(self):
        return json.loads((self.repo / PROFILE_REL).read_text())

    def test_detect_write_before_install(self):
        detect.write(self.repo, which=no_tools)
        install(self.repo)
        profile = self.read()
        self.assertEqual(profile["profile"], "repo")
        self.assertEqual(profile["handlers"]["eval-policy"]["handler"], "eval.gate")
        uninstall(self.repo)
        profile = self.read()
        self.assertNotIn("profile", profile)
        self.assertIn("eval-policy", profile["handlers"])

    def test_detect_write_after_install_keeps_reinstall_and_uninstall_working(self):
        install(self.repo)
        detect.write(self.repo, which=no_tools)
        install(self.repo)
        self.assertIn("eval-policy", self.read()["handlers"])
        self.assertEqual(uninstall(self.repo)["status"], "uninstalled")
        self.assertNotIn("profile", self.read())

    def test_plain_install_uninstall_leaves_no_profile(self):
        install(self.repo)
        uninstall(self.repo)
        self.assertFalse((self.repo / PROFILE_REL).exists())

    def test_install_refuses_to_override_a_configured_policy(self):
        (self.repo / ".osengineer").mkdir()
        (self.repo / PROFILE_REL).write_text('{"policy": "AGENTS.md"}')
        with self.assertRaises(ValueError) as caught:
            install(self.repo)
        self.assertIn("policy", str(caught.exception))
        self.assertEqual(self.read(), {"policy": "AGENTS.md"})


if __name__ == "__main__":
    unittest.main()
