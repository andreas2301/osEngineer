"""PHASE_PLAN.md frontmatter: strict stdlib validation, schema parity, budget estimate."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from repo_profile import phase_plan

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "specs" / "SCHEMAS" / "phase-plan.schema.json"
TEMPLATE = ROOT / "planning" / "TEMPLATES" / "PHASE_PLAN.md"

VALID = {
    "phase_id": "phase-033-retry-backoff",
    "goal": "Add exponential backoff to the executor retry path.",
    "tasks": [
        {"id": "T1", "description": "Write the failing test", "acceptance": "test is red",
         "budget": {"tool_calls": 20, "wall_minutes": 10, "tokens": 50000}},
        {"id": "T2", "description": "Implement", "acceptance": "tests green", "depends_on": ["T1"],
         "budget": {"tool_calls": 40, "wall_minutes": 30}},
    ],
}


def render(data, body="\n# Phase\n"):
    return "---\n" + json.dumps(data, indent=2) + "\n---\n" + body


class Validate(unittest.TestCase):
    def test_valid_plan_parses(self):
        plan = phase_plan.parse(render(VALID), "p")
        self.assertEqual(plan["phase_id"], "phase-033-retry-backoff")

    def test_estimate_sums_task_budgets(self):
        self.assertEqual(phase_plan.estimate(VALID),
                         {"tool_calls": 60, "wall_minutes": 40, "tokens": 50000})
        no_tokens = copy.deepcopy(VALID)
        del no_tokens["tasks"][0]["budget"]["tokens"]
        self.assertIsNone(phase_plan.estimate(no_tokens)["tokens"])

    def rejected(self, text, fragment):
        with self.assertRaises(phase_plan.PlanError) as caught:
            phase_plan.parse(text, "planning/active/x/PHASE_PLAN.md")
        self.assertIn("planning/active/x/PHASE_PLAN.md", str(caught.exception))
        self.assertIn(fragment, str(caught.exception))

    def mutate(self, fn):
        data = copy.deepcopy(VALID)
        fn(data)
        return render(data)

    def test_invalid_plans_fail_closed_naming_the_key(self):
        cases = [
            ("# Phase 1\n", "frontmatter"),
            ("---\nphase_id: phase-001-x\n---\n", "JSON"),
            ("---\n[]\n---\n", "must be an object"),
            (self.mutate(lambda d: d.pop("tasks")), "tasks"),
            (self.mutate(lambda d: d.update(extra=1)), "unknown keys: extra"),
            (self.mutate(lambda d: d.update(phase_id="phase-1")), "phase_id"),
            (self.mutate(lambda d: d.update(goal="short")), "goal"),
            (self.mutate(lambda d: d.update(classification="epic")), "classification"),
            (self.mutate(lambda d: d.update(tasks=[])), "tasks"),
            (self.mutate(lambda d: d["tasks"][0].update(id="1")), "tasks[0].id"),
            (self.mutate(lambda d: d["tasks"][1].update(id="T1")), "duplicate"),
            (self.mutate(lambda d: d["tasks"][1].update(depends_on=["T9"])), "tasks[1].depends_on"),
            (self.mutate(lambda d: d["tasks"][0].pop("budget")), "tasks[0].budget"),
            (self.mutate(lambda d: d["tasks"][0]["budget"].pop("tool_calls")), "tasks[0].budget.tool_calls"),
            (self.mutate(lambda d: d["tasks"][0]["budget"].update(wall_minutes=0)), "tasks[0].budget.wall_minutes"),
            (self.mutate(lambda d: d["tasks"][0]["budget"].update(tool_calls=True)), "tasks[0].budget.tool_calls"),
            (self.mutate(lambda d: d["tasks"][0]["budget"].update(tokens=5)), "tasks[0].budget.tokens"),
            (self.mutate(lambda d: d["tasks"][0]["budget"].update(usd=1)), "unknown keys: usd"),
            (self.mutate(lambda d: d["tasks"][0].update(status="done")), "tasks[0].status"),
            (self.mutate(lambda d: d.update(risk_flags=[{"risk": "r", "likelihood": "x", "impact": "low"}])),
             "risk_flags[0].likelihood"),
            (self.mutate(lambda d: d.update(acceptance_criteria=[1])), "acceptance_criteria"),
        ]
        for text, fragment in cases:
            with self.subTest(fragment=fragment):
                self.rejected(text, fragment)

    def test_active_plan_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            planning = Path(tmp)
            self.assertIsNone(phase_plan.load_active(planning))
            d = planning / "active" / "phase-033"
            d.mkdir(parents=True)
            (d / "PHASE_PLAN.md").write_text(render(VALID))
            path, plan = phase_plan.load_active(planning)
            self.assertEqual(path, d / "PHASE_PLAN.md")
            self.assertEqual(plan["goal"], VALID["goal"])
            other = planning / "active" / "phase-034"
            other.mkdir()
            (other / "PHASE_PLAN.md").write_text(render(VALID))
            with self.assertRaises(phase_plan.PlanError) as caught:
                phase_plan.load_active(planning)
            self.assertIn("more than one", str(caught.exception))


class SchemaParity(unittest.TestCase):
    """The schema documents what the validator enforces; they must not drift."""

    def setUp(self):
        self.schema = json.loads(SCHEMA.read_text())

    def test_closed_schema_matches_validator_keys(self):
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual(set(self.schema["properties"]), set(phase_plan.TOP_KEYS))
        self.assertEqual(set(self.schema["required"]), set(phase_plan.TOP_REQUIRED))
        task = self.schema["properties"]["tasks"]["items"]
        self.assertFalse(task["additionalProperties"])
        self.assertEqual(set(task["properties"]), set(phase_plan.TASK_KEYS))
        self.assertEqual(set(task["required"]), set(phase_plan.TASK_REQUIRED))
        budget = task["properties"]["budget"]
        self.assertFalse(budget["additionalProperties"])
        self.assertEqual({k: v["minimum"] for k, v in budget["properties"].items()},
                         phase_plan.BUDGET_MINIMUMS)
        self.assertEqual(set(budget["required"]), set(phase_plan.BUDGET_REQUIRED))

    def test_template_frontmatter_validates(self):
        phase_plan.parse(TEMPLATE.read_text(), str(TEMPLATE))


if __name__ == "__main__":
    unittest.main()
