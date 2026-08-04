import subprocess
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "bin" / "osengineer"


def run(args, cwd=None):
    result = subprocess.run(
        ["python3", str(BIN), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result


class TestVersion(unittest.TestCase):
    def test_version(self):
        result = run(["version"])
        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout, r"^osengineer \d+\.\d+\.\d+")

    def test_dash_version(self):
        result = run(["--version"])
        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout, r"^osengineer \d+\.\d+\.\d+")


class TestExplain(unittest.TestCase):
    def test_overview(self):
        result = run(["explain"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("osEngineer", result.stdout)

    def test_phases(self):
        result = run(["explain", "phases"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("Phase lifecycle", result.stdout)

    def test_unknown_topic(self):
        result = run(["explain", "nonexistent"])
        self.assertEqual(result.returncode, 1)


class TestDetectTeams(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ose-test-"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_go_repo(self):
        (self.tmp / "go.mod").write_text("module example\n")
        (self.tmp / "internal").mkdir()
        (self.tmp / ".osengineer").mkdir()
        result = run(["detect-teams", str(self.tmp)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("team_id: coding", result.stdout)
        self.assertIn("folder: internal/", result.stdout)
        self.assertNotIn("team_id: infra", result.stdout)

    def test_python_repo_with_docs(self):
        (self.tmp / "pyproject.toml").write_text("[project]\n")
        (self.tmp / "docs").mkdir()
        (self.tmp / ".osengineer").mkdir()
        result = run(["detect-teams", str(self.tmp)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("team_id: coding", result.stdout)
        self.assertIn("team_id: docs", result.stdout)


class TestState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ose-state-"))
        (self.tmp / ".git").mkdir()
        (self.tmp / ".osengineer").mkdir()
        (self.tmp / ".osengineer" / "state.yml").write_text("phase: idle\ncurrent_team: coding\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_reads_state(self):
        result = run(["state"], cwd=str(self.tmp))
        self.assertEqual(result.returncode, 0)
        self.assertIn("phase: idle", result.stdout)
        self.assertIn("current_team: coding", result.stdout)

    def test_sets_state_field(self):
        result = run(["state", "set", "phase", "execute"], cwd=str(self.tmp))
        self.assertEqual(result.returncode, 0)
        content = (self.tmp / ".osengineer" / "state.yml").read_text()
        self.assertIn("phase: execute", content)


class TestHandoff(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ose-handoff-"))
        (self.tmp / ".git").mkdir()
        (self.tmp / ".osengineer").mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_open_and_close_repo_handoff(self):
        open_result = run([
            "handoff", "open", "--from", "coding", "--to", "infra",
            "--slug", "add-compose", "--closes-when", "docker-compose.yml merged",
        ], cwd=str(self.tmp))
        self.assertEqual(open_result.returncode, 0, open_result.stderr)
        self.assertIn("HO-001", open_result.stdout)

        list_result = run(["handoff", "list"], cwd=str(self.tmp))
        self.assertEqual(list_result.returncode, 0)
        self.assertIn("HO-001", list_result.stdout)

        close_result = run(["handoff", "close", "HO-001", "--reason", "Done"], cwd=str(self.tmp))
        self.assertEqual(close_result.returncode, 0, close_result.stderr)

        content = (self.tmp / ".osengineer" / "handoffs" / "HO-001-add-compose.md").read_text()
        self.assertIn("closed_at:", content)
        self.assertIn("close_reason:", content)


if __name__ == "__main__":
    unittest.main()
