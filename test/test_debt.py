"""`osengineer debt` lists `shortcut:` comments from tracked files.

A deliberate limit is written as `<comment> shortcut: <limit> — revisit when
<trigger>`. An entry without a trigger is debt nobody will revisit, so it is
flagged, and `--check` fails on it.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "bin" / "osengineer"


class Debt(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="ose-debt-"))
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def write(self, rel, text, track=True):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        if track:
            subprocess.run(["git", "-C", str(self.repo), "add", rel], check=True)

    def debt(self, *args):
        return subprocess.run(["python3", str(BIN), "debt", *args], cwd=self.repo,
                              capture_output=True, text=True)

    def entries(self, *args):
        proc = self.debt("--json", *args)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_parses_every_comment_syntax(self):
        self.write("a.py", "x = 1\ny = 2  # shortcut: no cache — revisit when >1k rows\n")
        self.write("b.js", "// shortcut: linear scan — revisit when list > 500\n")
        self.write("c.sql", "SELECT 1; -- shortcut: no index - revisit when slow log shows it\n")
        self.write("d.c", "int x; /* shortcut: fixed buffer — revisit when inputs exceed 4k */\n")
        got = {(e["file"], e["line"], e["limit"], e["trigger"]) for e in self.entries()}
        self.assertEqual(got, {
            ("a.py", 2, "no cache", ">1k rows"),
            ("b.js", 1, "linear scan", "list > 500"),
            ("c.sql", 1, "no index", "slow log shows it"),
            ("d.c", 1, "fixed buffer", "inputs exceed 4k"),
        })

    def test_missing_trigger_is_flagged(self):
        self.write("a.py", "# shortcut: hardcoded region\n")
        [entry] = self.entries()
        self.assertEqual(entry["limit"], "hardcoded region")
        self.assertIsNone(entry["trigger"])
        text = self.debt()
        self.assertEqual(text.returncode, 0)
        self.assertIn("a.py:1", text.stdout)
        self.assertIn("no-trigger", text.stdout)

    def test_check_fails_only_on_missing_trigger(self):
        self.write("a.py", "# shortcut: no retry — revisit when errors appear\n")
        self.assertEqual(self.debt("--check").returncode, 0)
        self.write("b.py", "# shortcut: no retry\n")
        proc = self.debt("--check")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("b.py:1", proc.stdout)

    def test_only_tracked_files_and_not_vendor_or_fixtures(self):
        self.write("untracked.py", "# shortcut: x — revisit when y\n", track=False)
        self.write("vendor/lib.py", "# shortcut: x — revisit when y\n")
        self.write("test/fixtures/f.py", "# shortcut: x — revisit when y\n")
        self.write("gen/out.py", "# shortcut: x — revisit when y\n")
        self.write("keep.py", "# shortcut: x — revisit when y\n")
        self.assertEqual([e["file"] for e in self.entries("--exclude", "gen/")], ["keep.py"])

    def test_prose_mentions_are_not_entries(self):
        self.write("README.md", "Write `# shortcut: <limit> — revisit when <trigger>`.\n"
                                "The word shortcut: alone is prose.\n")
        self.write("bin.dat", "\x00\n# shortcut: binary\n")
        self.assertEqual(self.entries(), [])

    def test_outside_a_git_repo_is_an_error(self):
        plain = Path(tempfile.mkdtemp(prefix="ose-debt-plain-"))
        self.addCleanup(shutil.rmtree, plain, True)
        proc = subprocess.run(["python3", str(BIN), "debt"], cwd=plain,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("git", proc.stderr)


if __name__ == "__main__":
    unittest.main()
