"""bin/ose-tdd-check enforces test-first ordering on a commit range.

CLAUDE.md says TDD is strict, but nothing checked it after the fact: a feat
commit could land without any test commit ahead of it and CI stayed green.
The rule checked here is deliberately simple and honest, not coverage analysis:

  * every commit that changes production code must have a `test(...)` commit
    that touches tests between it and the previous production commit (walking
    first parents inside the range), or
  * carry a `Risk-Exception: <class> — <reason>` trailer granted by the
    architect, with class in docs/config/rename/trivial/revert/generated.

Every fixture is a throwaway git repo built in a temp dir.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "bin" / "ose-tdd-check"

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
}


class Repo:
    def __init__(self, path):
        self.path = Path(path)
        self.git("init", "-q", "-b", "main")
        self.base = self.commit("chore: initial", {"README.md": "x\n"})

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.path, env=GIT_ENV,
                              capture_output=True, text=True, check=True).stdout.strip()

    def commit(self, message, files):
        for rel, content in files.items():
            p = self.path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            self.git("add", rel)
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")


def run_check(repo, *args, base=None, head="HEAD"):
    cmd = [sys.executable, str(CHECK), "--repo", str(repo.path),
           f"{base or repo.base}..{head}", *args]
    return subprocess.run(cmd, capture_output=True, text=True)


class TddCheckCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def json_of(self, proc):
        return json.loads(proc.stdout)


class TestOrdering(TddCheckCase):
    def test_test_commit_before_feat_passes(self):
        self.repo.commit("test(x): add failing test", {"test/test_x.py": "t\n"})
        self.repo.commit("feat(x): implement", {"bin/x": "code\n"})
        proc = run_check(self.repo)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_feat_without_test_fails_and_names_the_commit(self):
        sha = self.repo.commit("feat(x): implement", {"bin/x": "code\n"})
        proc = run_check(self.repo)
        self.assertEqual(proc.returncode, 1)
        self.assertIn(sha[:7], proc.stdout)

    def test_test_commit_after_feat_does_not_count(self):
        self.repo.commit("feat(x): implement", {"bin/x": "code\n"})
        self.repo.commit("test(x): add test", {"test/test_x.py": "t\n"})
        self.assertEqual(run_check(self.repo).returncode, 1)

    def test_one_test_commit_covers_only_the_next_production_commit(self):
        self.repo.commit("test(x): add test", {"test/test_x.py": "t\n"})
        self.repo.commit("feat(x): implement", {"bin/x": "code\n"})
        sha = self.repo.commit("fix(x): tweak", {"hooks/h.sh": "code\n"})
        proc = run_check(self.repo)
        self.assertEqual(proc.returncode, 1)
        self.assertIn(sha[:7], proc.stdout)

    def test_docs_commits_between_test_and_feat_are_fine(self):
        self.repo.commit("test(x): add test", {"test/test_x.py": "t\n"})
        self.repo.commit("docs: explain", {"docs/x.md": "d\n", "CHANGELOG.md": "c\n"})
        self.repo.commit("feat(x): implement", {"repo_profile/x.py": "code\n"})
        self.assertEqual(run_check(self.repo).returncode, 0)

    def test_test_type_must_touch_tests(self):
        self.repo.commit("test(x): claims a test", {"docs/x.md": "d\n"})
        self.repo.commit("feat(x): implement", {"bin/x": "code\n"})
        self.assertEqual(run_check(self.repo).returncode, 1)

    def test_tests_touched_by_non_test_commit_do_not_count(self):
        self.repo.commit("chore(x): move fixtures", {"test/fixtures/a": "t\n"})
        self.repo.commit("feat(x): implement", {"bin/x": "code\n"})
        self.assertEqual(run_check(self.repo).returncode, 1)

    def test_feat_bundling_its_own_tests_still_needs_a_test_commit_first(self):
        self.repo.commit("feat(x): implement", {"bin/x": "code\n", "test/test_x.py": "t\n"})
        self.assertEqual(run_check(self.repo).returncode, 1)

    def test_docs_only_range_passes(self):
        self.repo.commit("docs: readme", {"README.md": "y\n", "hooks/README.md": "z\n"})
        self.assertEqual(run_check(self.repo).returncode, 0)

    def test_empty_range_passes(self):
        self.assertEqual(run_check(self.repo).returncode, 0)

    def test_breaking_test_type_counts(self):
        self.repo.commit("test(x)!: rewrite tests", {"test/test_x.py": "t\n"})
        self.repo.commit("feat(x)!: rewrite", {"bin/x": "code\n"})
        self.assertEqual(run_check(self.repo).returncode, 0)


class TestMerges(TddCheckCase):
    def test_merge_commits_are_skipped_and_branch_order_is_followed(self):
        self.repo.git("checkout", "-q", "-b", "feature")
        self.repo.commit("test(x): add test", {"test/test_x.py": "t\n"})
        self.repo.commit("feat(x): implement", {"bin/x": "code\n"})
        self.repo.git("checkout", "-q", "main")
        self.repo.commit("docs: unrelated", {"docs/y.md": "y\n"})
        self.repo.git("merge", "-q", "--no-ff", "-m", "Merge branch 'feature'", "feature")
        proc = run_check(self.repo, "--json")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        subjects = [c["subject"] for c in self.json_of(proc)["commits"]]
        self.assertNotIn("Merge branch 'feature'", subjects)

    def test_test_on_another_branch_does_not_cover(self):
        self.repo.git("checkout", "-q", "-b", "tests-only")
        self.repo.commit("test(x): add test", {"test/test_x.py": "t\n"})
        self.repo.git("checkout", "-q", "main")
        self.repo.commit("feat(x): implement", {"bin/x": "code\n"})
        self.repo.git("merge", "-q", "--no-ff", "-m", "Merge branch 'tests-only'", "tests-only")
        self.assertEqual(run_check(self.repo).returncode, 1)


class TestRiskException(TddCheckCase):
    def test_valid_trailer_passes_and_is_listed(self):
        sha = self.repo.commit(
            "fix(x): typo in message\n\nRisk-Exception: trivial — one-word string fix",
            {"bin/x": "code\n"})
        proc = run_check(self.repo, "--json")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        exc = self.json_of(proc)["exceptions"]
        self.assertEqual(len(exc), 1)
        self.assertEqual(exc[0]["sha"], sha)
        self.assertEqual(exc[0]["class"], "trivial")
        self.assertEqual(exc[0]["reason"], "one-word string fix")

    def test_text_report_lists_every_exception(self):
        self.repo.commit("chore: regen\n\nRisk-Exception: generated — rebuilt index",
                         {"hooks/INDEX.json": "{}\n"})
        self.repo.commit("refactor: rename\n\nRisk-Exception: rename -- helper renamed",
                         {"bin/y": "code\n"})
        proc = run_check(self.repo)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("Risk exceptions (2)", proc.stdout)
        self.assertIn("generated", proc.stdout)
        self.assertIn("helper renamed", proc.stdout)

    def test_all_documented_classes_are_accepted(self):
        for i, cls in enumerate(("docs", "config", "rename", "trivial", "revert", "generated")):
            self.repo.commit(f"chore: c{i}\n\nRisk-Exception: {cls} — reason {i}",
                             {f"bin/f{i}": "code\n"})
        self.assertEqual(run_check(self.repo).returncode, 0)

    def test_unknown_class_fails(self):
        self.repo.commit("feat(x): parser\n\nRisk-Exception: urgent — no time",
                         {"bin/x": "code\n"})
        proc = run_check(self.repo)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("urgent", proc.stdout)

    def test_missing_reason_fails(self):
        self.repo.commit("fix(x): tweak\n\nRisk-Exception: trivial", {"bin/x": "code\n"})
        self.assertEqual(run_check(self.repo).returncode, 1)

    def test_trailer_in_body_prose_is_not_a_trailer(self):
        self.repo.commit(
            "fix(x): tweak\n\nRisk-Exception: trivial — not a trailer\n\nmore prose after it",
            {"bin/x": "code\n"})
        self.assertEqual(run_check(self.repo).returncode, 1)

    def test_exception_on_non_production_commit_is_still_listed(self):
        self.repo.commit("docs: x\n\nRisk-Exception: docs — prose only", {"docs/x.md": "d\n"})
        proc = run_check(self.repo, "--json")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(len(self.json_of(proc)["exceptions"]), 1)


class TestClassification(TddCheckCase):
    def test_default_globs_cover_installers_and_packages(self):
        for i, rel in enumerate(("install.sh", "uninstall.sh", "repo_runtime/r.py",
                                 "repo_integrations/c.py", "hooks/lib/l.py")):
            self.repo.commit(f"feat: f{i}", {rel: "code\n"})
        data = self.json_of(run_check(self.repo, "--json"))
        self.assertEqual([c["kind"] for c in data["commits"]], ["production"] * 5)

    def test_markdown_inside_production_dirs_is_other(self):
        self.repo.commit("docs: hooks", {"hooks/README.md": "d\n", "bin/NOTES.md": "n\n"})
        data = self.json_of(run_check(self.repo, "--json"))
        self.assertEqual(data["commits"][0]["kind"], "other")

    def test_prod_flag_replaces_defaults(self):
        self.repo.commit("feat: lib", {"src/lib.py": "code\n"})
        self.repo.commit("feat: bin", {"bin/x": "code\n"})
        proc = run_check(self.repo, "--prod", "src/*", "--json")
        kinds = [c["kind"] for c in self.json_of(proc)["commits"]]
        self.assertEqual(kinds, ["production", "other"])

    def test_tests_flag_replaces_default(self):
        self.repo.commit("test: spec", {"spec/x_spec.rb": "t\n"})
        self.repo.commit("feat: x", {"bin/x": "code\n"})
        self.assertEqual(run_check(self.repo, "--tests", "spec/*").returncode, 0)


class TestInputErrors(TddCheckCase):
    def test_bad_range_exits_2(self):
        proc = run_check(self.repo, base="deadbeef")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("error", proc.stderr)

    def test_not_a_repo_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run([sys.executable, str(CHECK), "--repo", d, "HEAD~1..HEAD"],
                                  capture_output=True, text=True, env=GIT_ENV)
        self.assertEqual(proc.returncode, 2)


class TestMarkdown(TddCheckCase):
    def test_markdown_report_has_exceptions_table(self):
        self.repo.commit("fix: t\n\nRisk-Exception: trivial — typo", {"bin/x": "code\n"})
        proc = run_check(self.repo, "--markdown")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("| ", proc.stdout)
        self.assertIn("trivial", proc.stdout)
        self.assertIn("typo", proc.stdout)


class TestVerifyRed(TddCheckCase):
    """--verify-red checks out the covering test commit and expects a failure."""

    def add_suite(self, passing):
        script = "import sys\nsys.exit(0)\n" if passing else "import sys\nsys.exit(1)\n"
        self.repo.commit("test(x): add test", {"test/run.py": script})
        self.repo.commit("feat(x): implement", {"bin/x": "code\n"})

    def verify(self):
        return run_check(self.repo, "--verify-red", "--test-cmd",
                         f"{sys.executable} test/run.py", "--json")

    def test_red_test_commit_passes(self):
        self.add_suite(passing=False)
        proc = self.verify()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        prod = [c for c in self.json_of(proc)["commits"] if c["kind"] == "production"]
        self.assertEqual(prod[0]["red"], "verified")

    def test_green_test_commit_fails(self):
        self.add_suite(passing=True)
        proc = self.verify()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("passed at the test commit", proc.stdout)

    def test_verify_red_leaves_no_worktree_behind(self):
        self.add_suite(passing=False)
        self.verify()
        self.assertEqual(len(self.repo.git("worktree", "list").splitlines()), 1)


class TestCiWiring(unittest.TestCase):
    """The PR gate must run the check on the PR range and surface exceptions."""

    def setUp(self):
        body = (ROOT / ".github" / "workflows" / "osengineer.yml").read_text()
        self.job = body.split("\n  commit-messages:", 1)[1]

    def test_commit_messages_job_runs_the_check_on_the_pr_range(self):
        self.assertIn("bin/ose-tdd-check", self.job)
        self.assertIn("steps.range.outputs.base }}..${{ steps.range.outputs.head", self.job)

    def test_exceptions_reach_the_job_summary(self):
        self.assertIn("--markdown", self.job)
        self.assertIn("GITHUB_STEP_SUMMARY", self.job)

    def test_red_verification_stays_off_in_ci(self):
        # The suite takes minutes; one run per test commit does not fit a PR gate.
        self.assertNotIn("--verify-red", self.job)


if __name__ == "__main__":
    unittest.main()
