"""The 13 slash commands must actually be installed, and render once.

install.sh contains ZERO references to commands/ — verified by grep. So
/osEngineer:fix, :plan, :verify and the other ten verbs documented throughout
README.md and SKILL.md have never existed as invocable commands in any repo.
They are read only by prompt-guard's fuzzy routing-hint loader.

This also establishes the single prompt producer the headless runner needs: an
interactive slash command and `osengineer run` must render from the SAME body,
or the two paths drift. The body is delimited so prose around it (syntax notes,
preconditions, rationale) stays out of the rendered prompt.

Both harnesses are served: Claude reads .claude/commands/, and Kimi reads
.kimi-code/skills/ (its binary also discovers .claude/skills/).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.sh"
CLI = ROOT / "bin" / "osengineer"
COMMANDS = ROOT / "commands"

BODY_START = "<!-- ose:body:start -->"
BODY_END = "<!-- ose:body:end -->"


def command_files():
    return sorted(COMMANDS.glob("osEngineer-*.md"))


def verb_of(path):
    raw = path.read_text()
    m = re.search(r"^name:\s*osEngineer:([\w-]+)", raw, re.MULTILINE)
    return m.group(1) if m else None


def make_git_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True)
    (path / "m.py").write_text("x=1\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "i"], cwd=path, check=True)
    return path


def run_install(repo, home, runtimes="claude kimi", kimi_home=None):
    env = dict(os.environ)
    env.update({"OSE_NONINTERACTIVE": "1", "HOME": str(home), "RUNTIMES": runtimes})
    if kimi_home:
        env["KIMI_CODE_HOME"] = str(kimi_home)
    env.pop("CI", None)
    return subprocess.run(
        ["bash", str(INSTALL), str(repo)],
        capture_output=True, text=True, timeout=300, env=env,
    )


class TestInstallerKnowsAboutCommands(unittest.TestCase):
    def test_install_references_commands_dir(self):
        self.assertIn(
            "commands/", INSTALL.read_text(),
            "install.sh never mentions commands/ — the 13 documented slash "
            "commands are not installed anywhere",
        )


class TestCommandsLandInRepo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = Path(self.tmp) / "home"
        self.kimi_home = Path(self.tmp) / "kimi"
        self.home.mkdir()
        self.kimi_home.mkdir()
        self.repo = make_git_repo(Path(self.tmp) / "repo")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_claude_commands_are_written(self):
        proc = run_install(self.repo, self.home, kimi_home=self.kimi_home)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        dest = self.repo / ".claude" / "commands" / "osEngineer"
        self.assertTrue(dest.is_dir(), f"{dest} not created")
        got = {p.stem for p in dest.glob("*.md")}
        want = {verb_of(p) for p in command_files() if verb_of(p)}
        self.assertEqual(want - got, set(), f"verbs not installed: {sorted(want - got)}")

    def test_kimi_skills_are_written(self):
        run_install(self.repo, self.home, kimi_home=self.kimi_home)
        dest = self.repo / ".kimi-code" / "skills"
        self.assertTrue(
            dest.is_dir(),
            "Kimi discovers .kimi-code/skills/; without it Kimi users get no verbs",
        )
        got = {p.name for p in dest.iterdir() if (p / "SKILL.md").exists()}
        want = {verb_of(p) for p in command_files() if verb_of(p)}
        self.assertEqual(want - got, set(), f"skills not installed: {sorted(want - got)}")

    def test_claude_only_install_skips_kimi_skills(self):
        run_install(self.repo, self.home, runtimes="claude", kimi_home=self.kimi_home)
        self.assertFalse(
            (self.repo / ".kimi-code" / "skills").exists(),
            "Kimi skills written for a Claude-only install",
        )


class TestCommandBodiesAreFenced(unittest.TestCase):
    def test_fix_has_a_body_fence(self):
        raw = (COMMANDS / "osEngineer-fix.md").read_text()
        self.assertIn(
            BODY_START, raw,
            f"osEngineer-fix.md has no {BODY_START} fence, so there is no way to "
            f"render the executable body without the surrounding prose",
        )
        self.assertIn(BODY_END, raw)
        self.assertLess(
            raw.index(BODY_START), raw.index(BODY_END), "fence markers inverted"
        )


class TestRenderVerb(unittest.TestCase):
    def _render(self, verb, *args):
        return subprocess.run(
            [sys.executable, str(CLI), "render", verb, *args],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "OSENGINEER_HOME": str(ROOT)},
        )

    def test_render_emits_the_body(self):
        proc = self._render("fix")
        self.assertEqual(proc.returncode, 0, f"render failed:\n{proc.stderr}")
        self.assertTrue(proc.stdout.strip(), "render produced nothing")

    def test_render_excludes_frontmatter_and_fence_markers(self):
        out = self._render("fix").stdout
        self.assertNotIn(BODY_START, out, "fence marker leaked into the prompt")
        self.assertNotIn(BODY_END, out)
        self.assertNotIn("phase_allowed:", out, "frontmatter leaked into the prompt")

    def test_render_is_deterministic(self):
        a = self._render("fix").stdout
        b = self._render("fix").stdout
        self.assertEqual(a, b, "render is not deterministic")

    def test_render_rejects_unknown_verb(self):
        proc = self._render("definitely-not-a-verb")
        self.assertNotEqual(proc.returncode, 0, "unknown verb silently succeeded")

    def test_render_passes_arguments_without_shell_injection(self):
        """Arguments must not be interpolated into anything shell-evaluated."""
        proc = self._render("fix", "TICKET-1; rm -rf /")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("TICKET-1; rm -rf /", proc.stdout,
                      "argument was dropped or mangled")


class TestGeneratedCommandsHaveNoInjection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = Path(self.tmp) / "home"
        self.kimi_home = Path(self.tmp) / "kimi"
        self.home.mkdir()
        self.kimi_home.mkdir()
        self.repo = make_git_repo(Path(self.tmp) / "repo")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_arguments_inside_a_backtick_injection(self):
        """$ARGUMENTS inside a `!`/backtick injection is textual substitution
        into a shell command, which bypasses pre-bash-guard entirely."""
        run_install(self.repo, self.home, kimi_home=self.kimi_home)
        offenders = []
        for base in (self.repo / ".claude" / "commands", self.repo / ".kimi-code" / "skills"):
            if not base.exists():
                continue
            for p in base.rglob("*.md"):
                for i, line in enumerate(p.read_text().splitlines(), 1):
                    if "$ARGUMENTS" in line and ("`" in line or line.strip().startswith("!")):
                        offenders.append(f"{p.name}:{i}: {line.strip()}")
        self.assertEqual(offenders, [], "shell injection risk:\n" + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
