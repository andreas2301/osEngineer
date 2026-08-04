"""Integration regression tests for install.sh / uninstall.sh / post-commit hook.

Guards three fixes:
  * install.sh must not SIGPIPE-abort on repos with >200 source files.
  * uninstall.sh must remove agent files that install.sh copied, even though
    the source agents are dir-style (agents/<role>/AGENT.md).
  * post-commit hook must invoke `graphify update` without the removed
    --ast-only flag.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.sh"
UNINSTALL = ROOT / "uninstall.sh"
POST_COMMIT = ROOT / "hooks" / "osEngineer-post-commit.sh"


def sh(script, arg, home):
    """Run a skill shell script non-interactively with an isolated HOME so
    `git config --global` writes don't touch the real user config."""
    env = dict(os.environ)
    env["OSE_NONINTERACTIVE"] = "1"
    env["HOME"] = str(home)
    return subprocess.run(
        ["bash", str(script), str(arg)],
        capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL,
    )


class _RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ose-repo-"))
        self.home = Path(tempfile.mkdtemp(prefix="ose-home-"))
        subprocess.run(["git", "init", "-q", str(self.tmp)], check=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.home, ignore_errors=True)


class TestInstallLargeRepo(_RepoCase):
    def test_large_repo_gets_full_install(self):
        # >200 source files: the `find | head -200` pipeline SIGPIPEs, which
        # (pre-fix) aborted init_repo before AGENTS.md / CLAUDE.md were written.
        for i in range(500):
            (self.tmp / f"f{i}.go").write_text(f"package p\nfunc F{i}() {{}}\n")
        r = sh(INSTALL, self.tmp, self.home)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertTrue((self.tmp / "AGENTS.md").exists(), "AGENTS.md missing (SIGPIPE regression)")
        self.assertTrue((self.tmp / "CLAUDE.md").exists(), "CLAUDE.md missing (SIGPIPE regression)")
        self.assertIn("project_classification: large", (self.tmp / "AGENTS.md").read_text())


class TestUninstallRemovesAgents(_RepoCase):
    def test_install_then_uninstall_clears_agents(self):
        (self.tmp / "main.go").write_text("package main\n")
        ri = sh(INSTALL, self.tmp, self.home)
        self.assertEqual(ri.returncode, 0, ri.stderr)
        agents_dir = self.tmp / ".claude" / "agents"
        self.assertGreaterEqual(len(list(agents_dir.glob("*.md"))), 17, "install copied no agents")

        ru = sh(UNINSTALL, self.tmp, self.home)
        self.assertEqual(ru.returncode, 0, ru.stderr)
        remaining = list(agents_dir.glob("*.md")) if agents_dir.exists() else []
        self.assertEqual(remaining, [], f"uninstall left agent files (dir-style regression): {remaining}")
        self.assertFalse((self.tmp / ".osengineer").exists(), ".osengineer/ not removed by uninstall")


class TestPostCommitGraphify(unittest.TestCase):
    def test_no_ast_only_flag(self):
        src = POST_COMMIT.read_text()
        self.assertIn("graphify update .", src)
        for line in src.splitlines():
            if line.strip().startswith("graphify update"):
                self.assertNotIn("--ast-only", line, "post-commit still passes removed --ast-only flag")


if __name__ == "__main__":
    unittest.main()
