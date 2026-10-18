"""osEngineer must wire Codex CLI where Codex actually looks.

Checked against the Codex docs on 2026-10-18 (learn.chatgpt.com/docs/hooks,
/docs/build-skills, developers.openai.com/codex/guides/agents-md):

  * Hooks load from ~/.codex/hooks.json, ~/.codex/config.toml,
    <repo>/.codex/hooks.json and <repo>/.codex/config.toml. Project hooks are
    per repo (like Claude's .claude/settings.json), so no global ledger is
    needed. They run only once the project .codex/ layer and each hook are
    trusted (/hooks), and a changed command must be trusted again.
  * hooks.json nests event -> [{matcher, hooks: [{type, command, timeout}]}].
    There is no env block, so OSENGINEER_HOME rides in the command.
  * Edits are reported as tool_name "apply_patch"; the matcher accepts
    apply_patch, Edit or Write.
  * Skills are discovered under .agents/skills/<name>/SKILL.md.
  * AGENTS.md at the repo root is read natively; no copy is needed.
  * Custom agents are TOML files in .codex/agents/, so the Markdown agent
    copies Claude uses would be inert there.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.sh"
UNINSTALL = ROOT / "uninstall.sh"
COMMANDS = ROOT / "commands"

CODEX_EVENTS = {
    "PreToolUse", "PermissionRequest", "PostToolUse", "PreCompact", "PostCompact",
    "UserPromptSubmit", "SubagentStop", "Stop", "Interrupt", "SessionStart",
    "SubagentStart", "SessionEnd",
}
EXPECTED_SCRIPTS = {
    "osEngineer-prompt-guard.py",
    "osEngineer-pre-edit-guard.py",
    "osEngineer-pre-bash-guard.py",
    "osEngineer-session-start.py",
}
FOREIGN = {"type": "command", "command": "python3 /opt/other/unrelated-guard.py", "timeout": 30}


def env_for(home):
    env = dict(os.environ)
    env.update({"OSE_NONINTERACTIVE": "1", "HOME": str(home)})
    env.pop("CI", None)
    return env


def run_install(repo, home, runtimes="claude codex"):
    env = env_for(home)
    env["RUNTIMES"] = runtimes
    return subprocess.run(["bash", str(INSTALL), str(repo)],
                          capture_output=True, text=True, timeout=300, env=env)


def run_uninstall(repo, home):
    return subprocess.run(["bash", str(UNINSTALL), str(repo)],
                          capture_output=True, text=True, timeout=300, env=env_for(home))


def make_git_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True)
    (path / "main.py").write_text("print('x')\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True)
    return path


def verbs():
    out = []
    for src in sorted(COMMANDS.glob("osEngineer-*.md")):
        for line in src.read_text().splitlines():
            if line.startswith("name: osEngineer:"):
                out.append((line.split(":", 2)[2].strip(), src))
                break
    return out


class CodexBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = Path(self.tmp) / "home"
        self.home.mkdir()
        self.repo = make_git_repo(Path(self.tmp) / "repo")
        (self.repo / ".codex").mkdir()
        self.hooks_json = self.repo / ".codex" / "hooks.json"
        self.hooks_json.write_text(json.dumps({"hooks": {
            "PreToolUse": [{"matcher": "Bash", "hooks": [FOREIGN]}],
        }}))
        foreign_skill = self.repo / ".agents" / "skills" / "mine"
        foreign_skill.mkdir(parents=True)
        (foreign_skill / "SKILL.md").write_text("---\nname: mine\ndescription: user skill\n---\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def install(self):
        proc = run_install(self.repo, self.home)
        self.assertEqual(proc.returncode, 0, f"install failed:\n{proc.stdout}\n{proc.stderr}")
        return proc

    def handlers(self):
        if not self.hooks_json.exists():
            return []
        data = json.loads(self.hooks_json.read_text())
        out = []
        for event, groups in (data.get("hooks") or {}).items():
            for group in groups:
                for h in group.get("hooks", []):
                    out.append((event, group.get("matcher"), h))
        return out

    def ose_handlers(self):
        return [x for x in self.handlers() if "osEngineer-" in x[2].get("command", "")]


class TestCodexHooksAreWired(CodexBase):
    def test_hooks_land_in_project_codex_hooks_json(self):
        self.install()
        self.assertTrue(self.ose_handlers(), "no osEngineer hooks in .codex/hooks.json")

    def test_expected_guards_are_wired_on_valid_events(self):
        self.install()
        wired = set()
        for event, _matcher, h in self.ose_handlers():
            self.assertIn(event, CODEX_EVENTS)
            self.assertEqual(h.get("type"), "command")
            wired.add(h["command"].split()[-1].strip('"'))
        self.assertEqual(EXPECTED_SCRIPTS - wired, set(), f"guards not wired on Codex: {wired}")

    def test_edit_guard_matches_apply_patch(self):
        self.install()
        matchers = [m for _e, m, h in self.ose_handlers() if "pre-edit-guard" in h["command"]]
        self.assertTrue(matchers and all("apply_patch" in (m or "") for m in matchers),
                        f"Codex reports edits as apply_patch: {matchers}")

    def test_commands_route_through_the_adapter_and_bake_home(self):
        self.install()
        self.assertTrue(self.ose_handlers(), "precondition: hooks wired")
        for _e, _m, h in self.ose_handlers():
            self.assertIn("hooks/lib/codex_hook.py", h["command"])
            self.assertIn("OSENGINEER_HOME=", h["command"], "Codex hooks.json has no env block")

    def test_foreign_hooks_survive(self):
        self.install()
        self.assertIn(FOREIGN, [h for _e, _m, h in self.handlers()])

    def test_no_inert_codex_files(self):
        self.install()
        self.assertFalse((self.repo / ".codex" / "settings.json").exists(), "Codex never reads settings.json")
        self.assertFalse(list((self.repo / ".codex").glob("agents/*.md")),
                         "Codex agents are TOML; Markdown copies are inert")

    def test_reinstall_does_not_duplicate(self):
        self.install()
        first = self.ose_handlers()
        self.assertTrue(first, "precondition: hooks wired")
        self.install()
        self.assertEqual(len(first), len(self.ose_handlers()))

    def test_upgrade_replaces_stale_osengineer_entries(self):
        stale = {"type": "command", "command": "python3 /old/checkout/hooks/osEngineer-pre-bash-guard.py"}
        data = json.loads(self.hooks_json.read_text())
        data["hooks"]["PreToolUse"].append({"matcher": "Bash", "hooks": [stale]})
        self.hooks_json.write_text(json.dumps(data))
        self.install()
        commands = [h["command"] for _e, _m, h in self.handlers()]
        self.assertNotIn(stale["command"], commands)

    def test_install_warns_that_codex_hooks_need_trust(self):
        proc = self.install()
        self.assertRegex(proc.stdout + proc.stderr, r"(?i)codex.*trust.*/hooks",
                         "Codex skips untrusted hooks silently; the user must be told to trust them")


class TestCodexSkills(CodexBase):
    def test_commands_install_as_codex_skills_verbatim(self):
        self.install()
        for verb, src in verbs():
            dst = self.repo / ".agents" / "skills" / verb / "SKILL.md"
            self.assertTrue(dst.exists(), f"missing Codex skill {dst}")
            self.assertEqual(dst.read_text(), src.read_text())


class TestCodexUnwiring(CodexBase):
    def test_uninstall_removes_only_osengineer_wiring(self):
        self.install()
        self.assertTrue(self.ose_handlers(), "precondition: hooks wired")
        proc = run_uninstall(self.repo, self.home)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.ose_handlers(), [])
        self.assertIn(FOREIGN, [h for _e, _m, h in self.handlers()])
        for verb, _src in verbs():
            self.assertFalse((self.repo / ".agents" / "skills" / verb).exists(), verb)
        self.assertTrue((self.repo / ".agents" / "skills" / "mine" / "SKILL.md").exists())

    def test_uninstall_deletes_hooks_json_it_alone_populated(self):
        self.hooks_json.unlink()
        self.install()
        self.assertTrue(self.ose_handlers(), "precondition: hooks wired")
        run_uninstall(self.repo, self.home)
        self.assertFalse(self.hooks_json.exists())

    def test_uninstall_keeps_a_user_modified_skill(self):
        self.install()
        verb = verbs()[0][0]
        edited = self.repo / ".agents" / "skills" / verb / "SKILL.md"
        edited.write_text(edited.read_text() + "\nlocal note\n")
        run_uninstall(self.repo, self.home)
        self.assertTrue(edited.exists(), "uninstall deleted a user-modified skill")


class TestCodexIsOffered(unittest.TestCase):
    def test_codex_offered_in_the_runtime_menu(self):
        self.assertIn("Codex CLI", INSTALL.read_text())


class TestCommandsFitSkillLimits(unittest.TestCase):
    """Codex and Claude skills cap name at 64 and description at 1024 chars."""

    def test_command_frontmatter_fits(self):
        for src in sorted(COMMANDS.glob("osEngineer-*.md")):
            fm = src.read_text().split("---", 2)[1]
            lines = fm.splitlines()
            desc, collecting = [], False
            for line in lines:
                if line.startswith("description:"):
                    rest = line.split(":", 1)[1].strip()
                    collecting = rest in (">", ">-", "|", "|-")
                    if not collecting:
                        desc.append(rest)
                elif collecting and line.startswith("  "):
                    desc.append(line.strip())
                elif collecting:
                    collecting = False
            name = next(line.split(":", 1)[1].strip() for line in lines if line.startswith("name:"))
            self.assertLessEqual(len(name), 64, src.name)
            self.assertLessEqual(len(" ".join(desc)), 1024, f"{src.name} description too long for a skill")


if __name__ == "__main__":
    unittest.main()
