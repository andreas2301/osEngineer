"""The budget breaker is not the agent's to reset, raise or switch off.

The meter's evidence and its limit both sat within the agent's reach:

  * `osengineer state set budget_tool_calls 0` wrote runtime.yml through the CLI,
    which the file guards never saw; `state set` only refused phase keys.
  * the budget and the phase_id usage is counted under were re-read from
    PHASE_PLAN.md on every call, and that file stays editable in execute, so
    raising a budget or renaming the phase took effect at once.
  * a plan moved out of active/ stopped the metering altogether.
  * .osengineer/profile.json holds budget.tripPct and, with workbench-config.yml,
    the profile switch that turns the meter off; both were as editable as any
    other artifact, and `osengineer profile install` flipped the switch too.

The contract now: hooks alone write the counters, and the budget is the one the
human approved (`osengineer approve` records it). Raising it takes a new approval.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from test_circuit_breaker import plan_text, runtime_map
from test_phase_gate import approvals, bash, cli, edit, is_block, make_repo, phase, run_hook


def post_tool(repo):
    return run_hook("osEngineer-post-tool.py", {
        "session_id": "tamper", "cwd": str(repo), "tool_name": "Read",
        "tool_input": {"file_path": "x"},
    }, repo)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = make_repo(self.tmp.name, "plan")
        self.plan_dir = self.repo / "planning" / "active" / "phase-001-breaker"
        self.plan_dir.mkdir(parents=True)
        self.write_plan()

    def write_plan(self, **kw):
        (self.plan_dir / "PHASE_PLAN.md").write_text(plan_text(**kw))

    def approve(self, target, *args):
        proc = cli(self.repo, "approve", target, *args)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def usage(self):
        return runtime_map(self.repo)


class TestCounterWrites(Base):
    def test_state_set_refuses_every_runtime_field(self):
        (self.repo / ".osengineer" / "runtime.yml").write_text("budget_tool_calls: 7\n")
        for key in ("budget_tool_calls", "budget_wall_seconds", "budget_phase", "budget_ratio_pct",
                    "budget_warned", "budget_used", "context_used_pct"):
            proc = cli(self.repo, "state", "set", key, "0")
            self.assertNotEqual(proc.returncode, 0, f"state set {key} was accepted")
            self.assertIn(key, proc.stderr)
        self.assertEqual(self.usage(), {"budget_tool_calls": "7"})

    def test_the_cli_refuses_what_the_guard_cannot_spell(self):
        """`$o state set ...` is past any pattern; the refusal at the source still holds."""
        self.assertFalse(is_block(bash(self.repo, "o=osengineer; $o state set budget_tool_calls 0")))
        self.assertNotEqual(cli(self.repo, "state", "set", "budget_tool_calls", "0").returncode, 0)

    def test_state_set_still_sets_other_keys(self):
        self.assertEqual(cli(self.repo, "state", "set", "current_team", "coding").returncode, 0)

    def test_guard_refuses_the_meter_routes(self):
        for cmd in (
            "osengineer state set budget_tool_calls 0",
            "cd sub && osengineer state set budget_phase x",
            "python3 bin/osengineer state set budget_wall_seconds 0",
            "osengineer state set budget_used 0",
            "osengineer state set context_used_pct 0",
            "python3 -c 'from osengineer_common import update_state_fields'",
            "python3 -c 'import osengineer_common as c; c._rewrite_fields'",
            "echo '{}' > .osengineer/profile.json",
            "sed -i 's/150/1000/' .osengineer/profile.json",
            "cp /tmp/x .osengineer/profile.json",
            "mv .osengineer /tmp/ose-away",
            "mv .osengineer/ /tmp/ose-away",
            "rm -r .osengineer",
            "git checkout HEAD~1 -- .osengineer",
            "git restore --source=HEAD~1 .osengineer/",
            "git clean -fdX",
            "git stash -a",
            "git stash push --all",
            "osengineer profile install --repo .",
            "osengineer profile detect --repo . --write",
            "python3 -m repo_profile install --repo .",
            "echo 'validation_profile: repo' > .osengineer/workbench-config.yml",
        ):
            self.assertTrue(is_block(bash(self.repo, cmd)), f"agent could run: {cmd}")

    def test_guard_lets_reads_and_look_alike_files_through(self):
        for cmd in (
            "osengineer state",
            "osengineer state set current_team coding",
            "cat .osengineer/profile.json",
            "git add .osengineer/profile.json",
            "cp fixtures/profile.json /tmp/x",
            "echo '{}' > fixtures/profile.json",
            "ls .osengineer",
            "grep -r phase .osengineer",
            "git clean -n",
            "git stash",
            "git stash list",
            "mv src/.osengineer-notes /tmp/x",
            "osengineer profile detect --repo .",
            "python3 -m repo_profile doctor --repo .",
            "cat .osengineer/workbench-config.yml",
        ):
            self.assertFalse(is_block(bash(self.repo, cmd)), f"false positive: {cmd}")

    def test_edit_guard_refuses_the_profile_only(self):
        self.assertTrue(is_block(edit(self.repo, self.repo / ".osengineer" / "profile.json")))
        self.assertTrue(is_block(edit(self.repo, self.repo / ".osengineer" / "workbench-config.yml")))
        self.assertFalse(is_block(edit(self.repo, self.repo / "planning" / "profile.json")))

    def test_bypass_does_not_lift_the_profile_refusal(self):
        proc = edit(self.repo, self.repo / ".osengineer" / "profile.json", OSE_BYPASS="1")
        self.assertTrue(is_block(proc))


class TestApprovedBudget(Base):
    def setUp(self):
        super().setUp()
        self.approve("execute")

    def test_approval_records_the_budget(self):
        record = next(line for line in (self.repo / ".osengineer" / "state.yml").read_text().splitlines()
                      if line.startswith("phase_approved_budget:"))
        data = json.loads(record.split(":", 1)[1])
        self.assertEqual(data["phase_id"], "phase-001-breaker")
        self.assertEqual(data["plan"], "planning/active/phase-001-breaker/PHASE_PLAN.md")
        self.assertEqual(data["estimate"], {"tool_calls": 2, "wall_minutes": 60, "tokens": None})

    def test_approval_log_names_the_budget(self):
        self.assertEqual(approvals(self.repo)[-1]["budget"]["estimate"]["tool_calls"], 2)

    def test_raising_the_plan_budget_changes_nothing(self):
        post_tool(self.repo)
        self.write_plan(tool_calls=1000)
        post_tool(self.repo)
        self.assertEqual(self.usage()["budget_ratio_pct"], "100")
        post_tool(self.repo)
        self.assertEqual(phase(self.repo), "blocked")

    def test_renaming_the_phase_does_not_reset_usage(self):
        post_tool(self.repo)
        self.write_plan(phase_id="phase-002-fresh-start")
        post_tool(self.repo)
        self.assertEqual(self.usage()["budget_tool_calls"], "2")
        self.assertEqual(self.usage()["budget_phase"], "phase-001-breaker")

    def test_moving_the_plan_away_does_not_stop_the_meter(self):
        post_tool(self.repo)
        backlog = self.repo / "planning" / "backlog"
        backlog.mkdir()
        shutil.move(str(self.plan_dir), str(backlog))
        proc = post_tool(self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.usage()["budget_tool_calls"], "2")

    def test_trip_after_the_plan_moved_names_the_approved_plan(self):
        post_tool(self.repo)
        shutil.rmtree(self.plan_dir)
        post_tool(self.repo)
        post_tool(self.repo)
        self.assertEqual(phase(self.repo), "blocked")
        blocked = (self.repo / ".osengineer" / "BLOCKED.md").read_text()
        self.assertIn("planning/active/phase-001-breaker/PHASE_PLAN.md", blocked)

    def test_invalid_plan_still_fails_closed(self):
        (self.plan_dir / "PHASE_PLAN.md").write_text("# no frontmatter\n")
        self.assertEqual(post_tool(self.repo).returncode, 2)

    def test_a_human_raises_it_by_approving_again(self):
        for _ in range(3):
            post_tool(self.repo)
        self.assertEqual(phase(self.repo), "blocked")
        self.approve("plan")
        self.write_plan(tool_calls=100)
        self.approve("execute")
        post_tool(self.repo)
        self.assertEqual(self.usage()["budget_tool_calls"], "4")
        self.assertEqual(self.usage()["budget_ratio_pct"], "4")
        self.assertEqual(phase(self.repo), "execute")

    def test_a_new_approved_phase_starts_from_zero(self):
        post_tool(self.repo)
        cli(self.repo, "approve", "blocked")
        self.approve("plan")
        self.write_plan(phase_id="phase-002-next", tool_calls=10)
        self.approve("execute")
        post_tool(self.repo)
        self.assertEqual(self.usage()["budget_phase"], "phase-002-next")
        self.assertEqual(self.usage()["budget_tool_calls"], "1")

    def test_approval_without_a_plan_clears_the_old_budget(self):
        cli(self.repo, "approve", "blocked")
        self.approve("plan")
        shutil.rmtree(self.plan_dir)
        self.approve("micro")
        post_tool(self.repo)
        self.assertNotIn("budget_tool_calls", self.usage())

    def test_the_record_is_out_of_reach(self):
        proc = cli(self.repo, "state", "set", "phase_approved_budget", "{}")
        self.assertNotEqual(proc.returncode, 0)
        self.assertTrue(is_block(bash(self.repo, "osengineer state set phase_approved_budget x")))

    def test_an_invalid_plan_is_approved_as_before(self):
        """Presence is what the gate checks; the guards refuse the plan in execute."""
        (self.plan_dir / "PHASE_PLAN.md").write_text("# no frontmatter\n")
        cli(self.repo, "approve", "blocked")
        self.approve("plan")
        self.approve("execute")
        self.assertTrue(is_block(edit(self.repo, self.repo / "src.py")))


if __name__ == "__main__":
    unittest.main()
