"""The budget circuit breaker: post-tool measures usage against the PHASE_PLAN
task budgets, warns at budget.warnPct, and at budget.tripPct writes BLOCKED.md
and sets phase=blocked; the pre guards then refuse edits and Bash.

Measured per tool call: tool-call count and wall time (gaps between calls up to
budget.idleSeconds). Tokens come from the Claude Code transcript when present
and are recorded, never enforced.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from test_headless_run import HeadlessBase, make_repo, run_cli

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"


def plan_text(tool_calls=2, wall_minutes=60, phase_id="phase-001-breaker", tokens=None):
    budget = {"tool_calls": tool_calls, "wall_minutes": wall_minutes}
    if tokens:
        budget["tokens"] = tokens
    return "---\n" + json.dumps({
        "phase_id": phase_id, "goal": "Exercise the circuit breaker.",
        "tasks": [{"id": "T1", "description": "d", "acceptance": "a", "budget": budget}],
    }) + "\n---\n# Plan\n"


def runtime_map(root):
    p = root / ".osengineer" / "runtime.yml"
    out = {}
    if p.exists():
        for line in p.read_text().splitlines():
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


class BreakerBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".osengineer").mkdir()
        self.state("execute")
        self.session = "ose-test-" + uuid.uuid4().hex
        self.plan_dir = self.root / "planning" / "active" / "phase-001"
        self.plan_dir.mkdir(parents=True)
        self.plan()

    def tearDown(self):
        self.tmp.cleanup()

    def state(self, phase):
        (self.root / ".osengineer/state.yml").write_text(f"phase: {phase}\ncurrent_team: null\n")

    def plan(self, **kw):
        (self.plan_dir / "PHASE_PLAN.md").write_text(plan_text(**kw))

    def profile(self, **settings):
        (self.root / ".osengineer/profile.json").write_text(json.dumps(settings))

    def hook(self, name, payload=None):
        env = dict(os.environ)
        for k in ("OSE_BYPASS", "OSENGINEER_HOME", "OSE_HEADLESS"):
            env.pop(k, None)
        body = {"cwd": str(self.root), "session_id": self.session, "tool_name": "Read",
                "tool_input": {"file_path": "x"}, **(payload or {})}
        return subprocess.run([sys.executable, str(HOOKS / f"osEngineer-{name}.py")],
                              input=json.dumps(body), text=True, capture_output=True, env=env, timeout=30)

    def phase(self):
        return re.search(r"^phase:\s*(\S+)", (self.root / ".osengineer/state.yml").read_text(), re.M).group(1)


class Accounting(BreakerBase):
    def test_tool_calls_are_counted_per_phase_in_runtime(self):
        r = self.hook("post-tool")
        self.assertEqual(r.returncode, 0, r.stderr)
        rt = runtime_map(self.root)
        self.assertEqual(rt["budget_phase"], "phase-001-breaker")
        self.assertEqual(rt["budget_tool_calls"], "1")
        self.assertEqual(rt["budget_ratio_pct"], "50")
        self.assertNotIn("budget_", (self.root / ".osengineer/state.yml").read_text())

    def test_counters_reset_when_the_phase_id_changes(self):
        self.hook("post-tool")
        self.plan(phase_id="phase-002-next", tool_calls=10)
        self.hook("post-tool")
        rt = runtime_map(self.root)
        self.assertEqual(rt["budget_phase"], "phase-002-next")
        self.assertEqual(rt["budget_tool_calls"], "1")

    def test_nothing_is_counted_outside_execution_or_without_a_plan(self):
        self.state("plan")
        self.hook("post-tool")
        self.assertNotIn("budget_tool_calls", runtime_map(self.root))
        self.state("execute")
        (self.plan_dir / "PHASE_PLAN.md").unlink()
        self.assertEqual(self.hook("post-tool").returncode, 0)
        self.assertNotIn("budget_tool_calls", runtime_map(self.root))

    def test_invalid_plan_in_execute_fails_closed(self):
        (self.plan_dir / "PHASE_PLAN.md").write_text("# no frontmatter\n")
        r = self.hook("post-tool")
        self.assertEqual(r.returncode, 2)
        self.assertIn("PHASE_PLAN.md", r.stderr)

    def test_wall_time_counts_gaps_up_to_idle_seconds(self):
        self.hook("post-tool")
        rt_path = self.root / ".osengineer/runtime.yml"
        rt_path.write_text(re.sub(r"budget_last_ts: .*", f"budget_last_ts: {time.time() - 30}", rt_path.read_text()))
        self.hook("post-tool")
        self.assertAlmostEqual(float(runtime_map(self.root)["budget_wall_seconds"]), 30, delta=5)
        rt_path.write_text(re.sub(r"budget_last_ts: .*", f"budget_last_ts: {time.time() - 5000}", rt_path.read_text()))
        self.hook("post-tool")
        self.assertAlmostEqual(float(runtime_map(self.root)["budget_wall_seconds"]), 30, delta=5)

    def test_tokens_are_recorded_from_the_transcript_without_duplicates(self):
        transcript = self.root / "t.jsonl"
        usage = {"input_tokens": 10, "output_tokens": 5, "cache_creation_input_tokens": 100,
                 "cache_read_input_tokens": 1000}
        rows = [{"type": "user", "message": {"content": "hi"}},
                {"type": "assistant", "message": {"id": "m1", "usage": usage}},
                {"type": "assistant", "message": {"id": "m1", "usage": usage}},
                {"type": "assistant", "message": {"id": "m2", "usage": {"input_tokens": 1, "output_tokens": 2}}}]
        transcript.write_text("".join(json.dumps(r) + "\n" for r in rows))
        self.hook("post-tool", {"transcript_path": str(transcript)})
        self.assertEqual(runtime_map(self.root)["budget_tokens"], "1118")
        with transcript.open("a") as f:
            f.write(json.dumps({"type": "assistant", "message": {"id": "m3", "usage": {"output_tokens": 7}}}) + "\n")
        self.hook("post-tool", {"transcript_path": str(transcript)})
        self.assertEqual(runtime_map(self.root)["budget_tokens"], "1125")


class Breaker(BreakerBase):
    def test_warns_at_warn_pct_then_trips_at_trip_pct(self):
        self.assertEqual(self.hook("post-tool").stdout, "")
        warn = self.hook("post-tool")
        self.assertIn("BUDGET WARNING", warn.stdout)
        self.assertEqual(self.phase(), "execute")
        trip = self.hook("post-tool")
        self.assertEqual(trip.returncode, 0, trip.stderr)
        self.assertIn("CIRCUIT BREAKER TRIPPED", trip.stdout)
        self.assertEqual(self.phase(), "blocked")
        state = (self.root / ".osengineer/state.yml").read_text()
        self.assertIn("blocked_from: execute", state)
        blocked = (self.root / ".osengineer/BLOCKED.md").read_text()
        self.assertIn("phase-001-breaker", blocked)
        self.assertIn("tool calls: 3 / 2 (150%)", blocked)
        self.assertIn("approve", blocked)

    def test_wall_time_alone_can_trip(self):
        self.plan(tool_calls=100, wall_minutes=1)
        self.hook("post-tool")
        rt_path = self.root / ".osengineer/runtime.yml"
        rt_path.write_text(re.sub(r"budget_last_ts: .*", f"budget_last_ts: {time.time() - 100}", rt_path.read_text()))
        self.hook("post-tool")
        self.assertEqual(self.phase(), "blocked")
        self.assertIn("wall time:", (self.root / ".osengineer/BLOCKED.md").read_text())

    def test_thresholds_come_from_the_profile(self):
        self.profile(budget={"warnPct": 200, "tripPct": 300})
        for _ in range(3):
            self.assertNotIn("BUDGET", self.hook("post-tool").stdout)
        self.assertEqual(self.phase(), "execute")

    def test_blocked_phase_refuses_edits_and_bash(self):
        self.state("blocked")
        edit = self.hook("pre-edit-guard", {"tool_name": "Edit", "tool_input": {"file_path": "src/a.py"}})
        self.assertEqual(json.loads(edit.stdout)["decision"], "block")
        bash = self.hook("pre-bash-guard", {"tool_name": "Bash", "tool_input": {"command": "ls"}})
        self.assertEqual(bash.returncode, 0, bash.stderr)
        out = json.loads(bash.stdout)
        self.assertEqual(out["decision"], "block")
        self.assertIn("blocked", out["reason"])

    def test_bash_is_not_refused_outside_blocked(self):
        bash = self.hook("pre-bash-guard", {"tool_name": "Bash", "tool_input": {"command": "ls"}})
        self.assertEqual(bash.stdout.strip(), "")


class HeadlessRunMetering(HeadlessBase):
    """`osengineer run` meters wall time for every harness, records usage in
    RUN.json, and caps the child at the wall budget left before tripPct."""

    def repo(self, runtime=None, wall_minutes=30):
        repo = make_repo(self.tmp)
        (repo / ".osengineer/.gitignore").write_text("runtime.yml\n.state.lock\n")
        (repo / "planning/active/phase-1/PHASE_PLAN.md").write_text(
            plan_text(tool_calls=50, wall_minutes=wall_minutes, phase_id="phase-001-test"))
        if runtime:
            (repo / ".osengineer/runtime.yml").write_text(runtime)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "setup"], cwd=repo, check=True)
        return repo

    def run_json(self, repo):
        (run_dir,) = [d for d in (repo / ".osengineer/runs").iterdir() if d.is_dir()]
        return json.loads((run_dir / "RUN.json").read_text())

    def test_run_records_usage_against_the_estimate(self):
        repo = self.repo()
        proc = run_cli(repo, ["run", "fix", "T"], self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        usage = self.run_json(repo)["usage"]
        self.assertEqual(usage["phase_id"], "phase-001-test")
        self.assertEqual(usage["estimate"], {"tool_calls": 50, "wall_minutes": 30, "tokens": None})
        self.assertEqual(usage["tool_calls"], 0)
        self.assertIsNone(usage["tokens"])
        self.assertGreaterEqual(usage["wall_seconds"], 0)
        self.assertIn("ratio_pct", usage)
        self.assertIsNone(usage["breaker"])
        rt = runtime_map(repo)
        self.assertEqual(rt["budget_phase"], "phase-001-test")
        self.assertGreater(float(rt["budget_wall_seconds"]), 0)

    def test_run_is_capped_at_the_remaining_wall_budget_and_trips(self):
        # 1 minute budget, trip at 150% = 90 s, 89 s already used: 1 s left.
        repo = self.repo("budget_phase: phase-001-test\nbudget_wall_seconds: 89.0\nbudget_tool_calls: 0\n",
                         wall_minutes=1)
        proc = run_cli(repo, ["run", "fix", "T"], self.env(FAKE_HARNESS_MODE="sleep"))
        self.assertNotEqual(proc.returncode, 0)
        data = self.run_json(repo)
        self.assertEqual(data["status"], "timeout")
        self.assertEqual(data["usage"]["breaker"], "tripped")
        self.assertLessEqual(data["usage"]["timeout_seconds"], 1)
        self.assertIn("phase: blocked", (repo / ".osengineer/state.yml").read_text())
        self.assertIn("headless run", (repo / ".osengineer/BLOCKED.md").read_text())


if __name__ == "__main__":
    unittest.main()
