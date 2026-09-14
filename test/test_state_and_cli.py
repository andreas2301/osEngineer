"""State writes must survive concurrency, and the CLI must be invocable.

Two problems that only bite once osEngineer runs headlessly:

  * write_state_field() is read_text -> mutate -> write_text with no locking and
    no atomic replace (hooks/lib/osengineer_common.py). A repo-wide grep for
    flock/lockf/fcntl/O_EXCL/os.replace finds nothing. This is masked today only
    because the PostToolUse writer was dead; now that it runs, a hook rewrites
    state.yml on every tool call. Headless runs add cross-process concurrency on
    top of that, and a torn write loses the phase.

  * The same parser is duplicated verbatim in hooks/lib/osengineer_common.py and
    bin/osengineer with no shared import, so a fix to one silently leaves the
    other wrong.

  * Every doc invokes `osengineer ...` but the CLI is not on PATH and there is
    no launcher, so none of the documented commands work as written.
"""
import concurrent.futures
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMON = ROOT / "hooks" / "lib" / "osengineer_common.py"
CLI = ROOT / "bin" / "osengineer"

sys.path.insert(0, str(ROOT / "hooks" / "lib"))
import osengineer_common  # noqa: E402


def make_repo(tmp):
    repo = Path(tmp)
    (repo / ".osengineer").mkdir(parents=True, exist_ok=True)
    (repo / ".osengineer" / "state.yml").write_text(
        "phase: idle\ncurrent_team: null\nbudget_used: 0\nosengineer_version: 0.4.0\n"
    )
    return repo


class TestStateWritesAreAtomic(unittest.TestCase):
    def test_uses_atomic_replace(self):
        src = COMMON.read_text()
        self.assertIn(
            "os.replace", src,
            "write_state_field truncates the file in place; a crash or a "
            "concurrent reader mid-write loses state. Write to a temp file in "
            "the same directory and os.replace() it.",
        )

    def test_uses_locking(self):
        src = COMMON.read_text()
        self.assertTrue(
            any(t in src for t in ("fcntl", "flock", "LOCK_EX")),
            "write_state_field has no lock. With PostToolUse live and headless "
            "runs concurrent, two writers interleave read-modify-write and one "
            "update is lost.",
        )

    def test_concurrent_writers_never_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            state = repo / ".osengineer" / "state.yml"

            script = (
                "import sys;"
                f"sys.path.insert(0, {str(ROOT / 'hooks' / 'lib')!r});"
                "from osengineer_common import write_state_field;"
                f"write_state_field({str(repo)!r}, 'budget_used', int(sys.argv[1]))"
            )

            def writer(i):
                return subprocess.run(
                    [sys.executable, "-c", script, str(i)],
                    capture_output=True, text=True, timeout=60,
                ).returncode

            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
                list(ex.map(writer, range(40)))

            raw = state.read_text()
            self.assertTrue(raw.strip(), "state.yml was truncated to empty")
            keys = re.findall(r"^(\w+):", raw, re.MULTILINE)
            for required in ("phase", "current_team", "budget_used"):
                self.assertIn(
                    required, keys,
                    f"concurrent writes lost the `{required}` key.\n{raw!r}",
                )
            self.assertEqual(
                len(keys), len(set(keys)),
                f"concurrent writes duplicated keys: {keys}\n{raw!r}",
            )
            self.assertEqual(
                len(re.findall(r"^budget_used:", raw, re.MULTILINE)), 1,
                f"budget_used written more than once:\n{raw!r}",
            )


class TestStateParserIsNotDuplicated(unittest.TestCase):
    def test_cli_imports_shared_helpers(self):
        src = CLI.read_text()
        self.assertIn(
            "osengineer_common", src,
            "bin/osengineer re-implements read_state_map/write_state_field "
            "instead of importing the shared copy from hooks/lib — a fix to one "
            "silently leaves the other wrong.",
        )

    def test_cli_does_not_redefine_write_state_field(self):
        src = CLI.read_text()
        defs = re.findall(r"^def (read_state_map|write_state_field)\b", src, re.MULTILINE)
        self.assertEqual(
            defs, [],
            f"bin/osengineer still defines its own {defs}; import them instead",
        )

    def test_dead_reader_is_gone(self):
        """read_workbench_config() has had zero callers since it was written."""
        src = CLI.read_text()
        if "def read_workbench_config" not in src:
            return
        callers = [
            line for line in src.splitlines()
            if "read_workbench_config" in line and not line.strip().startswith("def ")
        ]
        self.assertTrue(
            callers,
            "read_workbench_config() is defined but never called anywhere; "
            "delete it or wire it up",
        )


class TestCliIsInvocable(unittest.TestCase):
    def test_cli_runs_via_python(self):
        proc = subprocess.run(
            [sys.executable, str(CLI), "version"],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_launcher_is_installed_into_the_repo(self):
        """Docs all say `osengineer ...`. Without a launcher, nothing that
        shells out to the CLI works — including the headless runner."""
        install = (ROOT / "install.sh").read_text()
        self.assertTrue(
            re.search(r"\.osengineer/bin/osengineer", install),
            "install.sh never creates a .osengineer/bin/osengineer launcher, so "
            "the documented `osengineer` command does not exist in a target repo",
        )

    def test_launcher_does_not_hardcode_a_checkout_path(self):
        """OSENGINEER_HOME is written as a resolved absolute path, so every repo
        pins one machine's checkout. CI has no such path."""
        install = (ROOT / "install.sh").read_text()
        bad = [
            f"{i}: {line.strip()}"
            for i, line in enumerate(install.splitlines(), 1)
            if "/root/sideProjects" in line or "/home/" in line and "HOME" not in line
        ]
        self.assertEqual(bad, [], "absolute developer paths baked in:\n" + "\n".join(bad))


class TestPlanningDirsAreCreated(unittest.TestCase):
    def test_install_creates_planning_dirs(self):
        """Both plan gates and planning/PROTOCOL.md reference planning/active,
        which install.sh has never created."""
        install = (ROOT / "install.sh").read_text()
        self.assertIn(
            "planning/active", install,
            "install.sh never creates planning/active/, so the phase gate and "
            "the PHASE_PLAN precondition both point at a directory that does "
            "not exist in any installed repo",
        )


if __name__ == "__main__":
    unittest.main()
