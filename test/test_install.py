"""Integration regression tests for install.sh / uninstall.sh / post-commit hook.

Guards three fixes:
  * install.sh must not SIGPIPE-abort on repos with >200 source files.
  * uninstall.sh must remove agent files that install.sh copied, even though
    the source agents are dir-style (agents/<role>/AGENT.md).
  * post-commit hook must invoke `graphify update` without the removed
    --ast-only flag.
"""
import os
import re
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


class TestAgentReferencesCopied(_RepoCase):
    """agents/<role>/references/*.md must land beside the installed agent file.

    Pre-fix install.sh copied only agents/<role>/AGENT.md, leaving every
    `](references/x.md)` link dangling — 131 dead links across 17 agents in one
    consuming repo. Basenames collide across agents (output-format.md is in 5),
    so the destination is namespaced per role and the links are rewritten.
    """

    def test_references_are_installed_and_links_resolve(self):
        (self.tmp / "main.go").write_text("package main\n")
        r = sh(INSTALL, self.tmp, self.home)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)

        agents_dir = self.tmp / ".claude" / "agents"
        refs_root = agents_dir / "references"
        self.assertTrue(refs_root.is_dir(), "references/ tree was not installed at all")

        # Every references/<x>.md link in every installed agent must resolve.
        link_re = re.compile(r"\]\((\./)?(references/[A-Za-z0-9._/-]+\.md)\)")
        dangling, checked = [], 0
        for agent_file in agents_dir.glob("*.md"):
            for m in link_re.finditer(agent_file.read_text()):
                checked += 1
                if not (agents_dir / m.group(2)).is_file():
                    dangling.append(f"{agent_file.name} -> {m.group(2)}")
        self.assertGreater(checked, 0, "no references/ links found — did the agent sources change?")
        self.assertEqual(dangling, [], f"{len(dangling)} dangling reference link(s): {dangling[:5]}")

    def test_colliding_basenames_do_not_clobber(self):
        # output-format.md exists in several agents with DIFFERENT content; a
        # flat destination would silently keep only the last one copied.
        srcs = sorted(ROOT.glob("agents/*/references/output-format.md"))
        if len(srcs) < 2:
            self.skipTest("no colliding reference basename in the current agent set")
        (self.tmp / "main.go").write_text("package main\n")
        self.assertEqual(sh(INSTALL, self.tmp, self.home).returncode, 0)

        refs_root = self.tmp / ".claude" / "agents" / "references"
        for src in srcs:
            role = src.parent.parent.name
            dst = refs_root / role / "output-format.md"
            if dst.exists():
                self.assertEqual(
                    dst.read_text(), src.read_text(),
                    f"{role}/output-format.md was clobbered by another agent's copy",
                )

    def test_uninstall_removes_references(self):
        (self.tmp / "main.go").write_text("package main\n")
        self.assertEqual(sh(INSTALL, self.tmp, self.home).returncode, 0)
        refs_root = self.tmp / ".claude" / "agents" / "references"
        self.assertTrue(refs_root.is_dir())

        self.assertEqual(sh(UNINSTALL, self.tmp, self.home).returncode, 0)
        leftovers = list(refs_root.rglob("*.md")) if refs_root.exists() else []
        self.assertEqual(leftovers, [], f"uninstall left reference files: {leftovers[:5]}")


class TestAppendStripsFrontmatter(_RepoCase):
    """Appending onto an existing agent file must not inject a 2nd frontmatter.

    A raw `cat` of the source AGENT.md put a second `---` YAML block mid-body,
    where the loader ignores it but the model reads it as a competing mandate.
    Observed 2026-08-04 as duplicate name:/role:/scope: keys at developer.md:185.
    """

    def test_append_does_not_duplicate_frontmatter(self):
        (self.tmp / "main.go").write_text("package main\n")
        self.assertEqual(sh(INSTALL, self.tmp, self.home).returncode, 0)

        agents_dir = self.tmp / ".claude" / "agents"
        target = agents_dir / "developer.md"
        if not target.exists():
            candidates = sorted(agents_dir.glob("*.md"))
            self.assertTrue(candidates, "no agents installed")
            target = candidates[0]

        # Make it differ from source so the 2nd install takes the append path,
        # without the "## osEngineer" marker that short-circuits it.
        original = target.read_text()
        target.write_text(original.replace("\n", "\n", 1) + "\nLocal customisation line.\n")

        self.assertEqual(sh(INSTALL, self.tmp, self.home).returncode, 0)

        # Counting '---' lines is NOT the test: '---' is also a markdown
        # horizontal rule, and the agent bodies legitimately contain several.
        # The defect is specifically a FRONTMATTER block appearing after line 1,
        # i.e. a fence immediately followed by a `key:` line.
        lines = target.read_text().splitlines()
        injected = [
            (i + 1, lines[i + 1])
            for i in range(1, len(lines) - 1)
            if lines[i].strip() == "---" and re.match(r"^[A-Za-z_][A-Za-z0-9_-]*:", lines[i + 1])
        ]
        self.assertEqual(
            injected, [],
            f"{target.name}: append re-injected a YAML frontmatter block mid-body at "
            f"line(s) {[n for n, _ in injected]} -> {[t for _, t in injected]}",
        )
        # Sanity: the real frontmatter at line 1 must survive untouched.
        self.assertEqual(lines[0].strip(), "---", "leading frontmatter fence lost")
        self.assertRegex(lines[1], r"^name:", "leading frontmatter no longer starts with name:")


class TestPostCommitGraphify(unittest.TestCase):
    def test_no_ast_only_flag(self):
        src = POST_COMMIT.read_text()
        self.assertIn("graphify update .", src)
        for line in src.splitlines():
            if line.strip().startswith("graphify update"):
                self.assertNotIn("--ast-only", line, "post-commit still passes removed --ast-only flag")


if __name__ == "__main__":
    unittest.main()
