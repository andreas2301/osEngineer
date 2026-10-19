"""The evolve loop proposes; the owner decides.

`osengineer evolve accept` used to write the promoted pattern straight into the
SHARED skill home (`<skill>/memory/patterns/`) from any target repo — no review,
no commit, and a headless run could do it too. The proposer was the approver.

Now:
  * `accept` only writes a reviewable proposal into the TARGET repo
    (`.osengineer/evolve/proposals/<id>.md`) and never touches the skill home.
  * `promote <id>` is a separate, human-run step that commits the pattern on a
    new branch of the skill home git checkout (working tree untouched) and, with
    `--pr`, opens a PR. It refuses headless, on a dirty or non-git skill home,
    and on a proposal with missing fields. Nothing is ever merged.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GIT_ID = {
    "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.com",
}


def git(cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True,
        env={**os.environ, **GIT_ID},
    )


def snapshot(tree):
    """Every file outside .git with its bytes — the skill home's working tree."""
    out = {}
    for p in sorted(Path(tree).rglob("*")):
        if ".git" in p.relative_to(tree).parts or not p.is_file():
            continue
        out[str(p.relative_to(tree))] = p.read_bytes()
    return out


class EvolveCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        # A disposable skill home: a copy of the CLI so SCRIPT_DIR points here,
        # never at the real checkout running the tests.
        self.home = tmp / "skill"
        (self.home / "bin").mkdir(parents=True)
        shutil.copy2(ROOT / "bin" / "osengineer", self.home / "bin" / "osengineer")
        for pkg in ("hooks/lib", "repo_profile"):
            shutil.copytree(ROOT / pkg, self.home / pkg,
                            ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(ROOT / "VERSION", self.home / "VERSION")
        (self.home / "memory" / "patterns").mkdir(parents=True)
        (self.home / "memory" / "patterns" / ".gitkeep").write_text("")
        git(self.home, "init", "-q", "-b", "master")
        git(self.home, "add", "-A")
        git(self.home, "commit", "-q", "-m", "chore: init")
        self.cli = self.home / "bin" / "osengineer"

        self.repo = tmp / "target"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        (self.repo / ".osengineer").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *args, headless=False, home=None, path_prefix=None):
        env = {k: v for k, v in os.environ.items()
               if k not in ("OSE_HEADLESS", "OSE_BYPASS")}
        if path_prefix:
            env["PATH"] = f"{path_prefix}{os.pathsep}{env.get('PATH', '')}"
        env.update(GIT_ID)
        env["OSENGINEER_HOME"] = str(home or self.home)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if headless:
            env["OSE_HEADLESS"] = "1"
        return subprocess.run(
            [sys.executable, str(self.cli), *args], cwd=self.repo,
            capture_output=True, text=True, env=env, timeout=60,
        )

    def propose_and_accept(self, *extra):
        r = self.run_cli("evolve", "propose", "--title", "Declare queue before bind",
                         "--body", "Seen twice in retros: bind before declare races.")
        self.assertEqual(r.returncode, 0, r.stderr)
        return self.run_cli(
            "evolve", "accept", "EP-001", "--pattern-slug", "queue-declare-before-bind",
            "--why", "Two retros hit the same race.",
            "--risk", "Low: docs-only pattern file.",
            *extra,
        )

    def proposal_path(self):
        return self.repo / ".osengineer" / "evolve" / "proposals" / "EP-001.md"


class TestAcceptNeverTouchesSkillHome(EvolveCase):
    def test_accept_leaves_skill_home_tree_unchanged(self):
        before = snapshot(self.home)
        r = self.propose_and_accept()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(snapshot(self.home), before,
                         "evolve accept modified the shared skill home")
        self.assertEqual(git(self.home, "status", "--porcelain").stdout, "")

    def test_headless_accept_leaves_skill_home_tree_unchanged(self):
        before = snapshot(self.home)
        self.run_cli("evolve", "propose", "--title", "x", "--body", "y", headless=True)
        self.run_cli("evolve", "accept", "EP-001", "--pattern-slug", "x-pattern",
                     headless=True)
        self.assertEqual(snapshot(self.home), before)

    def test_accept_writes_reviewable_proposal_in_target_repo(self):
        r = self.propose_and_accept()
        self.assertEqual(r.returncode, 0, r.stderr)
        text = self.proposal_path().read_text()
        for heading in ("## What changes", "## Why", "## Risk",
                        "## How to revert", "## Evidence", "## Pattern"):
            self.assertIn(heading, text)
        self.assertIn("pattern_slug: queue-declare-before-bind", text)
        self.assertIn("EP-001", text)
        self.assertIn("Two retros hit the same race.", text)
        self.assertIn("bind before declare races", text)

    def test_accept_rejects_path_like_slug(self):
        self.run_cli("evolve", "propose", "--title", "x", "--body", "y")
        r = self.run_cli("evolve", "accept", "EP-001", "--pattern-slug", "../../evil")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.proposal_path().exists())


class TestPromoteIsHumanOnly(EvolveCase):
    def branches(self):
        return git(self.home, "branch", "--format=%(refname:short)").stdout.split()

    def test_headless_promote_refuses(self):
        self.propose_and_accept()
        r = self.run_cli("evolve", "promote", "EP-001", headless=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("headless", r.stderr.lower())
        self.assertEqual(self.branches(), ["master"])

    def test_promote_refuses_dirty_skill_home(self):
        self.propose_and_accept()
        (self.home / "stray.txt").write_text("uncommitted")
        r = self.run_cli("evolve", "promote", "EP-001")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.branches(), ["master"])

    def test_promote_refuses_non_git_skill_home(self):
        self.propose_and_accept()
        shutil.rmtree(self.home / ".git")
        r = self.run_cli("evolve", "promote", "EP-001")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.home / "memory" / "patterns" /
                          "queue-declare-before-bind.md").exists())

    def test_promote_refuses_proposal_missing_fields(self):
        self.run_cli("evolve", "propose", "--title", "x", "--body", "y")
        r = self.run_cli("evolve", "accept", "EP-001", "--pattern-slug", "x-pattern")
        self.assertEqual(r.returncode, 0, r.stderr)  # accept without --risk is allowed
        r = self.run_cli("evolve", "promote", "EP-001")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("risk", r.stderr.lower())
        self.assertEqual(self.branches(), ["master"])

    def test_promote_commits_on_branch_without_touching_tree(self):
        self.propose_and_accept()
        before = snapshot(self.home)
        r = self.run_cli("evolve", "promote", "EP-001")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(snapshot(self.home), before,
                         "promote changed the skill home working tree")
        self.assertEqual(git(self.home, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip(),
                         "master")
        branch = [b for b in self.branches() if b != "master"]
        self.assertEqual(len(branch), 1, self.branches())
        subject = git(self.home, "log", "-1", "--format=%s", branch[0]).stdout.strip()
        self.assertRegex(subject, r"^docs\(patterns\): ")
        self.assertLessEqual(len(subject), 72)
        files = git(self.home, "show", "--name-only", "--format=", branch[0]).stdout.split()
        self.assertEqual(files, ["memory/patterns/queue-declare-before-bind.md"])
        pattern = git(self.home, "show",
                      f"{branch[0]}:memory/patterns/queue-declare-before-bind.md").stdout
        self.assertIn("bind before declare races", pattern)
        self.assertIn("status: promoted", self.proposal_path().read_text())


class TestPromoteMarksTheOriginalProposal(EvolveCase):
    """The EP-NNN proposal the loop opened records that a human promoted it,
    and where to review it, so `evolve status` no longer lists it as open."""

    def original(self):
        d = self.repo / ".osengineer" / "evolution-proposals"
        files = sorted(d.glob("EP-001-*.md"))
        self.assertEqual(len(files), 1, files)
        return files[0].read_text()

    def test_promote_marks_original_with_branch(self):
        self.propose_and_accept()
        r = self.run_cli("evolve", "promote", "EP-001")
        self.assertEqual(r.returncode, 0, r.stderr)
        text = self.original()
        self.assertRegex(text, r"(?m)^status: promoted$")
        self.assertRegex(text, r"(?m)^promoted_branch: evolve/ep-001-queue-declare-before-bind$")
        self.assertRegex(text, r"(?m)^promoted_at: \S+")
        self.assertRegex(text, r"(?m)^skill_proposal: \.osengineer/evolve/proposals/EP-001\.md$")
        self.assertNotIn("promoted_pr:", text)
        status = self.run_cli("evolve", "status").stdout
        self.assertIn("open proposals: 0", status)
        self.assertIn("closed proposals: 1", status)

    def test_promote_with_pr_links_the_pr(self):
        origin = Path(self._tmp.name) / "origin.git"
        git(origin.parent, "init", "-q", "--bare", str(origin))
        git(self.home, "remote", "add", "origin", str(origin))
        fake = Path(self._tmp.name) / "fakebin"
        fake.mkdir()
        gh = fake / "gh"
        gh.write_text("#!/bin/sh\necho https://github.com/o/r/pull/7\n")
        gh.chmod(0o755)
        self.propose_and_accept()
        r = self.run_cli("evolve", "promote", "EP-001", "--pr", path_prefix=str(fake))
        self.assertEqual(r.returncode, 0, r.stderr)
        text = self.original()
        self.assertRegex(text, r"(?m)^status: promoted$")
        self.assertRegex(text, r"(?m)^promoted_pr: https://github.com/o/r/pull/7$")
        self.assertIn("promoted_pr: https://github.com/o/r/pull/7",
                      self.proposal_path().read_text())


if __name__ == "__main__":
    unittest.main()
