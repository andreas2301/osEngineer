"""HANDOFF.json (family-handoff/1) is read at one place: the human gate into execute.

autoRoadmap leaves it next to the PHASE_PLAN.md it emits. Until now nothing here
looked at it, so the item's trace id stopped at the phase folder and an edited
plan went through the gate unnoticed. The contract now:

  * a plan without a sidecar is approved as before; osEngineer stays standalone.
  * a matching sidecar puts the trace id on the approval record.
  * a plan that differs from the one handed off needs a human's --reason.
  * a sidecar this release cannot read is refused, naming the file and the key.
"""
import hashlib
import json
import tempfile
import unittest

from test_circuit_breaker import plan_text
from test_phase_gate import approvals, cli, make_repo, phase

TRACE = "3d7cbe5a1b2c:RM-012"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = make_repo(self.tmp.name, "plan")
        self.phase_dir = self.repo / "planning" / "active" / "phase-001-breaker"
        self.phase_dir.mkdir(parents=True)
        self.plan = plan_text()
        (self.phase_dir / "PHASE_PLAN.md").write_text(self.plan)

    def sidecar(self, **overrides):
        record = {
            "schema": "family-handoff/1", "trace_id": TRACE, "roadmap_id": "RM-012", "run_id": "r1",
            "baseline_sha": "08528ee", "producer": {"name": "autoRoadmap", "version": "0.1.3"},
            "consumer": {"name": "osEngineer", "schema_version": "0.6.0", "schema_sha256": "a" * 64},
            "artefact_sha256": sha(self.plan), "citation_ids": ["CIT-0001"],
        }
        record.update(overrides)
        (self.phase_dir / "HANDOFF.json").write_text(json.dumps(record))

    def approve(self, *args):
        return cli(self.repo, "approve", "execute", *args)


class TestGate(Base):
    def test_plan_without_a_sidecar_is_approved_as_before(self):
        proc = self.approve()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("handoff", approvals(self.repo)[-1])

    def test_matching_sidecar_puts_the_trace_id_on_the_record(self):
        self.sidecar()
        proc = self.approve()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(TRACE, proc.stdout)
        self.assertEqual(approvals(self.repo)[-1]["handoff"], {
            "trace_id": TRACE, "producer": "autoRoadmap 0.1.3", "artefact_sha256": sha(self.plan),
            "plan_sha256": sha(self.plan), "plan_changed": False,
        })

    def test_plan_edited_after_the_handoff_needs_a_reason(self):
        self.sidecar()
        (self.phase_dir / "PHASE_PLAN.md").write_text(self.plan + "\nedited\n")
        proc = self.approve()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(TRACE, proc.stderr)
        self.assertIn("--reason", proc.stderr)
        self.assertEqual(phase(self.repo), "plan")
        self.assertEqual(approvals(self.repo), [])

    def test_a_reason_takes_the_edited_plan_and_records_the_change(self):
        self.sidecar()
        (self.phase_dir / "PHASE_PLAN.md").write_text(self.plan + "\nedited\n")
        proc = self.approve("--reason", "reviewed the edit")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("changed", proc.stdout)
        entry = approvals(self.repo)[-1]
        self.assertEqual(entry["reason"], "reviewed the edit")
        self.assertTrue(entry["handoff"]["plan_changed"])
        self.assertEqual(entry["handoff"]["plan_sha256"], sha(self.plan + "\nedited\n"))

    def test_unreadable_sidecars_are_refused(self):
        for overrides, key in (
            ({"schema": "family-handoff/2"}, "schema"),
            ({"consumer": {"name": "somethingElse"}}, "consumer"),
            ({"consumer": "osEngineer"}, "consumer"),
            ({"trace_id": "RM-012"}, "trace_id"),
            ({"trace_id": "3d7cbe5a1b2c:RM-013"}, "trace_id"),
            ({"roadmap_id": None}, "trace_id"),
            ({"producer": {"name": "autoRoadmap"}}, "producer"),
            ({"artefact_sha256": "abc"}, "artefact_sha256"),
        ):
            self.sidecar(**overrides)
            proc = self.approve()
            self.assertNotEqual(proc.returncode, 0, f"accepted {overrides}")
            self.assertIn("HANDOFF.json", proc.stderr)
            self.assertIn(key, proc.stderr)
            self.assertEqual(phase(self.repo), "plan")

    def test_not_json_is_refused(self):
        for text in ("{not json", "[]"):
            (self.phase_dir / "HANDOFF.json").write_text(text)
            proc = self.approve()
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("HANDOFF.json", proc.stderr)

    def test_keys_it_does_not_read_are_left_to_the_producer(self):
        """A second producer adds skill fields; schema id and keys read stay the same."""
        self.sidecar(skill_sha256="b" * 64, rule_ids=["R-1"])
        self.assertEqual(self.approve().returncode, 0)

    def test_only_the_gate_into_execute_reads_it(self):
        (self.phase_dir / "HANDOFF.json").write_text("{not json")
        self.assertEqual(cli(self.repo, "approve", "discuss").returncode, 0)
        self.assertEqual(cli(self.repo, "approve", "plan").returncode, 0)
        self.assertNotEqual(self.approve().returncode, 0)


if __name__ == "__main__":
    unittest.main()
