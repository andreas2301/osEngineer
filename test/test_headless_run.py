"""`osengineer run` — execute a phase with no human in the session.

This is the headless half of the hybrid: the same agent prompts and the same
guards, driven from CI or a webhook instead of an interactive session. It must
reuse the EXISTING command bodies via `osengineer render`, so the interactive
and headless paths cannot drift.

Safety properties that only matter headlessly, and are asserted here:

  * OSE_HEADLESS=1 must reach the harness child, because that is what makes the
    denylist absolute (see test_selfauth_guard). A runner that forgets it gives
    the agent back its self-authorisation route.
  * Budget is also enforced by the runner, out of process: the harness gets at
    most the wall time left before budget.tripPct (test_circuit_breaker), so a
    harness without the post-tool hook is still bounded.
  * A run must be resumable/auditable: a transcript on disk, not just stdout.

Tests drive a FAKE harness binary so nothing here spends tokens or needs network.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "osengineer"

FAKE_HARNESS = """#!/usr/bin/env python3
import json, os, sys, pathlib
# Record how we were invoked so the test can assert on argv and env.
rec = {
    "argv": sys.argv[1:],
    "cwd": os.getcwd(),
    "OSE_HEADLESS": os.environ.get("OSE_HEADLESS"),
    "OSENGINEER_HOME": os.environ.get("OSENGINEER_HOME"),
}
# NOTE: deliberately does not read stdin. The runner passes the prompt via
# argv (-p), and a blocking read() here hangs the whole suite.
out = os.environ.get("FAKE_HARNESS_RECORD")
if out:
    pathlib.Path(out).write_text(json.dumps(rec))
mode = os.environ.get("FAKE_HARNESS_MODE", "ok")
if mode == "fail":
    print("boom", file=sys.stderr)
    sys.exit(3)
if mode == "sleep":
    import time
    time.sleep(float(os.environ.get("FAKE_HARNESS_SLEEP", "5")))
print(json.dumps({"type": "result", "text": "done"}))
sys.exit(0)
"""


VALID_PLAN = '---\n{"phase_id": "phase-001-test", "goal": "A valid test phase plan.", "tasks": [{"id": "T1", "description": "d", "acceptance": "a", "budget": {"tool_calls": 50, "wall_minutes": 30}}]}\n---\n# Phase 1\n'


def make_repo(tmp, phase="plan", plan=True, dirty=False):
    repo = Path(tmp) / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    (repo / ".osengineer").mkdir()
    # As install.sh writes it: hook-written runtime files never dirty the tree.
    (repo / ".osengineer" / ".gitignore").write_text("runtime.yml\n.state.lock\n")
    (repo / ".osengineer" / "state.yml").write_text(
        f"phase: {phase}\ncurrent_team: null\nbudget_used: 0\n"
    )
    if plan:
        d = repo / "planning" / "active" / "phase-1"
        d.mkdir(parents=True)
        (d / "PHASE_PLAN.md").write_text(VALID_PLAN)
    (repo / "m.py").write_text("x=1\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "i"], cwd=repo, check=True)
    if dirty:
        (repo / "m.py").write_text("x=2\n")
    return repo


def make_fake_harness(tmp, name="claude"):
    p = Path(tmp) / name
    p.write_text(FAKE_HARNESS)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return p


def run_cli(repo, args, env=None):
    e = dict(os.environ)
    e["OSENGINEER_HOME"] = str(ROOT)
    if env:
        e.update(env)
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(repo), capture_output=True, text=True, timeout=120, env=e,
    )


class HeadlessBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.harness = make_fake_harness(self.tmp)
        self.record = Path(self.tmp) / "record.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def env(self, **over):
        e = {
            "OSE_HARNESS_BIN": str(self.harness),
            "FAKE_HARNESS_RECORD": str(self.record),
        }
        e.update(over)
        return e

    def rec(self):
        self.assertTrue(self.record.exists(), "harness was never invoked")
        return json.loads(self.record.read_text())


class TestRunSubcommandExists(unittest.TestCase):
    def test_run_is_a_known_subcommand(self):
        proc = subprocess.run(
            [sys.executable, str(CLI), "help"],
            capture_output=True, text=True, timeout=60,
        )
        self.assertIn("run", proc.stdout, "`run` missing from the CLI usage text")


class TestRunInvokesHarness(HeadlessBase):
    def test_happy_path_exits_zero(self):
        repo = make_repo(self.tmp)
        proc = run_cli(repo, ["run", "fix", "TICKET-1"], self.env())
        self.assertEqual(proc.returncode, 0, f"{proc.stdout}\n{proc.stderr}")

    def test_headless_flag_reaches_the_child(self):
        repo = make_repo(self.tmp)
        run_cli(repo, ["run", "fix", "TICKET-1"], self.env())
        self.assertEqual(
            self.rec().get("OSE_HEADLESS"), "1",
            "OSE_HEADLESS=1 did not reach the harness; without it the 4-part "
            "plan file still lifts the denylist and the agent can self-authorise",
        )

    def test_prompt_is_passed_to_the_harness(self):
        repo = make_repo(self.tmp)
        run_cli(repo, ["run", "fix", "TICKET-1"], self.env())
        rec = self.rec()
        blob = " ".join(rec["argv"])
        self.assertTrue(blob.strip(), "harness received no prompt at all")
        self.assertIn(
            "TICKET-1", blob, "the run argument never reached the harness prompt"
        )

    def test_harness_failure_is_reported(self):
        repo = make_repo(self.tmp)
        proc = run_cli(repo, ["run", "fix", "T"], self.env(FAKE_HARNESS_MODE="fail"))
        self.assertNotEqual(
            proc.returncode, 0, "a failing harness produced a successful run"
        )


class TestPreflightGates(HeadlessBase):
    def test_refuses_without_a_phase_plan(self):
        repo = make_repo(self.tmp, plan=False)
        proc = run_cli(repo, ["run", "fix", "T"], self.env())
        self.assertNotEqual(proc.returncode, 0, "ran with no PHASE_PLAN.md")
        self.assertFalse(
            self.record.exists(), "harness was spawned despite a failed pre-flight"
        )

    def test_refuses_on_a_dirty_tree(self):
        repo = make_repo(self.tmp, dirty=True)
        proc = run_cli(repo, ["run", "fix", "T"], self.env())
        self.assertNotEqual(proc.returncode, 0, "ran with uncommitted changes")

    def test_refuses_outside_an_osengineer_repo(self):
        plain = Path(self.tmp) / "plain"
        plain.mkdir()
        proc = run_cli(plain, ["run", "fix", "T"], self.env())
        self.assertNotEqual(proc.returncode, 0, "ran outside an osEngineer repo")

    def test_refuses_an_unknown_verb(self):
        repo = make_repo(self.tmp)
        proc = run_cli(repo, ["run", "not-a-verb"], self.env())
        self.assertNotEqual(proc.returncode, 0, "unknown verb was accepted")


class TestRunArtifacts(HeadlessBase):
    def test_run_directory_is_written(self):
        repo = make_repo(self.tmp)
        run_cli(repo, ["run", "fix", "TICKET-1"], self.env())
        runs = repo / ".osengineer" / "runs"
        self.assertTrue(runs.is_dir(), "no .osengineer/runs/ directory")
        entries = [d for d in runs.iterdir() if d.is_dir()]
        self.assertEqual(len(entries), 1, f"expected one run dir, got {entries}")
        run_dir = entries[0]
        meta = run_dir / "RUN.json"
        self.assertTrue(meta.exists(), "no RUN.json — the run is not auditable")
        data = json.loads(meta.read_text())
        for key in ("verb", "harness", "status", "started_at"):
            self.assertIn(key, data, f"RUN.json missing {key}: {data}")
        self.assertEqual(data["verb"], "fix")

    def test_failure_is_recorded_in_run_json(self):
        repo = make_repo(self.tmp)
        run_cli(repo, ["run", "fix", "T"], self.env(FAKE_HARNESS_MODE="fail"))
        runs = repo / ".osengineer" / "runs"
        run_dir = [d for d in runs.iterdir() if d.is_dir()][0]
        data = json.loads((run_dir / "RUN.json").read_text())
        self.assertNotEqual(
            data.get("status"), "success", "a failed run was recorded as success"
        )

    def test_concurrent_runs_get_distinct_directories(self):
        repo = make_repo(self.tmp)
        run_cli(repo, ["run", "fix", "A"], self.env())
        run_cli(repo, ["run", "fix", "B"], self.env())
        runs = [d for d in (repo / ".osengineer" / "runs").iterdir() if d.is_dir()]
        self.assertEqual(len(runs), 2, f"run dirs collided: {runs}")


class TestHarnessSelection(HeadlessBase):
    def test_kimi_harness_is_selectable(self):
        repo = make_repo(self.tmp)
        kimi = make_fake_harness(self.tmp, "kimi")
        proc = run_cli(
            repo, ["run", "fix", "T", "--harness", "kimi"],
            self.env(OSE_HARNESS_BIN=str(kimi)),
        )
        self.assertEqual(proc.returncode, 0, f"{proc.stdout}\n{proc.stderr}")
        self.assertEqual(self.rec()["argv"][0], "-p",
                         "kimi must be driven with -p (it is already autonomous; "
                         "it rejects --auto and -y alongside -p)")

    def test_recorded_harness_name_matches(self):
        repo = make_repo(self.tmp)
        kimi = make_fake_harness(self.tmp, "kimi")
        run_cli(repo, ["run", "fix", "T", "--harness", "kimi"],
                self.env(OSE_HARNESS_BIN=str(kimi)))
        runs = [d for d in (repo / ".osengineer" / "runs").iterdir() if d.is_dir()]
        data = json.loads((runs[0] / "RUN.json").read_text())
        self.assertEqual(data["harness"], "kimi")


if __name__ == "__main__":
    unittest.main()
